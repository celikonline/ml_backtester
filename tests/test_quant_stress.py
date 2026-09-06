import numpy as np
import pandas as pd

from backend.quant.stress import (
    cost_stress_matrix,
    latency_stress,
    slippage_stress,
    systematic_stress,
)
from backend.engine import fx_backtest


def _data(n=200):
    rng = np.random.default_rng(0)
    preds = rng.normal(size=n)
    actuals = rng.normal(scale=0.001, size=n)
    stamps = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    reality = {"spread_bps": 0.5, "commission_bps": 0.0, "slippage_bps": 0.0}
    return preds, actuals, stamps, reality


def test_higher_cost_reduces_or_preserves_return():
    preds, actuals, stamps, reality = _data()
    df = slippage_stress(preds, actuals, stamps, reality, fx_backtest, [0, 20])
    assert df.iloc[0]["total_return"] >= df.iloc[1]["total_return"] - 1e-12
    assert list(df.columns) == ["slippage_bps", "total_return", "sharpe",
                                "max_drawdown", "trade_count"]


def test_latency_shift():
    preds, actuals, stamps, reality = _data()
    df = latency_stress(preds, actuals, stamps, reality, fx_backtest, [0, 2])
    assert df["latency_bars"].tolist() == [0, 2]


def test_scenario_output():
    preds, actuals, stamps, reality = _data()
    df = systematic_stress(preds, actuals, stamps, reality, fx_backtest)
    assert {"Normal", "High Slippage", "1-Bar Delay"} <= set(df["scenario"])
    matrix = cost_stress_matrix(preds, actuals, stamps, reality, fx_backtest,
                                commissions=[0, 5], slippages=[0, 5])
    assert matrix["sharpe_matrix"].shape == (2, 2)
