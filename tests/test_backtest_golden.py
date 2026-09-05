"""Golden regression tests for the FX reality execution model.

Every expectation below is hand-computed from first principles (signal rule,
turnover accounting, spread/commission/slippage, day-count financing). If any
of these fail, the engine's money math changed and the diff must be reviewed
as a pricing change, not a test fix.
"""
import numpy as np
import pandas as pd
import pytest
from datetime import date

from backend.engine import audit_calendar, demo_prices, fx_backtest, fx_holidays_for_year, read_prices
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


def test_leverage_scales_pnl_and_costs_linearly():
    ts = hours("2024-01-02T00:00", "2024-01-02T01:00")
    # signal [1, 1], turnover [1, 1] with final exit; spread 2 bps -> one-way 1 bp.
    base_cfg = {"spread_bps": 2.0, "commission_bps": 0.0, "slippage_bps": 0.0,
                "rollover_bps_per_day": 0.0}
    unscaled, _, _ = fx_backtest([1, 1], [0.001, 0.002], reality(**base_cfg), ts)
    assert unscaled.tolist() == pytest.approx([0.001 - 0.0001, 0.002 - 0.0001])
    # exposure = 3 * 1 = 3
    ret, signal, summary = fx_backtest(
        [1, 1], [0.001, 0.002],
        reality(max_leverage=3.0, **base_cfg), ts)
    assert signal.tolist() == [1, 1]
    assert ret.tolist() == pytest.approx([v * 3.0 for v in unscaled])
    assert summary["exposure"] == pytest.approx(3.0)
    assert summary["max_leverage"] == pytest.approx(3.0)
    assert summary["margin_calls"] == 0 and summary["liquidated"] is False
    # exposure = 4 * 0.5 = 2
    ret2, _, summary2 = fx_backtest(
        [1, 1], [0.001, 0.002],
        reality(max_leverage=4.0, max_position_fraction=0.5, **base_cfg), ts)
    assert ret2.tolist() == pytest.approx([v * 2.0 for v in unscaled])
    assert summary2["exposure"] == pytest.approx(2.0)


def test_leverage_scales_financing():
    ts = hours("2024-01-05T20:00", "2024-01-08T00:00")  # 52-hour weekend gap
    ret, _, summary = fx_backtest([1, 1], [0, 0],
                                  reality(rollover_bps_per_day=2, max_leverage=2.0), ts)
    # unscaled financing 52/24*2 bps, scaled by exposure 2
    assert ret.tolist() == pytest.approx([0.0, -(52 / 24 * 2 * 2) / 10000])
    assert summary["financing_bps"] == pytest.approx(52 / 24 * 2 * 2)
    assert summary["exposure"] == pytest.approx(2.0)


def test_margin_guard_floors_and_freezes_after_liquidation():
    ts = hours("2024-01-02T00:00", "2024-01-02T01:00", "2024-01-02T02:00")
    # exposure 30; first bar -0.04 * 30 = -1.2 -> floored to -1.0, then flat.
    ret, signal, summary = fx_backtest([1, 1, 1], [-0.04, 0.01, 0.01],
                                       reality(max_leverage=30.0), ts)
    assert signal.tolist() == [1, 1, 1]
    assert ret.tolist() == pytest.approx([-1.0, 0.0, 0.0])
    assert summary["margin_calls"] == 1 and summary["liquidated"] is True
    # equity path: 1.0 -> 0.0 -> 0.0 (never negative, never recovers)
    equity = np.cumprod(1 + np.asarray(ret))
    assert equity.tolist() == pytest.approx([0.0, 0.0, 0.0])


def test_default_exposure_preserves_legacy_path():
    ts = hours("2024-01-02T00:00", "2024-01-02T01:00")
    _, _, summary = fx_backtest([1, -1], [0.001, 0.001], reality(spread_bps=2), ts)
    assert summary["exposure"] == pytest.approx(1.0)
    assert summary["margin_calls"] == 0 and summary["liquidated"] is False


def test_leverage_inputs_are_guarded():
    ts = hours("2024-01-02T00:00", "2024-01-02T01:00")
    with pytest.raises(ValueError, match="max_leverage"):
        fx_backtest([1, 1], [0.001, 0.001], {"max_leverage": 31.0}, ts)
    with pytest.raises(ValueError, match="max_leverage"):
        fx_backtest([1, 1], [0.001, 0.001], {"max_leverage": 0.5}, ts)
    with pytest.raises(ValueError, match="max_position_fraction"):
        fx_backtest([1, 1], [0.001, 0.001], {"max_position_fraction": 0.0}, ts)
    with pytest.raises(ValueError, match="max_position_fraction"):
        fx_backtest([1, 1], [0.001, 0.001], {"max_position_fraction": 1.5}, ts)


