"""Sprint 4 minimum tests: stress testing (md/05_SPRINT_4_STRESS_TEST.md)."""
import json

import numpy as np
import pandas as pd

from backend.engine import fx_backtest
from backend.platform.service import write_stress_artifact
from backend.quant.stress import (
    SYSTEMATIC_SCENARIOS,
    cost_stress_matrix,
    experiment_stress_report,
    latency_stress,
    robustness_score,
    slippage_stress,
    systematic_stress,
)


def _data(n=300):
    rng = np.random.default_rng(7)
    preds = rng.normal(size=n)
    actuals = rng.normal(scale=0.001, size=n)
    stamps = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    reality = {"spread_bps": 0.5, "commission_bps": 0.0, "slippage_bps": 0.0}
    return preds, actuals, stamps, reality


def test_zero_cost_matches_base():
    preds, actuals, stamps, reality = _data()
    row = slippage_stress(preds, actuals, stamps, reality, fx_backtest, [0]).iloc[0]
    ret, _, _ = fx_backtest(preds, actuals, reality, stamps)
    ret = np.asarray(ret, dtype=float)
    assert row["total_return"] == float(np.cumprod(1 + ret)[-1] - 1)
    cell = cost_stress_matrix(preds, actuals, stamps, reality, fx_backtest,
                              commissions=[0], slippages=[0])
    assert cell["sharpe_matrix"].iloc[0, 0] == row["sharpe"]
    assert cell["details"]["0x0"]["total_return"] == row["total_return"]


def test_higher_cost_not_better_due_to_cost_only():
    preds, actuals, stamps, reality = _data()
    df = slippage_stress(preds, actuals, stamps, reality, fx_backtest, [0, 1, 2, 5, 10, 20])
    rets = df["total_return"].tolist()
    assert rets == sorted(rets, reverse=True)
    matrix = cost_stress_matrix(preds, actuals, stamps, reality, fx_backtest)
    assert matrix["details"]["10x10"]["total_return"] <= matrix["details"]["0x0"]["total_return"]


def test_latency_shift():
    preds, actuals, stamps, reality = _data()
    df = latency_stress(preds, actuals, stamps, reality, fx_backtest, [0, 1, 2, 3, 5])
    assert df["latency_bars"].tolist() == [0, 1, 2, 3, 5]
    base = slippage_stress(preds, actuals, stamps, reality, fx_backtest, [0]).iloc[0]
    assert df.iloc[0]["sharpe"] == base["sharpe"]


def test_scenario_count():
    preds, actuals, stamps, reality = _data()
    df = systematic_stress(preds, actuals, stamps, reality, fx_backtest)
    assert len(df) == 7 and set(df["scenario"]) == set(SYSTEMATIC_SCENARIOS)


def test_worst_case_selected():
    preds, actuals, stamps, reality = _data()
    report = experiment_stress_report(preds, actuals, stamps, reality, fx_backtest)
    worst = min(report["scenarios"], key=lambda r: r["sharpe"])
    assert report["worst"] == worst
    assert report["base"]["scenario"] == "Normal"
    assert set(report) >= {"base", "worst", "robustness_score", "slippage_matrix",
                           "latency_curve", "scenarios", "cost_matrix", "report_only"}


def test_robustness_score_formula():
    s = robustness_score(1.0, 0.5, -0.2)
    assert s == 0.40 * 1.0 + 0.30 * 0.5 - 0.30 * 0.2
    assert robustness_score(0.0, 0.0, 0.0) == 0.0


def test_artifact_created(tmp_path):
    preds, actuals, stamps, reality = _data()
    report = experiment_stress_report(preds, actuals, stamps, reality, fx_backtest)
    name = write_stress_artifact(tmp_path, report)
    assert name == "stress_test_report.json"
    stored = json.loads((tmp_path / name).read_text(encoding="utf-8"))
    assert stored["worst"]["sharpe"] <= stored["base"]["sharpe"]
    assert len(stored["scenarios"]) == 7
