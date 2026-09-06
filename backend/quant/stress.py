"""Faz 5: Slippage / Latency / Cost matrix / Systematic stress (spec bolum 21-24).

Ayni backtest motoru uzerinden calisir; motor kopyalanmaz.
Burada motor: backend.engine.fx_backtest veya verilen callable.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_SLIPPAGE_BPS = [0, 1, 2, 5, 10, 20]
DEFAULT_LATENCY_BARS = [0, 1, 2, 3, 5]
SYSTEMATIC_SCENARIOS = ["Normal", "High Transaction Cost", "High Slippage",
                        "1-Bar Delay", "3-Bar Delay", "High Volatility Period",
                        "Low Liquidity Proxy"]


def _run(predictions, actuals, timestamps, reality: dict, backtest_fn,
         high=None, low=None, threshold: float = 0.0) -> dict:
    ret, signal, _ = backtest_fn(predictions, actuals, reality, timestamps,
                                 threshold, high=high, low=low)
    ret = np.asarray(ret, dtype=float)
    eq = np.cumprod(1 + ret)
    dd = eq / np.maximum.accumulate(eq) - 1
    std = float(np.std(ret, ddof=1)) if len(ret) > 1 else 0.0
    return {"total_return": float(eq[-1] - 1) if len(eq) else 0.0,
            "sharpe": float(np.mean(ret) / std * np.sqrt(252)) if std > 1e-12 else 0.0,
            "max_drawdown": float(dd.min()) if len(dd) else 0.0,
            "trade_count": int((np.diff(signal, prepend=0) != 0).sum())}


def slippage_stress(predictions, actuals, timestamps, base_reality: dict,
                    backtest_fn, levels_bps=None, high=None, low=None,
                    threshold: float = 0.0) -> pd.DataFrame:
    """Her slippage seviyesinde ayni motorla backtest."""
    levels_bps = list(levels_bps) if levels_bps is not None else list(DEFAULT_SLIPPAGE_BPS)
    rows = []
    for bps in levels_bps:
        reality = {**base_reality, "slippage_bps": float(bps)}
        m = _run(predictions, actuals, timestamps, reality, backtest_fn, high, low, threshold)
        rows.append({"slippage_bps": bps, **m})
    return pd.DataFrame(rows)


def latency_stress(signals_or_predictions, actuals, timestamps, base_reality: dict,
                   backtest_fn, latency_bars=None, high=None, low=None,
                   threshold: float = 0.0) -> pd.DataFrame:
    """executed_signal = signal.shift(latency_bars) yaklasimi: tahmini kaydirir."""
    latency_bars = list(latency_bars) if latency_bars is not None else list(DEFAULT_LATENCY_BARS)
    preds = np.asarray(signals_or_predictions, dtype=float)
    rows = []
    for lag in latency_bars:
        shifted = pd.Series(preds).shift(int(lag)).fillna(0.0).to_numpy()
        m = _run(shifted, actuals, timestamps, dict(base_reality), backtest_fn, high, low, threshold)
        rows.append({"latency_bars": lag, **m})
    return pd.DataFrame(rows)


def cost_stress_matrix(predictions, actuals, timestamps, base_reality: dict,
                       backtest_fn, commissions=None, slippages=None,
                       high=None, low=None, threshold: float = 0.0) -> dict:
    """Commission x Slippage matrisinde Sharpe (+ return/drawdown artifact)."""
    commissions = list(commissions) if commissions is not None else [0, 2, 5, 10]
    slippages = list(slippages) if slippages is not None else [0, 2, 5, 10]
    sharpe = pd.DataFrame(index=commissions, columns=slippages, dtype=float)
    detail = {}
    for c in commissions:
        for s in slippages:
            reality = {**base_reality, "commission_bps": float(c), "slippage_bps": float(s)}
            m = _run(predictions, actuals, timestamps, reality, backtest_fn, high, low, threshold)
            sharpe.loc[c, s] = m["sharpe"]
            detail[f"{c}x{s}"] = m
    return {"sharpe_matrix": sharpe, "details": detail,
            "commissions": commissions, "slippages": slippages}


def robustness_score(base_sharpe: float, worst_stress_sharpe: float,
                     worst_drawdown: float) -> float:
    """Sprint 4 madde 7: raporlama skoru, GA fitness'a baglanmaz.

    robustness = 0.40*norm(base) + 0.30*norm(worst) - 0.30*norm_dd
    norm(x): buyuk Sharpe buyuklugune gore olceklenir; norm_dd = min(1, |dd|).
    """
    scale = max(abs(base_sharpe), abs(worst_stress_sharpe), 1e-9)
    norm_dd = min(1.0, abs(worst_drawdown))
    return float(0.40 * (base_sharpe / scale) + 0.30 * (worst_stress_sharpe / scale)
                 - 0.30 * norm_dd)


def experiment_stress_report(predictions, actuals, timestamps, base_reality: dict,
                             backtest_fn, high=None, low=None,
                             threshold: float = 0.0) -> dict:
    """Deney test donemi icin tek cagrida butun stres raporu.

    Ayni motor (backtest_fn) farkli parametrelerle cagrilir; motor kopyalanmaz.
    Donus JSON-serializable'dir ve stress_test_report.json artifact'idir.
    """
    preds = np.asarray(predictions, dtype=float)
    slip = slippage_stress(preds, actuals, timestamps, dict(base_reality), backtest_fn, high=high, low=low)
    lat = latency_stress(preds, actuals, timestamps, dict(base_reality), backtest_fn, high=high, low=low)
    scen = systematic_stress(preds, actuals, timestamps, dict(base_reality), backtest_fn, high=high, low=low)
    matrix = cost_stress_matrix(preds, actuals, timestamps, dict(base_reality), backtest_fn, high=high, low=low)
    scenarios = scen.to_dict("records")
    base = next((r for r in scenarios if r["scenario"] == "Normal"), scenarios[0] if scenarios else {})
    worst = min(scenarios, key=lambda r: r["sharpe"]) if scenarios else {}
    worst_dd = min([r["max_drawdown"] for r in scenarios] + [0.0])
    score = robustness_score(float(base.get("sharpe", 0.0)),
                             float(worst.get("sharpe", 0.0)), float(worst_dd))
    return {"base": base, "worst": worst, "robustness_score": score,
            "slippage_matrix": slip.to_dict("records"),
            "latency_curve": lat.to_dict("records"),
            "scenarios": scenarios,
            "cost_matrix": {"sharpe": matrix["sharpe_matrix"].to_dict(),
                            "details": matrix["details"],
                            "commissions": matrix["commissions"],
                            "slippages": matrix["slippages"]},
            "report_only": True}


def systematic_stress(predictions, actuals, timestamps, base_reality: dict,
                      backtest_fn, high=None, low=None,
                      scenarios: list[str] | None = None,
                      volatility: np.ndarray | None = None,
                      threshold: float = 0.0) -> pd.DataFrame:
    """Ayni motorla 7 senaryo (spec bolum 24). Volatilite/Likidite proxy'leri
    maliyet carpaniyla modellenir (yeni veri kaynagi yok)."""
    scenarios = list(scenarios) if scenarios else list(SYSTEMATIC_SCENARIOS)
    preds = np.asarray(predictions, dtype=float)
    rows = []
    for name in scenarios:
        reality = dict(base_reality)
        run_preds = preds
        if name == "High Transaction Cost":
            reality["commission_bps"] = float(reality.get("commission_bps", 0)) + 5
        elif name == "High Slippage":
            reality["slippage_bps"] = float(reality.get("slippage_bps", 0)) + 10
        elif name == "1-Bar Delay":
            run_preds = pd.Series(preds).shift(1).fillna(0.0).to_numpy()
        elif name == "3-Bar Delay":
            run_preds = pd.Series(preds).shift(3).fillna(0.0).to_numpy()
        elif name == "High Volatility Period" and volatility is not None:
            vol = np.asarray(volatility, dtype=float)
            mask = vol >= np.quantile(vol, 0.8)
            if mask.sum() >= 5:
                m = _run(run_preds[mask], np.asarray(actuals)[mask],
                         np.asarray(timestamps)[mask], reality, backtest_fn,
                         high=np.asarray(high)[mask] if high is not None else None,
                         low=np.asarray(low)[mask] if low is not None else None)
                rows.append({"scenario": name, **m})
                continue
        elif name == "Low Liquidity Proxy":
            reality["slippage_bps"] = float(reality.get("slippage_bps", 0)) * 3 + 2
        m = _run(run_preds, actuals, timestamps, reality, backtest_fn, high, low)
        rows.append({"scenario": name, **m})
    return pd.DataFrame(rows)