def test_merged_reality_carries_leverage_and_honors_legacy_top_level():
    from backend.platform.research import merged_reality
    legacy = ExperimentSpec.model_validate({
        "name": "legacy leverage", "dataset_id": "demo", "models": ["ridge"],
        "backtest": {"capital": 10000, "max_leverage": 5.0,
                     "reality": {"spread_bps": 0.0}},
    })
    assert merged_reality(legacy).max_leverage == pytest.approx(5.0)
    assert merged_reality(legacy).max_position_fraction == pytest.approx(1.0)
    explicit = ExperimentSpec.model_validate({
        "name": "explicit reality", "dataset_id": "demo", "models": ["ridge"],
        "backtest": {"capital": 10000, "max_leverage": 5.0,
                     "reality": {"spread_bps": 0.0, "max_leverage": 3.0,
                                 "max_position_fraction": 0.5}},
    })
    merged = merged_reality(explicit)
    assert merged.max_leverage == pytest.approx(3.0)
    assert merged.max_position_fraction == pytest.approx(0.5)


def test_fx_holiday_calendar_lists_known_dates():
    holidays_2023 = fx_holidays_for_year(2023)
    assert date(2023, 4, 7) in holidays_2023  # Good Friday
    assert date(2023, 4, 10) in holidays_2023  # Easter Monday
    assert date(2023, 1, 2) in holidays_2023  # Jan 1 Sunday -> observed Monday
    assert date(2023, 1, 1) not in holidays_2023
    assert date(2023, 12, 25) in holidays_2023 and date(2023, 12, 26) in holidays_2023
    holidays_2022 = fx_holidays_for_year(2022)
    assert date(2022, 12, 26) in holidays_2022  # Dec 25 Sunday -> observed Monday
    assert date(2022, 12, 25) not in holidays_2022


def hourly_frame(start, end, drop_dates=()):
    idx = pd.date_range(start, end, freq="h", tz="UTC")
    idx = idx[~idx.normalize().isin(pd.DatetimeIndex(drop_dates, tz="UTC"))]
    df = pd.DataFrame({"open": 1.08, "high": 1.0810, "low": 1.0790, "close": 1.08},
                      index=idx.rename("timestamp"))
    df.attrs["source_timezone"] = "offset-aware"
    return df


def test_audit_separates_holiday_weekend_and_source_gaps():
    christmas = hourly_frame("2023-12-20T00:00", "2023-12-29T23:00",
                             drop_dates=["2023-12-23", "2023-12-24", "2023-12-25", "2023-12-26", "2023-12-30"])
    report = audit_calendar(christmas)
    # Single Fri 22 23:00 -> Wed 27 00:00 gap covering the holiday: not a weekend gap.
    assert report["gap_bars"] == 1 and report["holiday_gaps"] == 1
    assert report["weekend_gaps"] == 0 and report["midweek_gaps"] == 0
    assert "2023-12-25" in report["holidays_in_range"] and "2023-12-26" in report["holidays_in_range"]
    january = hourly_frame("2023-01-02T00:00", "2023-01-13T23:00",
                           drop_dates=["2023-01-07", "2023-01-08", "2023-01-14", "2023-01-15"])
    report = audit_calendar(january)
    # Fri Jan 6 -> Mon Jan 9 covers only Sat/Sun: plain weekend, even though
    # the observed Jan-2 holiday sits in range without causing any gap.
    assert report["weekend_gaps"] == 1 and report["holiday_gaps"] == 0 and report["midweek_gaps"] == 0
    assert "2023-01-02" in report["holidays_in_range"]
    holed = january.drop(january.index[30:33])
    assert audit_calendar(holed)["midweek_gaps"] == 1


def test_price_gap_jump_flows_exactly_through_equity():
    ts = hours("2024-01-04T23:00", "2024-01-05T00:00", "2024-01-05T01:00",
               "2024-01-08T00:00", "2024-01-08T01:00")
    actual = np.array([0.001, -0.0005, 0.002, 0.02, 0.0005])  # +2% weekend jump, no bars inside
    ret, signal, summary = fx_backtest([1, 1, 1, 1, 1], actual, reality(), ts)
    assert signal.tolist() == [1, 1, 1, 1, 1]
    # turnover [1, 0, 0, 0, 1 final exit] at zero cost: the jump passes through untouched.
    assert ret.tolist() == pytest.approx(actual.tolist())
    assert float(np.prod(1 + ret)) == pytest.approx(1.001 * 0.9995 * 1.002 * 1.02 * 1.0005)
    assert summary["margin_calls"] == 0 and summary["liquidated"] is False
    frame = pd.DataFrame({"open": 1.08, "high": 1.09, "low": 1.07, "close": 1.08},
                         index=ts.rename("timestamp"))
    frame.attrs["source_timezone"] = "offset-aware"
    audit = audit_calendar(frame)
    assert audit["gap_bars"] == 1 and audit["weekend_gaps"] == 1 and audit["holiday_gaps"] == 0


def test_price_gap_jump_with_costs_and_weekend_financing():
    ts = hours("2024-01-05T20:00", "2024-01-08T00:00")
    ret, _, summary = fx_backtest([1, 1], [0.001, 0.02],
                                  reality(spread_bps=2, rollover_bps_per_day=2), ts)
    # one-way 1 bp on turnover [1, 1]; 52-hour financing on the Monday bar.
    assert ret.tolist() == pytest.approx([0.001 - 0.0001, 0.02 - 0.0001 - (52 / 24 * 2) / 10000])
    assert summary["financing_bps"] == pytest.approx(52 / 24 * 2)


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
