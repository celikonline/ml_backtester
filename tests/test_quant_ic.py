import numpy as np
import pandas as pd
import pytest

from backend.quant.ic import (
    calculate_feature_ic,
    calculate_ic,
    calculate_ic_decay,
    calculate_sign_consistency,
    feature_quality_report,
    sign_consistency_report,
)


def test_positive_ic():
    f = pd.Series(np.arange(50, dtype=float))
    t = pd.Series(np.arange(50, dtype=float))
    assert calculate_ic(f, t) == pytest.approx(1.0)


def test_negative_ic():
    f = pd.Series(np.arange(50, dtype=float))
    t = pd.Series(np.arange(50, dtype=float)[::-1])
    assert calculate_ic(f, t) == pytest.approx(-1.0)


def test_nan_handling():
    f = pd.Series([1.0, np.nan, 3.0, 4.0, 5.0, 6.0])
    t = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    ic = calculate_ic(f, t)
    assert -1 <= ic <= 1


def test_constant_feature():
    f = pd.Series([1.0] * 20)
    t = pd.Series(np.arange(20, dtype=float))
    assert calculate_ic(f, t) == 0.0


def test_feature_ic_output_columns():
    rng = np.random.default_rng(0)
    X = pd.DataFrame({"a": rng.normal(size=100), "b": rng.normal(size=100)})
    y = pd.Series(X["a"] * 0.5 + rng.normal(scale=0.1, size=100))
    df = calculate_feature_ic(X, y)
    assert list(df.columns) == ["feature", "ic", "abs_ic", "sample_count"]
    assert df.iloc[0]["feature"] == "a"
    assert ((df["ic"] >= -1) & (df["ic"] <= 1)).all()


def test_ic_decay_default_horizons():
    rng = np.random.default_rng(1)
    f = pd.Series(rng.normal(size=200))
    t = pd.Series(rng.normal(size=200))
    df = calculate_ic_decay(f, t)
    assert df["horizon"].tolist() == [1, 2, 3, 5, 10, 20]
    assert list(df.columns) == ["feature", "horizon", "ic", "sample_count"]


def test_ic_decay_no_future_leak():
    # Son barlardaki aşırı feature outlier'ı h=1'i etkiler ama h=20'de
    # tail drop edildiği için etkisiz kalmalı (gelecek sızıntısı yok).
    n = 60
    base = np.arange(n, dtype=float)
    f = pd.Series(base)
    t = pd.Series(base)
    f_tail = f.copy()
    f_tail.iloc[-5:] = 1e6
    df_clean = calculate_ic_decay(f, t, horizons=[1, 20])
    df_tail = calculate_ic_decay(f_tail, t, horizons=[1, 20])
    assert df_tail["sample_count"].iloc[0] >= df_tail["sample_count"].iloc[-1]
    # h=1 tüm satırları kullanır -> outlier IC'yi bozar; h=20 tail'i atar.
    assert abs(df_tail.set_index("horizon").loc[1, "ic"]) < abs(
        df_clean.set_index("horizon").loc[1, "ic"])
    assert df_tail.set_index("horizon").loc[20, "ic"] == \
        df_clean.set_index("horizon").loc[20, "ic"] == pytest.approx(1.0)


def test_sign_consistency():
    assert calculate_sign_consistency([0.07, 0.05, 0.09, 0.02]) == 1.0
    assert calculate_sign_consistency([0.05, -0.04, 0.03]) == 2 / 3
    assert calculate_sign_consistency([]) == 0.0


def test_quality_report_sorts_by_score():
    ic_df = pd.DataFrame([{"feature": "a", "ic": 0.4, "abs_ic": 0.4, "sample_count": 50},
                          {"feature": "b", "ic": 0.1, "abs_ic": 0.1, "sample_count": 50}])
    cons = sign_consistency_report({"a": [0.4, 0.3], "b": [0.1, -0.1]})
    rep = feature_quality_report(ic_df, cons, {"a": 0.9, "b": 0.1})
    assert rep.iloc[0]["feature"] == "a"
    assert 0 <= rep.iloc[0]["quality_score"] <= 1
