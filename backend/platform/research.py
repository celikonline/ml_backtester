"""Development-only optimization followed by a single frozen-candidate test."""
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
from scipy.stats import kurtosis, norm, skew, spearmanr
from sklearn.feature_selection import mutual_info_regression
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from backend.engine import features, fx_backtest, metrics, causal_probabilities
from backend.quant.fitness import QuantFitnessCalculator
from backend.quant.validation import PurgedKFold, rolling_splits, anchored_splits
from .models import MODEL_REGISTRY, ModelAdapter
from .schema import ExperimentSpec
from .families import family_for_column
from .indicators import cached_indicators, indicator_names, rule_masks, apply_rules


def feature_frame(df, cache_dir=None):
    x = features(df)
    x = x.join(cached_indicators(df, cache_dir))
    base_columns = list(x.columns)
    r = np.log(df.close).diff()
    window = r.rolling(30)
    additions = {
        "quantile_25": window.quantile(.25), "quantile_75": window.quantile(.75),
        "rolling_min": window.min(), "rolling_max": window.max(),
        "rolling_skew": window.skew(), "rolling_kurtosis": window.kurt(),
        "rolling_iqr": window.quantile(.75) - window.quantile(.25),
        "signal_noise": window.mean() / window.std().replace(0, np.nan),
        "tanh_momentum": np.tanh(df.close.pct_change(14) * 100),
    }
    for name, s in additions.items():
        x[name] = s.reindex(x.index)
    # External observations are restricted to values known before the bar and
    # then shifted once more. This makes alignment explicit even for sources
    # that do not provide release timestamps.
    for column in df.columns:
        if column in {"open", "high", "low", "close"} or column.endswith("__available_at") or family_for_column(column) is None:
            continue
        series = pd.to_numeric(df[column], errors="coerce")
        timestamp_column = f"{column}__available_at"
        if timestamp_column in df:
            series = series.where(pd.to_datetime(df[timestamp_column], utc=True, errors="coerce") <= df.index)
        x[f"lag__{column}"] = series.shift(1)
        x[f"delta__{column}"] = series.diff().shift(1)
        x[f"return__{column}"] = series.pct_change(fill_method=None).shift(1)
    # A sparse macro source must not shorten a purely technical experiment.
    # Its missing values are only resolved once the selected feature pool is
    # known in ``_execute``.
    return x.replace([np.inf, -np.inf], np.nan).dropna(subset=base_columns)


def registry(df=None):
    names = [f"return_{n}" for n in [0,1,2,3,6]]
    names += [f"{kind}_{w}" for w in [6,14,30,50] for kind in ["momentum","sma","volatility"]]
    names += ["range","body","macd","rsi","hour_sin","hour_cos","quantile_25","quantile_75","rolling_min","rolling_max","rolling_skew","rolling_kurtosis","rolling_iqr","signal_noise","tanh_momentum"]
    names += indicator_names()
    def group(name):
        if name.startswith(("quantile", "rolling", "signal_noise", "tanh")): return "statistical"
        if name.startswith(("volatility", "atr_", "bb_position_")) or name == "range": return "volatility"
        if name.startswith(("sma", "ema_")) or name == "macd": return "trend"
        return "momentum"
    items = [{"id": n, "name": n, "category": group(n), "version": "1", "lookback": 50,
              "availability": "OHLC bar kapanışından sonra", "source_columns": ["open","high","low","close"]} for n in names]
    if df is not None:
        for column in df.columns:
            if column.endswith("__available_at"):
                continue
            family = family_for_column(column)
            if family is None:
                continue
            verified = f"{column}__available_at" in df
            availability = "Yayın zamanı denetlendi; bir bar gecikmeli" if verified else "Bir bar gecikmeli; yayın zamanı doğrulanmadı"
            for prefix, label in [("lag__", "gecikmeli seviye"), ("delta__", "gecikmeli değişim"), ("return__", "gecikmeli getiri")]:
                items.append({"id": prefix + column, "name": f"{label}: {column}", "category": "lagged_external",
                              "family": family, "version": "1", "lookback": 1, "availability": availability,
                              "source_columns": [column] + ([f"{column}__available_at"] if verified else [])})
    return items


def score(ret, signal, annual):
    m = metrics(ret, signal, annual)
    downside = np.sqrt(np.mean(np.minimum(ret, 0) ** 2))
    observed_sharpe=float(m.get("sharpe", 0.0))
    n=max(2,len(ret)); g=float(skew(ret,bias=False)) if n>2 else 0.0; k=float(kurtosis(ret,fisher=False,bias=False)) if n>3 else 3.0
    denominator=max(1e-12, 1.0-g*observed_sharpe+((k-1.0)/4.0)*(observed_sharpe**2))
    psr=float(norm.cdf((observed_sharpe*np.sqrt(n-1))/np.sqrt(denominator)))
    total_return=float(m.get("return",0.0))
    annualized=(1.0+total_return)**(annual/max(1,n))-1.0 if total_return>-1.0 else -1.0
    m.update(sortino=float(np.mean(ret) / downside * np.sqrt(annual)) if downside > 1e-12 else 0.0,
             volatility=float(np.std(ret) * np.sqrt(annual)), exposure=float(np.mean(signal != 0)),
             turnover=float(np.abs(np.diff(signal, prepend=0)).sum() + abs(signal[-1])),
             annualized_return=float(annualized), psr=psr)
    return m


