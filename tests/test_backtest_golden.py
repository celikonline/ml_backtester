"""Golden regression tests for the FX reality execution model.

Every expectation below is hand-computed from first principles (signal rule,
turnover accounting, spread/commission/slippage, day-count financing). If any
of these fail, the engine's money math changed and the diff must be reviewed
as a pricing change, not a test fix.
"""
import numpy as np
import pandas as pd
import pytest

from backend.engine import audit_calendar, demo_prices, fx_backtest, read_prices
from backend.platform.research import execute_research
from backend.platform.schema import BacktestRealityConfig, ExperimentSpec


def reality(**overrides):
    base = {"spread_model": "fixed", "spread_bps": 0.0, "commission_bps": 0.0,
            "slippage_bps": 0.0, "rollover_bps_per_day": 0.0}
    base.update(overrides)
    return BacktestRealityConfig.model_validate(base)


def hours(*stamps):
    return pd.DatetimeIndex([pd.Timestamp(s, tz="UTC") for s in stamps])


def test_fixed_cost_accounting_is_exact():
    ts = hours("2024-01-02T00:00", "2024-01-02T01:00", "2024-01-02T02:00", "2024-01-02T03:00")
    actual = np.array([0.001, -0.0005, 0.002, 0.0005])
    pred = np.array([0.01, -0.01, 0.02, 0.0])
    ret, signal, summary = fx_backtest(pred, actual, reality(spread_bps=2, commission_bps=1, slippage_bps=1), ts)
    assert signal.tolist() == [1, -1, 1, 0]
    # turnover [1,2,2,1] at 3 bps one-way: [7, -1, 14, -3] bps
    assert ret.tolist() == pytest.approx([0.0007, -0.0001, 0.0014, -0.0003])
    assert summary["one_way_cost_bps"] == pytest.approx(3.0)
    assert summary["avg_spread_bps"] == pytest.approx(2.0)
    assert summary["spread_model"] == "fixed" and summary["spread_fallback"] is False
    assert summary["financing_bps"] == pytest.approx(0.0)


def test_threshold_boundary_stays_flat():
    ts = hours("2024-01-02T00:00", "2024-01-02T01:00", "2024-01-02T02:00")
    ret, signal, _ = fx_backtest([0.0001, -0.0001, 0.0], [0.01, 0.01, 0.01], reality(), ts, threshold=0.0001)
    assert signal.tolist() == [0, 0, 0]
    assert ret.tolist() == [0.0, 0.0, 0.0]


def test_reversal_pays_two_way_cost_plus_final_exit():
    ts = hours("2024-01-02T00:00", "2024-01-02T01:00")
    ret, signal, _ = fx_backtest([1.0, -1.0], [0.001, 0.001], reality(spread_bps=2), ts)
    assert signal.tolist() == [1, -1]
    # turnover [1, 2 + 1 final exit]; one-way = 1 bp
    assert ret.tolist() == pytest.approx([0.001 - 0.0001, -0.001 - 0.0003])


def test_variable_spread_scales_with_bar_range():
    ts = hours("2024-01-02T00:00", "2024-01-02T01:00", "2024-01-02T02:00", "2024-01-02T03:00")
    high = np.array([1.1020, 1.1010, 1.1030, 1.1020])
    low = np.array([1.1000, 1.1000, 1.1000, 1.1000])
    ret, signal, summary = fx_backtest([1, 1, 1, 1], [0, 0, 0, 0], reality(spread_model="ohlc_range", spread_bps=10), ts, high=high, low=low)
    assert signal.tolist() == [1, 1, 1, 1]
    # widths [20, 10, 30, 20] pips, median 20 -> scales [1, .5, 1.5, 1]; one-way halves the spread
    assert ret.tolist() == pytest.approx([-0.0005, 0.0, 0.0, -0.0005])
    assert summary["spread_model"] == "ohlc_range" and summary["spread_fallback"] is False
    assert summary["avg_spread_bps"] == pytest.approx(10.0)


def test_variable_spread_falls_back_without_bars():
    ts = hours("2024-01-02T00:00", "2024-01-02T01:00")
    ret, _, summary = fx_backtest([1, 1], [0.001, 0.001], reality(spread_model="ohlc_range", spread_bps=4), ts)
    assert summary["spread_fallback"] is True
    # fixed leg: one-way 2 bps, turnover [1, 1]
    assert ret.tolist() == pytest.approx([0.001 - 0.0002, 0.001 - 0.0002])
    with pytest.raises(ValueError, match="uzunluğu"):
        fx_backtest([1, 1], [0.001, 0.001], reality(spread_model="ohlc_range", spread_bps=4), ts, high=[1.0], low=[1.0, 1.0])


