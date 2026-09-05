"""Development-only optimization followed by a single frozen-candidate test."""
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
from scipy.stats import spearmanr
from sklearn.feature_selection import mutual_info_regression
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from backend.engine import features, backtest, fx_backtest, metrics, causal_probabilities
from .models import MODEL_REGISTRY, ModelAdapter
from .schema import ExperimentSpec
from .families import family_for_column


def feature_frame(df):
    x = features(df)
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
    def group(name):
        if name.startswith(("quantile", "rolling", "signal_noise", "tanh")): return "statistical"
        if name.startswith("volatility") or name == "range": return "volatility"
        if name.startswith("sma") or name == "macd": return "trend"
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
    m.update(sortino=float(np.mean(ret) / downside * np.sqrt(annual)) if downside > 1e-12 else 0.0,
             volatility=float(np.std(ret) * np.sqrt(annual)), exposure=float(np.mean(signal != 0)),
             turnover=float(np.abs(np.diff(signal, prepend=0)).sum() + abs(signal[-1])))
    return m


def splits(n, method, train_ratio, folds, gap):
    if method == "holdout":
        a = int(n * train_ratio / (train_ratio + .15))
        return [(np.arange(a-gap), np.arange(a,n))]
    return list(TimeSeriesSplit(n_splits=folds, gap=gap).split(np.arange(n)))


def pareto_front(candidates):
    feasible = [c for c in candidates if c["feasible"]]
    return [c for c in feasible if not any(
        d["metrics"]["sharpe"] >= c["metrics"]["sharpe"] and d["metrics"]["return"] >= c["metrics"]["return"] and d["metrics"]["max_drawdown"] >= c["metrics"]["max_drawdown"]
        and any(d["metrics"][k] > c["metrics"][k] for k in ["sharpe","return","max_drawdown"])
        for d in feasible)]


def optimize(x_dev, y_dev, spec, annual, emit):
    """This function receives no holdout/test data, index or test callback."""
    o = spec.optimization
    rng = np.random.default_rng(spec.seed)
    columns = list(x_dev.columns)
    min_count, max_count = min(o.min_features,len(columns)), min(o.max_features,len(columns))
    partitions = splits(len(x_dev), spec.validation.method, spec.validation.train_ratio, spec.validation.folds, spec.validation.gap)
    cost = (spec.backtest.cost_bps + spec.backtest.slippage_bps) / 10000
    cache, generations = {}, []

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

    def evaluate(genome):
        key = hashlib.sha256(json.dumps(genome,sort_keys=True).encode()).hexdigest()[:16]
        if key in cache: return cache[key]
        chosen = [c for c,on in zip(columns,genome["mask"]) if on]
        params = MODEL_REGISTRY[genome["model"]]["parameters"][genome["param"]]
        returns, signals, fold_metrics = [], [], []
        for train, val in partitions:
            emit("optimization.candidate.started", {"evaluated": len(cache), "candidate_id": key})
            model = ModelAdapter(genome["model"], params, spec.seed).fit(x_dev.iloc[train][chosen],y_dev[train])
            pred = model.predict(x_dev.iloc[val][chosen])
            ret, sig = backtest(pred,y_dev[val],cost,genome["threshold"]/10000)
            returns.extend(ret); signals.extend(sig)
            fold_metrics.append({"train_end": x_dev.index[train[-1]].isoformat(), "validation_start": x_dev.index[val[0]].isoformat(),
                                 "validation_end": x_dev.index[val[-1]].isoformat(), "gap_bars": int(val[0]-train[-1]-1), **score(ret,sig,annual)})
        m = score(np.array(returns),np.array(signals),annual)
        feasible = abs(m["max_drawdown"]) <= o.max_drawdown
        fitness = m[o.objective] if feasible else -1000000 - abs(m["max_drawdown"])
        c = {"id": key, "genome": genome, "features": chosen, "model": genome["model"], "parameters": params,
             "threshold_bps": genome["threshold"], "metrics": m, "fitness": fitness, "feasible": feasible, "folds": fold_metrics}
        cache[key] = c
        return c

    if o.algorithm == "none":
        genomes = [{"mask": [True]*len(columns), "model": name, "param": 1, "threshold": 0.0} for name in spec.models]
        population = [evaluate(g) for g in genomes]
    else:
        population = [random_genome() for _ in range(o.population)]
        # Ensure every requested model is represented in the initial population.
        for i, model_id in enumerate(spec.models[:len(population)]): population[i]["model"] = model_id
        for generation in range(o.generations):
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
                parents = rng.choice(len(ranked),size=(2,3))
                p1,p2 = [max((ranked[int(i)] for i in ids),key=lambda c:c["fitness"])["genome"] for ids in parents]
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
            population = new
        population = list(cache.values())
    candidates = sorted(cache.values(),key=lambda c:(c["fitness"],c["id"]),reverse=True)
    feasible = [c for c in candidates if c["feasible"]]
    if not feasible: raise ValueError("Doğrulama düşüş sınırını sağlayan aday yok. Test açılmadı.")
    top = feasible[:max(1,int(np.ceil(len(feasible)*.25)))]
    survival = [{"feature":name,"selection_frequency":float(np.mean([name in c["features"] for c in candidates])),
                 "top_survival":float(np.mean([name in c["features"] for c in top])),
                 "fitness_present":float(np.mean([c["fitness"] for c in feasible if name in c["features"]])) if any(name in c["features"] for c in feasible) else None,
                 "fitness_absent":float(np.mean([c["fitness"] for c in feasible if name not in c["features"]])) if any(name not in c["features"] for c in feasible) else None} for name in columns]
    return {"best":feasible[0],"candidates":candidates,"generations":generations,"pareto":pareto_front(candidates),"survival":survival,
            "optimizer_access":"DEVELOPMENT_ONLY", "validation_method":spec.validation.method}