#: Minimum validation bars for a regime slice to count toward the
#: worst-regime gate and coverage. Smaller slices are reported but ignored.
MIN_REGIME_BARS = 15


class RegimeRouter:
    """Turns descriptive regimes into a measurable selection input.

    The HMM behind ``states`` is fitted on development data only and states
    come from causal forward-filtering, so reports use validation folds only:
    never test data, never future bars. The router records per-regime
    validation metrics plus worst-regime drawdown and coverage; selection
    pressure flows through the worst-regime gate in ``check_constraints``.
    Per-regime model/strategy routing at inference is explicitly out of scope.
    """

    def __init__(self, states, n_states, min_regime_bars=MIN_REGIME_BARS):
        self.states = np.asarray(states)
        self.n_states = n_states
        self.min_regime_bars = min_regime_bars

    def report(self, ret, signal, annual):
        ret, signal = np.asarray(ret, dtype=float), np.asarray(signal)
        entries = []
        for k in range(self.n_states):
            mask = self.states == k
            bars = int(mask.sum())
            if bars:
                m = metrics(ret[mask], signal[mask], annual)
                entry = {"regime": int(k), "bars": bars, "share": float(mask.mean()),
                         "sharpe": m["sharpe"], "return": m["return"], "max_drawdown": m["max_drawdown"],
                         "qualified": bool(bars >= self.min_regime_bars)}
            else:
                entry = {"regime": int(k), "bars": 0, "share": 0.0,
                         "sharpe": 0.0, "return": 0.0, "max_drawdown": 0.0, "qualified": False}
            entries.append(entry)
        qualified = [e for e in entries if e["qualified"]]
        worst = min((e["max_drawdown"] for e in qualified), default=None)
        coverage = len(qualified) / self.n_states if self.n_states else 0.0
        return {"regime_metrics": entries, "worst_regime_drawdown": worst, "regime_coverage": float(coverage)}


def splits(n, method, train_ratio, folds, gap, purge_window=0, embargo_pct=0.01,
           train_window=500, test_window=50, step=50, validation_ratio=.15):
    """Leakage-safe partitions. Returns [(train, val, meta)] with meta holding
    ``purged_samples`` / ``embargo_samples`` for the fold artifact (Sprint 3).

    - holdout / walk_forward: previous behavior, gap-separated.
    - purged_kfold: PurgedKFold with purge_window + embargo; train is past-only.
    - rolling / anchored: fixed / growing windows stepping through history.
    """
    from .schema import DomainError
    try:
        if method == "holdout":
            a = int(n * train_ratio / (train_ratio + validation_ratio))
            if a - gap < 1 or a >= n:
                raise ValueError("holdout")
            return [(np.arange(a-gap), np.arange(a,n),
                     {"method": method, "purged_samples": 0, "embargo_samples": 0})]
        if method == "purged_kfold":
            kf = PurgedKFold(n_splits=folds, purge_window=purge_window, embargo_pct=embargo_pct)
            embargo = kf._embargo(n)
            out = []
            for train, val in kf.split(np.arange(n)):
                out.append((train, val, {"method": method,
                                         "purged_samples": int(min(purge_window, val[0])),
                                         "embargo_samples": int(min(embargo, n - val[-1] - 1))}))
            return out
        if method == "rolling":
            return [(t, v, {"method": method, "purged_samples": 0, "embargo_samples": 0})
                    for t, v in rolling_splits(n, train_window, test_window, step)]
        if method == "anchored":
            return [(t, v, {"method": method, "purged_samples": 0, "embargo_samples": 0})
                    for t, v in anchored_splits(n, train_window, test_window, step)]
        return [(t, v, {"method": "walk_forward", "purged_samples": 0, "embargo_samples": 0})
                for t, v in TimeSeriesSplit(n_splits=folds, gap=gap).split(np.arange(n))]
    except DomainError:
        raise
    except ValueError:
        raise DomainError("Doğrulama için yeterli veri yok.", 422, "validation_error")


def count_splits(spec, n):
    """Fold count for budget accounting without materializing partitions."""
    m = spec.validation.method
    if m == "holdout":
        return 1
    if m == "purged_kfold":
        return spec.validation.folds
    if m in ("rolling", "anchored"):
        try:
            gen = (rolling_splits if m == "rolling" else anchored_splits)(
                n, spec.validation.train_window, spec.validation.test_window, spec.validation.step)
            return sum(1 for _ in gen)
        except ValueError:
            return 0
    return spec.validation.folds


