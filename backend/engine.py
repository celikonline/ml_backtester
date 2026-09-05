"""Reproducible, causal OHLC research pipeline inspired by the source notebooks."""
from __future__ import annotations

import io
import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
from scipy.special import logsumexp
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits


def read_prices(raw: bytes) -> pd.DataFrame:
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise ValueError("CSV okunamadı. UTF-8 ve virgülle ayrılmış dosya kullanın.") from exc
    df.columns = [str(c).strip().lower() for c in df.columns]
    if len(set(df.columns)) != len(df.columns):
        raise ValueError("Tekrarlanan sütun adları var.")
    for alias in ("date", "datetime", "time"):
        if alias in df and "timestamp" not in df:
            df = df.rename(columns={alias: "timestamp"})
    required = ["timestamp", "open", "high", "low", "close"]
    missing = set(required) - set(df.columns)
    if missing:
        raise ValueError("Eksik sütunlar: " + ", ".join(sorted(missing)))
    # Keep numeric, user-supplied series such as ``macro__us10y`` or
    # ``cross_asset__dxy``.  A matching ``<series>__available_at`` column is
    # the release timestamp used by the platform's point-in-time audit.
    # Text columns are deliberately not carried into the model snapshot.
    optional = [c for c in df.columns if c not in required]
    value_columns = [c for c in optional if not c.endswith("__available_at")]
    availability_columns = [c for c in optional if c.endswith("__available_at")]
    df = df[required + value_columns + availability_columns].copy()
    raw_stamp = df["timestamp"].astype(str)
    aware = bool(raw_stamp.str.contains(r"(Z|[+-]\d{2}:?\d{2})$").any())
    df["timestamp"] = pd.to_datetime(df.timestamp, errors="coerce", utc=True, format="mixed")
    for col in required[1:]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    retained = []
    for col in value_columns:
        numeric = pd.to_numeric(df[col], errors="coerce")
        # A completely non-numeric auxiliary column is descriptive metadata,
        # not a research input. Ignore it instead of silently coercing it.
        if numeric.notna().any():
            df[col] = numeric.replace([np.inf, -np.inf], np.nan)
            retained.append(col)
    value_columns = retained
    for col in availability_columns:
        df[col] = pd.to_datetime(df[col], errors="coerce", utc=True, format="mixed")
    if df.isna().any().any() or not np.isfinite(df[required[1:]].values).all():
        raise ValueError("Geçersiz tarih, eksik veya sonsuz fiyat bulundu. Dosyayı temizleyin.")
    if (df[required[1:]] <= 0).any().any():
        raise ValueError("Tüm fiyatlar sıfırdan büyük olmalı.")
    if (df.high < df[["open", "close", "low"]].max(axis=1)).any() or (df.low > df[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("OHLC tutarsız: High en yüksek, Low en düşük fiyat olmalı.")
    if df.timestamp.duplicated().any():
        raise ValueError("Tekrarlanan zaman damgaları var.")
    if not 400 <= len(df) <= 200_000:
        raise ValueError("CSV 400 ile 200.000 satır arasında olmalı.")
    out = df[required + value_columns + availability_columns].sort_values("timestamp").set_index("timestamp")
    out.attrs["source_timezone"] = "offset-aware" if aware else "naive-assumed-UTC"
    return out


def demo_prices(n=3000):
    rng = np.random.default_rng(42)
    state = (np.arange(n) // 240) % 3
    ret = rng.normal(np.choose(state, [0.00010, -0.00008, 0.00001]), np.choose(state, [0.0011, 0.0018, 0.0007]))
    close = 1.08 * np.exp(np.cumsum(ret))
    op = np.r_[1.08, close[:-1]]
    spread = rng.uniform(0.0001, 0.0010, n)
    idx = pd.date_range("2023-01-02", periods=n * 2, freq="4h", tz="UTC")
    idx = idx[idx.dayofweek < 5][:n]
    out = pd.DataFrame({"open": op, "high": np.maximum(op, close) + spread,
                        "low": np.minimum(op, close) - spread, "close": close}, index=idx.rename("timestamp"))
    out.attrs["source_timezone"] = "offset-aware"
    return out


def preview_value(value):
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    if isinstance(value, (float, np.floating, int, np.integer)):
        return float(value)
    return str(value)


def describe(df, identifier, name, demo=False):
    return {"id": identifier, "name": name, "demo": demo, "rows": len(df),
            "start": df.index[0].isoformat(), "end": df.index[-1].isoformat(),
            "last_close": float(df.close.iloc[-1]), "columns": list(df.columns),
            "preview": [{"timestamp": t.isoformat(), **{k: preview_value(v) for k, v in row.items()}} for t, row in df.tail(8).iterrows()]}


def features(df):
    c = df.close
    r = np.log(c).diff()
    x = pd.DataFrame(index=df.index)
    for lag in [0, 1, 2, 3, 6]:
        x[f"return_{lag}"] = r.shift(lag)
    for w in [6, 14, 30, 50]:
        x[f"momentum_{w}"] = c.pct_change(w)
        x[f"sma_{w}"] = c / c.rolling(w).mean() - 1
        x[f"volatility_{w}"] = r.rolling(w).std()
    x["range"] = (df.high - df.low) / c
    x["body"] = (c - df.open) / df.open
    x["macd"] = (c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()) / c
    delta = c.diff()
    gain, loss = delta.clip(lower=0).rolling(14).mean(), -delta.clip(upper=0).rolling(14).mean()
    x["rsi"] = (gain / (gain + loss).replace(0, np.nan)).fillna(0.5)
    x["hour_sin"] = np.sin(df.index.hour * 2 * np.pi / 24)
    x["hour_cos"] = np.cos(df.index.hour * 2 * np.pi / 24)
    return x.replace([np.inf, -np.inf], np.nan).dropna()


def causal_probabilities(model, x):
    """Forward filtering only; never use Viterbi or future observations."""
    variance = np.diagonal(model.covars_, axis1=1, axis2=2).clip(1e-8)
    emission = -0.5 * (np.log(2 * np.pi * variance).sum(axis=1)[None, :] +
                       (((x[:, None, :] - model.means_[None, :, :]) ** 2) / variance).sum(axis=2))
    transition = np.log(model.transmat_.clip(1e-300))
    alpha = np.log(model.startprob_.clip(1e-300))
    probs = []
    for i, obs in enumerate(emission):
        if i:
            alpha = logsumexp(alpha[:, None] + transition, axis=0)
        alpha = alpha + obs
        alpha -= logsumexp(alpha)
        probs.append(np.exp(alpha))
    return np.asarray(probs)


def backtest(prediction, actual, cost, threshold=0):
    signal = np.where(prediction > threshold, 1, np.where(prediction < -threshold, -1, 0))
    turnover = np.abs(np.diff(signal, prepend=0)).astype(float)
    # Close the final position, charging the same one-way transaction cost.
    turnover[-1] += abs(signal[-1])
    returns = signal * actual - turnover * cost
    return returns, signal


def fx_backtest(prediction, actual, reality, timestamps, threshold=0, high=None, low=None):
    """Deterministic FX execution: signal-close, next-open fill, then rollover.

    ``spread_model="ohlc_range"`` scales the quoted spread per bar by that bar's
    high-low range relative to the window median (cost normalization only; it
    never touches signals). Without bar data it falls back to the fixed spread.
    """
    config = reality.model_dump() if hasattr(reality, "model_dump") else reality
    prediction, actual = np.asarray(prediction, dtype=float), np.asarray(actual, dtype=float)
    if len(prediction) != len(actual):
        raise ValueError("Tahmin ve gerçekleşen uzunluğu uyuşmuyor.")
    spread_bps = config.get("spread_bps", 0)
    fallback = False
    if config.get("spread_model", "fixed") == "ohlc_range" and high is not None and low is not None:
        high, low = np.asarray(high, dtype=float), np.asarray(low, dtype=float)
        if len(high) != len(actual) or len(low) != len(actual):
            raise ValueError("Bar verisi uzunluğu uyuşmuyor.")
        width = np.maximum(high - low, 0)
        median = float(np.median(width)) or 1.0
        spread_vec = np.asarray(spread_bps, dtype=float) * width / median
    else:
        fallback = config.get("spread_model", "fixed") == "ohlc_range"
        spread_vec = np.full(len(actual), spread_bps, dtype=float)
    one_way = (spread_vec / 2 + config.get("commission_bps", 0) + config.get("slippage_bps", 0)) / 10000
    signal = np.where(prediction > threshold, 1, np.where(prediction < -threshold, -1, 0))
    turnover = np.abs(np.diff(signal, prepend=0)).astype(float)
    # Close the final position, charging the same one-way transaction cost.
    turnover[-1] += abs(signal[-1])
    base = signal * actual - turnover * one_way
    index = pd.DatetimeIndex(timestamps)
    elapsed_days = np.r_[0., np.maximum(0., np.diff(index.asi8) / 86_400_000_000_000)]
    flat = config.get("rollover_bps_per_day", 0)
    long_bps = config.get("rollover_long_bps_per_day", flat)
    short_bps = config.get("rollover_short_bps_per_day", flat)
    long_bps = flat if long_bps is None else long_bps
    short_bps = flat if short_bps is None else short_bps
    rate = np.where(signal > 0, long_bps, np.where(signal < 0, short_bps, 0)) / 10000
    if config.get("triple_wednesday_rollover", False):
        rate = np.where(index.dayofweek == 2, rate * 3, rate)
    financing = np.abs(signal) * elapsed_days * rate
    ret = base - financing
    return ret, signal, {"one_way_cost_bps": float(one_way.mean() * 10000),
                         "avg_spread_bps": float(spread_vec.mean()),
                         "spread_model": config.get("spread_model", "fixed"),
                         "spread_fallback": bool(fallback),
                         "financing_bps": float(financing.sum() * 10000)}


def audit_calendar(df):
    """Classify bar gaps: weekend sessions vs missing-source bars. Audit only, never rejects."""
    index = pd.DatetimeIndex(df.index).tz_convert("UTC")
    deltas = index.to_series().diff().dropna()
    median = float(deltas.median().total_seconds()) if len(deltas) else 0.0
    gaps = deltas[deltas > deltas.median() * 1.5] if len(deltas) else deltas[:0]
    weekend_gaps = sum(1 for ts in gaps.index if ts.dayofweek == 0)
    weekend_bars = int(((index.dayofweek == 5) | (index.dayofweek == 6)).sum())
    return {"source_timezone": df.attrs.get("source_timezone", "unknown"),
            "median_bar_seconds": median, "gap_bars": int(len(gaps)),
            "weekend_gaps": int(weekend_gaps), "midweek_gaps": int(len(gaps) - weekend_gaps),
            "weekend_bars": weekend_bars}


def metrics(ret, signal, annual):
    eq = np.r_[1.0, np.cumprod(1 + ret)]
    dd = eq / np.maximum.accumulate(eq) - 1
    std = np.std(ret, ddof=1) if len(ret) > 1 else 0
    return {"return": float(eq[-1] - 1), "sharpe": float(np.mean(ret) / std * np.sqrt(annual)) if std > 1e-12 else 0.0,
            "max_drawdown": float(dd.min()), "win_rate": float((ret[signal != 0] > 0).mean()) if (signal != 0).any() else 0.0,
            "active_bars": int((signal != 0).sum()), "position_changes": int((np.diff(signal, prepend=0) != 0).sum())}


def run_experiment(df, config, progress):
    with threadpool_limits(limits=2):
        return _run_experiment(df, config, progress)


def _run_experiment(df, config, progress):
    progress(8, "Veri ve teknik özellikler hazırlanıyor")
    interval = config["interval"]
    if interval != "native":
        native_delta = df.index.to_series().diff().median()
        if pd.Timedelta(interval) < native_delta:
            raise ValueError("Seçilen periyot kaynak veriden daha küçük olamaz.")
        df = df.resample(interval, closed="left", label="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    if len(df) < 400:
        raise ValueError("Periyot dönüşümünden sonra en az 400 bar gerekli.")
    x = features(df)
    # Signal after bar t closes, execute at t+1 open, exit/rebalance at t+2 open.
    target = (df.open.shift(-2) / df.open.shift(-1) - 1).reindex(x.index)
    valid = target.notna()
    x, y = x.loc[valid], target.loc[valid].to_numpy()
    if not np.isfinite(y).all() or (np.abs(y) >= 1).any():
        raise ValueError("Açılış fiyatlarında tek barda %100 veya üzeri değişim var. EUR/USD verisini kontrol edin.")
    n = len(x)
    a, b = int(n * config["train_ratio"]), int(n * (config["train_ratio"] + 0.15))
    tr, va, te = slice(0, a - 2), slice(a, b - 2), slice(b, n)
    if min(a - 2, b - a - 2, n - b) < 40:
        raise ValueError("Eğitim, doğrulama ve test bölümleri için yeterli bar yok.")
    groups = [
        ("Trend uzmanı", "Ridge", [c for c in x if c.startswith(("sma", "momentum")) or c == "macd"], make_pipeline(StandardScaler(), Ridge(alpha=10))),
        ("Momentum uzmanı", "Random Forest", [c for c in x if c.startswith("return") or c in ["rsi", "body", "hour_sin", "hour_cos"]], RandomForestRegressor(n_estimators=90, max_depth=5, min_samples_leaf=20, n_jobs=2, random_state=42)),
        ("Volatilite uzmanı", "Hist. Gradient Boosting", list(x.columns), HistGradientBoostingRegressor(max_iter=100, max_leaf_nodes=12, l2_regularization=5, early_stopping=False, random_state=42)),
    ]
    predictions = []
    for i, (name, family, cols, model) in enumerate(groups):
        progress(18 + i * 16, f"{name} eğitiliyor · {family}")
        # Basis points improve numerical conditioning for tree estimators.
        model.fit(x.iloc[tr][cols], y[tr] * 10000)
        predictions.append(model.predict(x[cols]) / 10000)
    pred = np.asarray(predictions).T
    progress(68, "Gaussian HMM eğitiliyor · nedensel rejim çıkarımı")
    regime_cols = ["return_0", "volatility_14", "momentum_30"]
    scaler = StandardScaler().fit(x.iloc[tr][regime_cols])
    z = scaler.transform(x[regime_cols])
    hmm = GaussianHMM(n_components=config["states"], covariance_type="diag", n_iter=120, random_state=42, min_covar=0.01)
    hmm.fit(z[tr])
    probability = causal_probabilities(hmm, z)
    state = probability.argmax(axis=1)
    progress(82, "Doğrulama verisiyle uzman ağırlıkları ve eşik seçiliyor")
    weights = []
    for k in range(config["states"]):
        mask = state[va] == k
        # Fall back to the entire validation set when a regime has too few bars.
        errors = (pred[va] - y[va, None]) ** 2
        mse = errors[mask].mean(axis=0) if mask.sum() >= 15 else errors.mean(axis=0)
        w = 1 / np.maximum(mse, 1e-12)
        weights.append(w / w.sum())
    weights = np.asarray(weights)
    ensemble = (pred * weights[state]).sum(axis=1)
    cost = config["cost_bps"] / 10000
    delta_hours = df.index.to_series().diff().median().total_seconds() / 3600
    annual = 252 * 24 / delta_hours
    thresholds = [0, 0.000025, 0.00005, 0.0001, 0.0002]
    best = max(thresholds, key=lambda t: metrics(*backtest(ensemble[va], y[va], cost, t), annual)["sharpe"])
    progress(92, "Ayrılmış test döneminde maliyetli backtest hesaplanıyor")
    strategies = [("HMM Ensemble", ensemble[te], best), ("Eşit ağırlık", pred[te].mean(axis=1), best)]
    strategies += [(g[0], pred[te, i], best) for i, g in enumerate(groups)]
    results = []
    for name, forecast, threshold in strategies:
        r, s = backtest(forecast, y[te], cost, threshold)
        results.append({"name": name, **metrics(r, s, annual), "returns": r, "signal": s})
    bh_r, bh_s = backtest(np.ones(len(y[te])), y[te], cost)
    results.append({"name": "Al & tut", **metrics(bh_r, bh_s, annual), "returns": bh_r, "signal": bh_s})
    main = results[0]
    eq = config["capital"] * np.cumprod(1 + main["returns"])
    benchmark = config["capital"] * np.cumprod(1 + bh_r)
    peak = np.maximum.accumulate(np.r_[config["capital"], eq])[1:]
    dates = x.index[te]
    # Report realization timestamp (t+2 open), not the earlier signal timestamp.
    realized_dates = pd.Series(df.index, index=df.index).shift(-2).reindex(dates)
    curve = [{"timestamp": realized_dates.iloc[i].isoformat(), "signal_timestamp": t.isoformat(), "equity": float(eq[i]), "benchmark": float(benchmark[i]),
              "drawdown": float((eq[i] / peak[i] - 1) * 100), "state": int(state[te][i]),
              "close": float(df.loc[t, "close"]), "prediction_bps": float(ensemble[te][i] * 10000),
              "return": float(main["returns"][i]), "signal": int(main["signal"][i])} for i, t in enumerate(dates)]
    regimes = [{"id": k, "share": float((state[te] == k).mean()), "bars": int((state[te] == k).sum()),
                "weights": weights[k].tolist(), "persistence": float(hmm.transmat_[k, k]),
                "mean_return_bps": float(y[te][state[te] == k].mean() * 10000) if (state[te] == k).any() else 0} for k in range(config["states"])]
    return {"metrics": {k: v for k, v in main.items() if k not in ["returns", "signal", "name"]},
            "comparison": [{k: v for k, v in r.items() if k not in ["returns", "signal"]} for r in results],
            "curve": curve, "regimes": regimes, "transition": hmm.transmat_.tolist(),
            "experts": [{"name": g[0], "family": g[1], "features": g[2]} for g in groups],
            "split": {"train": a - 2, "validation": b - a - 2, "test": n - b, "purged": 4,
                      "train_end": x.index[a-3].isoformat(), "validation_start": x.index[a].isoformat(),
                      "test_start": dates[0].isoformat(), "test_end": realized_dates.iloc[-1].isoformat()},
            "threshold_bps": best * 10000, "feature_count": len(x.columns), "annual_bars": annual,
            "hmm_converged": bool(len(hmm.monitor_.history) > 1 and 0 <= hmm.monitor_.history[-1] - hmm.monitor_.history[-2] < hmm.tol),
            "notes": ["Bu akış notebookların OHLC tabanlı, üç uzmanlı uyarlamasıdır; TFT, makro uzman havuzları ve MAIN_14 sonuçlarını yeniden üretmez.",
                      "Sinyal bar kapanışında üretilir; sonraki açılışta uygulanır. Hedef bir açılıştan sonraki açılışa getiridir.",
                      "Ölçekleyici ve HMM yalnızca eğitimde öğrenir. Ağırlık ve eşik doğrulamada seçilir. Test kronolojiktir; sınırlarda ikişer bar ayrılır.",
                      "Sharpe: sıfır risksiz oran, 252 işlem günü ve medyan bar aralığı varsayımı. Tek yön maliyeti giriş, yön değişimi ve son çıkışta uygulanır.",
                      "HMM durum numaraları ekonomik etiket değildir; çıkarım yalnızca o ana kadarki gözlemleri kullanır."]}