def feature_analysis(x, y, seed):
    # Development data only. No test-based feature ranking or pruning.
    sample = np.linspace(0,len(x)-1,min(5000,len(x)),dtype=int)
    mutual = mutual_info_regression(x.iloc[sample],y[sample],random_state=seed)
    out = []
    for i,c in enumerate(x):
        series = x[c]
        ic = spearmanr(series,y).statistic if series.nunique()>1 and np.std(y)>0 else 0
        windows = []
        for indices in np.array_split(np.arange(len(x)),4):
            v = spearmanr(series.iloc[indices],y[indices]).statistic if series.iloc[indices].nunique()>1 and np.std(y[indices])>0 else 0
            windows.append(float(v) if np.isfinite(v) else 0)
        out.append({"feature":c,"ic":float(ic) if np.isfinite(ic) else 0,"rolling_ic":windows,
                    "sign_consistency":float(np.mean(np.sign(windows)==np.sign(ic))),"mutual_information":float(mutual[i])})
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
    x = feature_frame(df)
    target = (df.open.shift(-2)/df.open.shift(-1)-1).reindex(x.index)
    x,target = x.loc[target.notna()],target.dropna()
    regime_frame = x[["return_0", "volatility_14", "momentum_30"]].copy()
    # Target conversion is deferred until selected external features have had
    # their release-time gaps removed.
    choices = registry(df)
    selected = spec.features.names or [f["id"] for f in choices if (
        "technical" in spec.features.groups or f["category"] in spec.features.groups or f.get("family") in spec.features.families)]
    if not selected or not set(selected)<=set(x): raise ValueError("Özellik seçimi geçersiz.")
    x = x[selected].dropna()
    regime_frame = regime_frame.reindex(x.index)
    target = target.reindex(x.index)
    y = target.to_numpy()
    if not np.isfinite(y).all() or (np.abs(y)>=1).any(): raise ValueError("Hedef getiriler geçersiz veya tek barda %100 üzerinde.")
    b = int(len(x)*(spec.validation.train_ratio+.15))
    dev_end = b-spec.validation.gap
    if dev_end<160 or len(x)-b<40: raise ValueError("Dönüşümden sonra yeterli eğitim/test barı yok (en az 160/40).")
    x_dev,y_dev = x.iloc[:dev_end].copy(),y[:dev_end].copy()
    annual = 252*24/(df.index.to_series().diff().median().total_seconds()/3600)
    emit("stage",{"status":"TRAINING","progress":15,"message":"Model havuzu ve zaman bölümleri hazırlanıyor"})
    emit("stage",{"status":"OPTIMIZING","progress":20,"message":"Adaylar yalnızca geliştirme verisinde değerlendiriliyor"})
    optimization = optimize(x_dev,y_dev,spec,annual,emit)
    best = optimization["best"]
    emit("stage",{"status":"VALIDATING","progress":70,"message":"Seçilen aday sabitleniyor"})
    freeze = {"candidate":best,"development_end":x_dev.index[-1].isoformat(),"test_start":x.index[b].isoformat(),"seed":spec.seed}
    (artifact_dir/"frozen_candidate.json").write_text(json.dumps(freeze,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    model = ModelAdapter(best["model"],best["parameters"],spec.seed).fit(x_dev[best["features"]],y_dev)
    model.save(artifact_dir/"model.joblib")
    analysis = feature_analysis(x_dev,y_dev,spec.seed)
    emit("candidate.frozen",{"id":best["id"],"features":best["features"],"test_access":"CLOSED_UNTIL_FREEZE"})
    emit("stage",{"status":"TESTING","progress":80,"message":"Sabit aday için tek final test ölçümü"})
    forecast = model.predict(x.iloc[b:][best["features"]])
    reality = spec.backtest.reality.model_copy(update={"slippage_bps": spec.backtest.slippage_bps + spec.backtest.reality.slippage_bps,
                                                        "spread_bps": spec.backtest.spread_bps + 2 * spec.backtest.cost_bps})
    ret,signal,execution = fx_backtest(forecast,y[b:],reality,x.index[b:],best["threshold_bps"]/10000)
    benchmark,_,_ = fx_backtest(np.ones(len(ret)),y[b:],reality,x.index[b:])
    emit("stage",{"status":"BACKTESTING","progress":88,"message":"Maliyet, kayma ve risk metrikleri"})
    m = score(ret,signal,annual)
    equity = spec.backtest.capital*np.cumprod(1+ret)
    peak = np.maximum.accumulate(np.r_[spec.backtest.capital,equity])[1:]
    baseline = spec.backtest.capital*np.cumprod(1+benchmark)
    timestamps = pd.Series(df.index,index=df.index).shift(-2).reindex(x.index[b:])
    curve = [{"timestamp":t.isoformat(),"signal_timestamp":x.index[b+i].isoformat(),"equity":float(equity[i]),"benchmark":float(baseline[i]),
              "drawdown":float(equity[i]/peak[i]-1),"return":float(ret[i]),"signal":int(signal[i]),"prediction_bps":float(forecast[i]*10000)} for i,t in enumerate(timestamps)]
    # HMM is descriptive here; fitted on development data, never on test.
    emit("stage",{"status":"ANALYZING","progress":94,"message":"Rejimler, özellik kararlılığı ve maliyet duyarlılığı"})
    scaler = StandardScaler().fit(regime_frame.iloc[:dev_end])
    z = scaler.transform(regime_frame)
    hmm = GaussianHMM(n_components=spec.regime_states,n_iter=100,covariance_type="diag",random_state=spec.seed).fit(z[:dev_end])
    states = causal_probabilities(hmm,z).argmax(axis=1)[b:]
    regimes = []
    for k in range(spec.regime_states):
        mask = states==k
        regimes.append({"id":k,"bars":int(mask.sum()),"share":float(mask.mean()),
                        "mean_net_return_bps":float(ret[mask].mean()*10000) if mask.any() else None})
    sensitivities = []
    for multiplier in [0,1,2,3]:
        multiplied = reality.model_copy(update={"spread_bps":reality.spread_bps*multiplier,"commission_bps":reality.commission_bps*multiplier,"slippage_bps":reality.slippage_bps*multiplier})
        rr,ss,details = fx_backtest(forecast,y[b:],multiplied,x.index[b:],best["threshold_bps"]/10000)
        sensitivities.append({"cost_multiplier":multiplier,**details,**score(rr,ss,annual)})
    # Read-only diagnostics, never fed back into candidate selection.
    warnings = []
    if m["sharpe"]<best["metrics"]["sharpe"]-.5: warnings.append("Test Sharpe, doğrulama Sharpe değerinden en az 0,5 puan düşük.")
    if m["position_changes"]<20: warnings.append("Test döneminde 20'den az pozisyon değişimi var.")
    return {"metrics":m,"validation_metrics":best["metrics"],"validation_test_sharpe_delta":m["sharpe"]-best["metrics"]["sharpe"],
            "curve":curve,"execution":{**execution,"signal_to_fill":"signal close -> next open","timezone":reality.timezone,"max_leverage":reality.max_leverage,"max_position_fraction":reality.max_position_fraction},"optimization":optimization,"feature_analysis":analysis,"regimes":regimes,"transition":hmm.transmat_.tolist(),
            "selected_features":best["features"],"selected_model":best["model"],"parameters":best["parameters"],"cost_sensitivity":sensitivities,
            "split":{"development":dev_end,"gap":spec.validation.gap,"test":len(x)-b,"development_end":x.index[dev_end-1].isoformat(),"test_start":x.index[b].isoformat(),"test_end":timestamps.iloc[-1].isoformat()},
            "test_policy":{"optimizer_access":False,"candidate_frozen_before_test":True,"test_evaluations":1,"repeated_research_warning":"Klonlar aynı test dönemini tekrar ölçebilir; bu dönem küresel olarak hiç görülmemiş holdout sayılmaz."},
            "warnings":warnings,"feature_count":len(best["features"]),"annual_bars":annual,
            "notes":["GA yalnızca seçili geliştirme özellikleri ve hedeflerini alır.","Walk-forward skorları gap ile ayrılmış kronolojik fold'lardan gelir; son model geliştirme verisinin tamamında yeniden eğitilir.","HMM durumları betimleyicidir; bu sürümde final modele yönlendirme uygulamaz.","Maliyet duyarlılığı test sonrası rapordur; aday seçmez."]}