#: Objective vector recorded per candidate: key → True when higher is better.
#: Turnover and cost are minimized. Exposure stays a constraint (and metric),
#: not a dominance dimension, so the Pareto front keeps its return-quality
#: semantics from (sharpe, return, max_drawdown).
OBJECTIVE_DIRECTIONS = {"sharpe": True, "return": True, "sortino": True,
                        "max_drawdown": True, "turnover": False, "cost_bps_estimate": False}


def _dominates(a, b):
    """Higher is better on sharpe, return and (negative) max_drawdown."""
    keys = ("sharpe", "return", "max_drawdown")
    return all(a[k] >= b[k] for k in keys) and any(a[k] > b[k] for k in keys)


def pareto_ranks(candidates):
    """Non-dominated sorting layers over feasible candidates (rank 0 = front).

    Infeasible candidates get no rank (``None``); ``pareto_front`` below
    returns exactly the rank-0 set.
    """
    feasible = [c for c in candidates if c["feasible"]]
    by_id = {c["id"]: c for c in feasible}
    remaining = set(by_id)
    ranks = {}
    rank = 0
    while remaining:
        front = [i for i in remaining
                 if not any(j != i and _dominates(by_id[j]["metrics"], by_id[i]["metrics"]) for j in remaining)]
        if not front:  # defensive: identical metrics can never empty the front
            for i in sorted(remaining):
                ranks[i] = rank
            break
        for i in sorted(front):
            ranks[i] = rank
            remaining.discard(i)
        rank += 1
    return ranks


def pareto_front(candidates):
    feasible = [c for c in candidates if c["feasible"]]
    return [c for c in feasible if not any(
        d["metrics"]["sharpe"] >= c["metrics"]["sharpe"] and d["metrics"]["return"] >= c["metrics"]["return"] and d["metrics"]["max_drawdown"] >= c["metrics"]["max_drawdown"]
        and any(d["metrics"][k] > c["metrics"][k] for k in ["sharpe","return","max_drawdown"])
        for d in feasible)]


def merged_reality(spec):
    """Single cost-model source: validation folds and the final test share it.

    ``reality`` is the source of truth for leverage sizing; the legacy
    top-level ``BacktestSpec.max_leverage / max_position_fraction`` are only
    honored when ``reality`` is still at its default (backward compatibility).
    """
    reality = spec.backtest.reality
    leverage = reality.max_leverage
    fraction = reality.max_position_fraction
    if spec.backtest.max_leverage != 1.0 and leverage == 1.0:
        leverage = spec.backtest.max_leverage
    if spec.backtest.max_position_fraction != 1.0 and fraction == 1.0:
        fraction = spec.backtest.max_position_fraction
    return reality.model_copy(update={"slippage_bps": spec.backtest.slippage_bps + reality.slippage_bps,
                                                    "spread_bps": spec.backtest.spread_bps + 2 * spec.backtest.cost_bps,
                                                    "max_leverage": leverage,
                                                    "max_position_fraction": fraction})