def test_weekend_gap_financing_is_exact():
    ts = hours("2024-01-05T20:00", "2024-01-08T00:00")  # 52-hour weekend gap
    ret, signal, summary = fx_backtest([1, 1], [0, 0], reality(rollover_bps_per_day=2), ts)
    assert signal.tolist() == [1, 1]
    assert ret.tolist() == pytest.approx([0.0, -(52 / 24 * 2) / 10000])
    assert summary["financing_bps"] == pytest.approx(52 / 24 * 2)


def test_asymmetric_rollover_and_wednesday_triple():
    tue_wed = hours("2024-01-02T00:00", "2024-01-03T00:00")
    _, _, flat = fx_backtest([0, 1], [0, 0], reality(rollover_long_bps_per_day=4, rollover_short_bps_per_day=12), tue_wed)
    assert flat["financing_bps"] == pytest.approx(0.0 + 4 / 10000 * 10000)  # long Wed bar, no triple
    _, _, tripled = fx_backtest([0, 1], [0, 0], reality(rollover_long_bps_per_day=4, triple_wednesday_rollover=True), tue_wed)
    assert tripled["financing_bps"] == pytest.approx(12.0)
    wed_thu = hours("2024-01-03T00:00", "2024-01-04T00:00")
    _, _, short = fx_backtest([0, -1], [0, 0], reality(rollover_long_bps_per_day=4, rollover_short_bps_per_day=12), wed_thu)
    assert short["financing_bps"] == pytest.approx(12.0)


def test_execution_is_deterministic():
    df = demo_prices(500)
    pred = np.sin(np.arange(len(df))) * 0.001
    actual = np.cos(np.arange(len(df))) * 0.0005
    cfg = reality(spread_model="ohlc_range", spread_bps=1, commission_bps=.2, rollover_bps_per_day=1)
    first = fx_backtest(pred, actual, cfg, df.index, high=df["high"].to_numpy(), low=df["low"].to_numpy())
    second = fx_backtest(pred, actual, cfg, df.index, high=df["high"].to_numpy(), low=df["low"].to_numpy())
    assert np.array_equal(first[0], second[0]) and np.array_equal(first[1], second[1]) and first[2] == second[2]


def test_calendar_audit_classifies_gaps():
    df = demo_prices(700)
    report = audit_calendar(df)
    assert report["source_timezone"] == "offset-aware"
    assert report["weekend_bars"] == 0 and report["weekend_gaps"] > 0 and report["midweek_gaps"] == 0
    holed = df.drop(df.index[100:103])
    assert audit_calendar(holed)["midweek_gaps"] == 1


def test_read_prices_records_source_timezone():
    base = demo_prices(500)
    aware_raw = base.reset_index().to_csv(index=False).encode()
    assert read_prices(aware_raw).attrs["source_timezone"] == "offset-aware"
    naive = base.reset_index()
    naive["timestamp"] = naive["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    assert read_prices(naive.to_csv(index=False).encode()).attrs["source_timezone"] == "naive-assumed-UTC"


def test_validation_and_final_test_share_reality_model(tmp_path):
    df = demo_prices(700)
    spec = ExperimentSpec.model_validate({
        "name": "reality parity", "dataset_id": "demo", "models": ["ridge"],
        "features": {"groups": ["technical"], "names": []},
        "optimization": {"algorithm": "none", "population": 4, "generations": 1, "elitism": 1,
                         "min_features": 1, "max_features": 3, "max_drawdown": .9},
        "validation": {"method": "walk_forward", "train_ratio": .65, "folds": 2, "gap": 2, "locked_test": True},
        "backtest": {"capital": 10000, "cost_bps": .5, "slippage_bps": .2,
                     "reality": {"spread_model": "ohlc_range", "spread_bps": 1.0, "commission_bps": 0.0,
                                 "slippage_bps": 0.0, "rollover_bps_per_day": 0.0}},
    })
    result = execute_research(df, spec, lambda *_: None, tmp_path)
    assert result["execution"]["spread_model"] == "ohlc_range"
    assert result["execution"]["spread_fallback"] is False
    stamps = [pd.Timestamp(p["timestamp"]) for p in result["curve"]]
    signals = [pd.Timestamp(p["signal_timestamp"]) for p in result["curve"]]
    assert all(t > s for t, s in zip(stamps, signals))