def optimize(x_dev, y_dev, spec, annual, emit, dev_market=None, router=None, signal_masks=None):
    """This function receives no holdout/test data, index or test callback.

    ``router`` (a dev-fitted, causal RegimeRouter) adds validation-only regime
    reports to every candidate and enables the worst-regime gate. Without it
    the gate is skipped and regime fields stay empty.
    """
    o = spec.optimization
    rng = np.random.default_rng(spec.seed)
    columns = list(x_dev.columns)
    min_count, max_count = min(o.min_features,len(columns)), min(o.max_features,len(columns))
    v = spec.validation
    partitions = splits(len(x_dev), v.method, v.train_ratio, v.folds, v.gap,
                        v.purge_window, v.embargo_pct, v.train_window, v.test_window, v.step, v.validation_ratio)
    reality = merged_reality(spec)
    # Sprint2: adapter GA'yı bozmaz — eski ranking default korunur.
    # feature_quality = seçili feature'ların dev-verideki mean abs(Spearman IC)'si (Sprint1 çıktısı).
    calc = QuantFitnessCalculator(getattr(o, "fitness_weights", None) or None)
    y_dev_series = pd.Series(np.asarray(y_dev).ravel(), index=x_dev.index)
    abs_ic_by_feature = {}
    for col in columns:
        s = x_dev[col]
        paired = pd.DataFrame({"f": s, "t": y_dev_series}).dropna()
        if len(paired) >= 3 and paired["f"].nunique() > 1 and paired["t"].nunique() > 1:
            v = spearmanr(paired["f"], paired["t"]).statistic
            abs_ic_by_feature[col] = float(abs(v)) if np.isfinite(v) else 0.0
        else:
            abs_ic_by_feature[col] = 0.0
    use_quant = bool(getattr(o, "use_quant_fitness", False))
    cache, generations = {}, []
    # One-way cost estimate per unit turnover (fixed leg of the merged reality;
    # the ohlc_range leg varies per bar and is accounted exactly in fx_backtest).
    one_way_bps = reality.spread_bps / 2 + reality.commission_bps + reality.slippage_bps
    # Lineage bookkeeping (never hashed into the genome): birth round's parent
    # candidate ids per genome key. First-seen evaluation wins; elites and
    # duplicate genomes keep their original generation/parents.
    birth_parents: dict[str, list[str]] = {}
    current_round = {"n": 1}

    def genome_key(genome):
        return hashlib.sha256(json.dumps(genome, sort_keys=True).encode()).hexdigest()[:16]

    def repair(mask):
        ids = np.flatnonzero(mask)
        if len(ids) > max_count:
            mask[rng.choice(ids, len(ids)-max_count, replace=False)] = False
        if mask.sum() < min_count:
            ids = np.flatnonzero(~mask)
            mask[rng.choice(ids, min_count-int(mask.sum()), replace=False)] = True
        return mask

    def random_genome():
        return {"mask": repair(rng.random(len(columns)) < .5).tolist(), "model": str(rng.choice(spec.models)),
                "param": int(rng.integers(3)) if o.hyperparameters else 1, "threshold": float(rng.choice(o.thresholds_bps))}

    def check_constraints(m, regime):
        violations = []
        if abs(m["max_drawdown"]) > o.max_drawdown: violations.append("max_drawdown")
        if m["position_changes"] < o.min_trades: violations.append("min_trades")
        if o.max_exposure is not None and m["exposure"] > o.max_exposure + 1e-12: violations.append("max_exposure")
        if o.max_worst_regime_drawdown is not None:
            worst = regime.get("worst_regime_drawdown")
            if worst is None or worst < -o.max_worst_regime_drawdown: violations.append("worst_regime_drawdown")
        return violations

    def evaluate(genome):
        key = genome_key(genome)
        if key in cache: return cache[key]
        chosen = [c for c,on in zip(columns,genome["mask"]) if on]
        params = MODEL_REGISTRY[genome["model"]]["parameters"][genome["param"]]
        returns, signals, positions, fold_metrics = [], [], [], []
        for train, val, meta in partitions:
            emit("optimization.candidate.started", {"evaluated": len(cache), "candidate_id": key})
            model = ModelAdapter(genome["model"], params, spec.seed).fit(x_dev.iloc[train][chosen],y_dev[train])
            pred = model.predict(x_dev.iloc[val][chosen])
            if signal_masks is not None:
                pred = apply_rules(pred, [mask[val] for mask in signal_masks])
            stamps = x_dev.index[val]
            bars = (dev_market["high"].to_numpy()[val], dev_market["low"].to_numpy()[val]) if dev_market is not None else (None, None)
            ret, sig, _ = fx_backtest(pred,y_dev[val],reality,stamps,genome["threshold"]/10000,high=bars[0],low=bars[1])
            returns.extend(ret); signals.extend(sig); positions.extend(np.asarray(val).tolist())
            fold_metrics.append({"train_end": x_dev.index[train[-1]].isoformat(), "validation_start": x_dev.index[val[0]].isoformat(),
                                 "validation_end": x_dev.index[val[-1]].isoformat(), "gap_bars": int(val[0]-train[-1]-1),
                                 "purged_samples": meta["purged_samples"], "embargo_samples": meta["embargo_samples"], **score(ret,sig,annual)})
        m = score(np.array(returns),np.array(signals),annual)
        if router is not None:
            aligned = RegimeRouter(router.states[np.asarray(positions)], router.n_states, router.min_regime_bars)
            regime = aligned.report(np.array(returns), np.array(signals), annual)
        else:
            regime = {"regime_metrics": [], "worst_regime_drawdown": None, "regime_coverage": 0.0}
        violations = check_constraints(m, regime)
        feasible = not violations
        # Sprint1 -> Sprint2: seçili setin kalitesi (dev-only, holdout/test yok).
        fq = float(np.mean([abs_ic_by_feature.get(c, 0.0) for c in chosen])) if chosen else 0.0
        breakdown = calc.breakdown(m["sharpe"], fq, m["max_drawdown"], m["turnover"],
                                   n_features=len(chosen))
        quant_fitness = (breakdown["sharpe_contribution"] + breakdown["feature_quality_contribution"]
                         - breakdown["drawdown_penalty"] - breakdown["turnover_penalty"]
                         - breakdown["feature_count_penalty"])
        if use_quant:
            fitness = quant_fitness if feasible else -1000000 - abs(m["max_drawdown"])
        else:
            fitness = m[o.objective] if feasible else -1000000 - abs(m["max_drawdown"])
        objectives = {"sharpe": m["sharpe"], "return": m["return"], "sortino": m["sortino"],
                      "max_drawdown": m["max_drawdown"], "turnover": m["turnover"],
                      "cost_bps_estimate": float(m["turnover"] * one_way_bps)}
        c = {"id": key, "genome": genome, "features": chosen, "model": genome["model"], "parameters": params,
             "threshold_bps": genome["threshold"], "metrics": m, "fitness": fitness, "feasible": feasible, "folds": fold_metrics,
             "objectives": objectives, "constraint_violations": violations,
             "regime_metrics": regime["regime_metrics"], "worst_regime_drawdown": regime["worst_regime_drawdown"],
             "regime_coverage": regime["regime_coverage"],
             "generation": current_round["n"], "parents": list(birth_parents.get(key, [])),
             # Sprint2 §6 breakdown artifact (her candidate için).
             "feature_quality": fq, "quant_fitness": quant_fitness,
             "fitness_breakdown": {"candidate_id": key, "generation": current_round["n"],
                                   "sharpe": m["sharpe"], "feature_quality": fq,
                                   "max_drawdown": m["max_drawdown"], "turnover": m["turnover"],
                                   "fitness": quant_fitness, **breakdown}}
        cache[key] = c
        return c

    if o.algorithm in ("grid", "random"):
        if o.algorithm == "grid":
            genomes = [{"mask": [True]*len(columns), "model": name, "param": param, "threshold": float(threshold)}
                       for name in spec.models for param in (range(3) if o.hyperparameters else [1]) for threshold in o.thresholds_bps]
        else:
            genomes = [random_genome() for _ in range(o.population*o.generations)]
        for genome in genomes: evaluate(genome)
    elif o.algorithm == "none":
        genomes = [{"mask": [True]*len(columns), "model": name, "param": 1, "threshold": 0.0} for name in spec.models]
        for g in genomes:
            birth_parents.setdefault(genome_key(g), [])
        population = [evaluate(g) for g in genomes]
    else:
        population = [random_genome() for _ in range(o.population)]
        # Ensure every requested model is represented in the initial population.
        for i, model_id in enumerate(spec.models[:len(population)]): population[i]["model"] = model_id
        for g in population:
            birth_parents.setdefault(genome_key(g), [])
        for generation in range(o.generations):
            current_round["n"] = generation + 1
            started = time.monotonic()
            ranked = sorted([evaluate(g) for g in population], key=lambda c:(c["fitness"],c["id"]), reverse=True)
            values = [c["fitness"] for c in ranked]
            summary = {"generation":generation+1,"total_generations":o.generations,"best_fitness":max(values),"mean_fitness":float(np.mean(values)),
                       "median_fitness":float(np.median(values)),"worst_fitness":min(values),"diversity":len({c["id"] for c in ranked})/len(ranked),
                       "candidate_count":len(cache),"duration_seconds":time.monotonic()-started,"best":ranked[0]}
            generations.append(summary)
            emit("optimization.generation.completed",summary)
            new = [dict(c["genome"]) for c in ranked[:o.elitism]]
            while len(new) < o.population:
                draws = rng.choice(len(ranked),size=(2,3))
                p1c,p2c = [max((ranked[int(i)] for i in triplet),key=lambda c:c["fitness"]) for triplet in draws]
                p1,p2 = p1c["genome"],p2c["genome"]
                mask = np.array(p1["mask"],dtype=bool)
                if rng.random() < o.crossover_rate:
                    choose = rng.random(len(mask)) < .5
                    mask[choose] = np.array(p2["mask"])[choose]
                flip = rng.random(len(mask)) < o.mutation_rate
                mask[flip] = ~mask[flip]
                child = {**p1,"mask":repair(mask).tolist()}
                if rng.random() < o.mutation_rate: child["model"] = str(rng.choice(spec.models))
                if o.hyperparameters and rng.random() < o.mutation_rate: child["param"] = int(rng.integers(3))
                if rng.random() < o.mutation_rate: child["threshold"] = float(rng.choice(o.thresholds_bps))
                new.append(child)
                birth_parents.setdefault(genome_key(child), sorted({p1c["id"], p2c["id"]}))
            population = new
        population = list(cache.values())
    candidates = sorted(cache.values(),key=lambda c:(c["fitness"],c["id"]),reverse=True)
    feasible = [c for c in candidates if c["feasible"]]
    if not feasible: raise ValueError("Kısıtları sağlayan aday yok (düşüş/işlem/pozisyon). Test açılmadı.")
    ranks = pareto_ranks(candidates)
    for c in candidates:
        c["pareto_rank"] = ranks.get(c["id"])
        c["dominance_count"] = sum(1 for d in candidates if d["id"] != c["id"] and _dominates(d["metrics"], c["metrics"]))
    top = feasible[:max(1,int(np.ceil(len(feasible)*.25)))]
    survival = [{"feature":name,"selection_frequency":float(np.mean([name in c["features"] for c in candidates])),
                 "top_survival":float(np.mean([name in c["features"] for c in top])),
                 "fitness_present":float(np.mean([c["fitness"] for c in feasible if name in c["features"]])) if any(name in c["features"] for c in feasible) else None,
                 "fitness_absent":float(np.mean([c["fitness"] for c in feasible if name not in c["features"]])) if any(name not in c["features"] for c in feasible) else None} for name in columns]
    return {"best":feasible[0],"candidates":candidates,"generations":generations,"pareto":pareto_front(candidates),"survival":survival,
            "optimizer_access":"DEVELOPMENT_ONLY", "validation_method":spec.validation.method,
            # Sprint2 §8 reproducibility (holdout/test içermez).
            "reproducibility": {"random_seed": spec.seed, "population_size": o.population,
                                "generation_count": o.generations, "mutation_rate": o.mutation_rate,
                                "crossover_rate": o.crossover_rate, "fitness_weights": dict(calc.weights),
                                "feature_count_penalty": dict(calc.count_penalty),
                                "use_quant_fitness": use_quant,
                                "feature_universe": columns}}


def _windowed_ic(series, y):
    windows = []
    for indices in np.array_split(np.arange(len(series)), 4):
        segment, target = series.iloc[indices], y[indices]
        v = spearmanr(segment, target).statistic if segment.nunique() > 1 and np.std(target) > 0 else 0
        windows.append(float(v) if np.isfinite(v) else 0)
    return windows


def _regime_metrics(series, y, states, n_states):
    """Per-regime Spearman IC on development data (descriptive, never selective)."""
    out = []
    for k in range(n_states):
        mask = np.asarray(states) == k
        segment, target = series.iloc[mask], y[mask]
        ic = spearmanr(segment, target).statistic if mask.sum() >= 15 and segment.nunique() > 1 and np.std(target) > 0 else 0
        out.append({"regime": int(k), "bars": int(mask.sum()), "share": float(mask.mean()),
                    "ic": float(ic) if np.isfinite(ic) else 0.0})
    return out


def feature_analysis(x, y, seed, missingness=None, dev_states=None, n_states=0):
    # Development data only. No test-based feature ranking or pruning.
    sample = np.linspace(0,len(x)-1,min(5000,len(x)),dtype=int)
    mutual = mutual_info_regression(x.iloc[sample],y[sample],random_state=seed)
    missingness = missingness or {}
    out = []
    for i,c in enumerate(x):
        series = x[c]
        ic = spearmanr(series,y).statistic if series.nunique()>1 and np.std(y)>0 else 0
        windows = _windowed_ic(series, y)
        item = {"feature":c,"ic":float(ic) if np.isfinite(ic) else 0,"rolling_ic":windows,
                "sign_consistency":float(np.mean(np.sign(windows)==np.sign(ic))),"mutual_information":float(mutual[i]),
                "missingness":float(missingness.get(c, 0.0))}
        if dev_states is not None:
            item["regime_metrics"] = _regime_metrics(series, y, dev_states, n_states)
        out.append(item)
    corr = x.corr().fillna(0)
    redundant = [{"a":a,"b":b,"correlation":float(corr.loc[a,b])} for i,a in enumerate(x) for b in list(x)[i+1:] if abs(corr.loc[a,b])>=.9]
    return {"scope":"development_only","features":out,"redundancy_pairs":redundant,"window_count":4}


def execute_research(df, spec:ExperimentSpec, emit, artifact_dir:Path):
    with threadpool_limits(limits=2):
        return _execute(df,spec,emit,artifact_dir)


def _execute(df,spec,emit,artifact_dir):
    emit("stage",{"status":"FEATURE_ENGINEERING","progress":10,"message":"Nedensel teknik ve istatistiksel özellikler"})
    if spec.timeframe != "native":
        if pd.Timedelta(spec.timeframe)<df.index.to_series().diff().median(): raise ValueError("Kaynak periyodundan küçük aralık seçilemez.")
        aggregations = {"open":"first","high":"max","low":"min","close":"last"}
        aggregations.update({column:"last" for column in df.columns if column not in aggregations})
        df = df.resample(spec.timeframe).agg(aggregations).dropna(subset=["open","high","low","close"])
    # Keep pre-start observations for indicator warm-up; trim the end before
    # creating next-open targets so no execution extends beyond the end date.
    if spec.period.end:
        df = df.loc[df.index < pd.Timestamp(spec.period.end, tz="UTC") + pd.Timedelta(days=1)]
    x = feature_frame(df, artifact_dir.parent.parent / 'feature_cache')
    target = (df.open.shift(-2)/df.open.shift(-1)-1).reindex(x.index)
    x,target = x.loc[target.notna()],target.dropna()
    if spec.period.start:
        x = x.loc[x.index >= pd.Timestamp(spec.period.start, tz="UTC")]
        target = target.reindex(x.index)
    all_features = x.copy()
    regime_frame = x[["return_0", "volatility_14", "momentum_30"]].copy()
    # Target conversion is deferred until selected external features have had
    # their release-time gaps removed.
    choices = registry(df)
    selected = spec.features.names or [f["id"] for f in choices if (
        "technical" in spec.features.groups or f["category"] in spec.features.groups or f.get("family") in spec.features.families)]
    if not selected or not set(selected)<=set(x): raise ValueError("Özellik seçimi geçersiz.")
    # Marginal NaN share per selected feature before rows are dropped; stored
    # durably so missingness is measured, not assumed.
    missingness = {c: float(x[c].isna().mean()) for c in selected}
    x = x[selected].dropna()
    masks = rule_masks(all_features.reindex(x.index), spec.signal_rules)
    regime_frame = regime_frame.reindex(x.index)
    target = target.reindex(x.index)
    y = target.to_numpy()
    if not np.isfinite(y).all() or (np.abs(y)>=1).any(): raise ValueError("Hedef getiriler geçersiz veya tek barda %100 üzerinde.")
    b = int(len(x)*(spec.validation.train_ratio+spec.validation.validation_ratio))
    if spec.period.test_start:
        b = int(x.index.searchsorted(pd.Timestamp(spec.period.test_start, tz="UTC")))
    dev_end = b-spec.validation.gap
    if dev_end<160 or len(x)-b<40: raise ValueError("Dönüşümden sonra yeterli eğitim/test barı yok (en az 160/40).")
    x_dev,y_dev = x.iloc[:dev_end].copy(),y[:dev_end].copy()
    annual = 252*24/(df.index.to_series().diff().median().total_seconds()/3600)
    # Descriptive regimes are fitted on development data only, before any
    # candidate is evaluated, so the router's validation reports cannot leak
    # test information. The same fit is reused for test-period reporting below.
    scaler = StandardScaler().fit(regime_frame.iloc[:dev_end])
    z = scaler.transform(regime_frame)
    hmm = GaussianHMM(n_components=spec.regime_states,n_iter=100,covariance_type="diag",random_state=spec.seed).fit(z[:dev_end])
    full_states = causal_probabilities(hmm,z).argmax(axis=1)
    router = RegimeRouter(full_states[:dev_end], spec.regime_states)
    emit("stage",{"status":"TRAINING","progress":15,"message":"Model havuzu ve zaman bölümleri hazırlanıyor"})
    emit("stage",{"status":"OPTIMIZING","progress":20,"message":"Adaylar yalnızca geliştirme verisinde değerlendiriliyor"})
    dev_market = df[["high", "low"]].reindex(x_dev.index)
    optimization = optimize(x_dev,y_dev,spec,annual,emit,dev_market,router,[mask[:dev_end] for mask in masks])
    best = optimization["best"]
    emit("stage",{"status":"VALIDATING","progress":70,"message":"Seçilen aday sabitleniyor"})
    freeze = {"candidate":best,"development_end":x_dev.index[-1].isoformat(),"test_start":x.index[b].isoformat(),"seed":spec.seed}
    (artifact_dir/"frozen_candidate.json").write_text(json.dumps(freeze,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    model = ModelAdapter(best["model"],best["parameters"],spec.seed).fit(x_dev[best["features"]],y_dev)
    model.save(artifact_dir/"model.joblib")
    emit("candidate.frozen",{"id":best["id"],"features":best["features"],"test_access":"CLOSED_UNTIL_FREEZE"})
    emit("stage",{"status":"TESTING","progress":80,"message":"Sabit aday için tek final test ölçümü"})
    forecast = model.predict(x.iloc[b:][best["features"]])
    forecast = apply_rules(forecast, [mask[b:] for mask in masks])
    reality = merged_reality(spec)
    test_bars = (df["high"].reindex(x.index[b:]).to_numpy(), df["low"].reindex(x.index[b:]).to_numpy())
    ret,signal,execution = fx_backtest(forecast,y[b:],reality,x.index[b:],best["threshold_bps"]/10000,high=test_bars[0],low=test_bars[1])
    benchmark,_,_ = fx_backtest(np.ones(len(ret)),y[b:],reality,x.index[b:],high=test_bars[0],low=test_bars[1])
    emit("stage",{"status":"BACKTESTING","progress":88,"message":"Maliyet, kayma ve risk metrikleri"})
    m = score(ret,signal,annual)
    equity = spec.backtest.capital*np.cumprod(1+ret)
    peak = np.maximum.accumulate(np.r_[spec.backtest.capital,equity])[1:]
    baseline = spec.backtest.capital*np.cumprod(1+benchmark)
    timestamps = pd.Series(df.index,index=df.index).shift(-2).reindex(x.index[b:])
    forecast_scale=max(float(np.std(forecast)),1e-12)
    confidence=np.clip(np.abs(forecast)/(3.0*forecast_scale),0.0,1.0)
    curve = [{"timestamp":t.isoformat(),"signal_timestamp":x.index[b+i].isoformat(),"equity":float(equity[i]),"benchmark":float(baseline[i]),
              "drawdown":float(equity[i]/peak[i]-1),"return":float(ret[i]),"signal":int(signal[i]),"prediction_bps":float(forecast[i]*10000),
              "confidence":float(confidence[i]),"close":float(df.loc[x.index[b+i],"close"])} for i,t in enumerate(timestamps)]
    trades=[]; previous=0
    for index,row in enumerate(curve):
        current=int(row["signal"])
        if current==previous: continue
        prior_equity=float(curve[index-1]["equity"]) if index else float(spec.backtest.capital)
        trades.append({"timestamp":row["timestamp"],"signal_timestamp":row["signal_timestamp"],"side":"long" if current>0 else ("short" if current<0 else "flat"),
                      "price":row["close"],"return":row["return"],"pnl":float(row["equity"]-prior_equity),"signal":current,
                      "confidence":row["confidence"],"source":"backtest_curve","record_type":"position_change"})
        previous=current
    # HMM is descriptive here; fitted on development data, never on test.
    emit("stage",{"status":"ANALYZING","progress":94,"message":"Rejimler, özellik kararlılığı ve maliyet duyarlılığı"})
    states = full_states[b:]
    # Feature intelligence is descriptive and computed after the freeze; regime
    # ICs use development rows only, matching feature_analysis scope.
    analysis = feature_analysis(x_dev,y_dev,spec.seed,missingness,full_states[:dev_end],spec.regime_states)
    regimes = []
    for k in range(spec.regime_states):
        mask = states==k
        regimes.append({"id":k,"bars":int(mask.sum()),"share":float(mask.mean()),
                        "mean_net_return_bps":float(ret[mask].mean()*10000) if mask.any() else None})
    sensitivities = []
    for multiplier in [0,1,2,3]:
        multiplied = reality.model_copy(update={"spread_bps":reality.spread_bps*multiplier,"commission_bps":reality.commission_bps*multiplier,"slippage_bps":reality.slippage_bps*multiplier})
        rr,ss,details = fx_backtest(forecast,y[b:],multiplied,x.index[b:],best["threshold_bps"]/10000,high=test_bars[0],low=test_bars[1])
        sensitivities.append({"cost_multiplier":multiplier,**details,**score(rr,ss,annual)})
    # Read-only diagnostics, never fed back into candidate selection.
    warnings = []
    if m["sharpe"]<best["metrics"]["sharpe"]-.5: warnings.append("Test Sharpe, doğrulama Sharpe değerinden en az 0,5 puan düşük.")
    if m["position_changes"]<20: warnings.append("Test döneminde 20'den az pozisyon değişimi var.")
    return {"metrics":m,"validation_metrics":best["metrics"],"validation_test_sharpe_delta":m["sharpe"]-best["metrics"]["sharpe"],
            "curve":curve,"trades":trades,"signal_confidence":{"source":"normalized_prediction_magnitude","calibrated":False,"scale":forecast_scale},"stress_inputs":{"prediction_bps":(forecast*10000).tolist(),"actual_bps":(y[b:]*10000).tolist(),
            "signal_timestamp":[x.index[b+i].isoformat() for i in range(len(ret))],
            "test_high":test_bars[0].tolist(),"test_low":test_bars[1].tolist(),"threshold_bps":best["threshold_bps"]},"execution":{**execution,"signal_to_fill":"signal close -> next open","timezone":reality.timezone,"spread_model":reality.spread_model,"max_leverage":reality.max_leverage,"max_position_fraction":reality.max_position_fraction},"optimization":optimization,"feature_analysis":analysis,"regimes":regimes,"transition":hmm.transmat_.tolist(),
            "selected_features":best["features"],"selected_model":best["model"],"parameters":best["parameters"],"cost_sensitivity":sensitivities,
            "split":{"development":dev_end,"gap":spec.validation.gap,"test":len(x)-b,"development_end":x.index[dev_end-1].isoformat(),"test_start":x.index[b].isoformat(),"test_end":timestamps.iloc[-1].isoformat()},
            "test_policy":{"optimizer_access":False,"candidate_frozen_before_test":True,"test_evaluations":1,"repeated_research_warning":"Klonlar aynı test dönemini tekrar ölçebilir; bu dönem küresel olarak hiç görülmemiş holdout sayılmaz."},
            "warnings":warnings,"feature_count":len(best["features"]),"annual_bars":annual,
            "notes":["GA yalnızca seçili geliştirme özellikleri ve hedeflerini alır.","Walk-forward skorları gap ile ayrılmış kronolojik fold'lardan gelir; son model geliştirme verisinin tamamında yeniden eğitilir.","HMM durumları betimleyicidir; bu sürümde final modele yönlendirme uygulamaz.","Maliyet duyarlılığı test sonrası rapordur; aday seçmez."]}
