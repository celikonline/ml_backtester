"""Sprint 3 minimum tests: leakage-safe validation (md/04_SPRINT_3_VALIDATION.md)."""
import numpy as np
import pytest

from backend.platform.research import splits, count_splits
from backend.quant.validation import PurgedKFold


def all_parts(method, n=1000, **kw):
    return splits(n, method, kw.pop("train_ratio", .65), kw.pop("folds", 3),
                  kw.pop("gap", 5), **kw)


def test_no_train_validation_overlap():
    for method in ("holdout", "walk_forward", "purged_kfold", "rolling", "anchored"):
        for train, val, _ in all_parts(method):
            assert not set(map(int, train)) & set(map(int, val)), method
            assert len(train) > 0 and len(val) > 0, method


def test_purge_applied():
    parts = all_parts("purged_kfold", n=1000, folds=4, purge_window=20, embargo_pct=0.0)
    assert len(parts) == 4
    for train, val, meta in parts:
        assert meta["purged_samples"] == 20
        # Train is past-only and the 20-bar purge zone stays empty.
        assert train.max() < val[0]
        assert (val[0] - train.max() - 1) == 20


def test_embargo_applied():
    parts = all_parts("purged_kfold", n=1000, folds=4, purge_window=0, embargo_pct=0.05)
    assert len(parts) == 4
    for i, (train, val, meta) in enumerate(parts):
        # Embargo zone after validation; the final fold has no bars left to embargo.
        assert meta["embargo_samples"] == (50 if i < 3 else 0)
        # Train never reaches into the embargo zone after validation.
        assert train.max() < val[0]


def test_time_order_preserved():
    for method in ("holdout", "walk_forward", "purged_kfold", "rolling", "anchored"):
        for train, val, _ in all_parts(method):
            assert train.max() < val.min(), method
            assert np.all(np.diff(train) > 0) and np.all(np.diff(val) > 0), method


def test_rolling_window_size():
    parts = all_parts("rolling", n=1000, train_window=500, test_window=50, step=50)
    assert len(parts) == 10
    for train, val, _ in parts:
        assert len(train) == 500 and len(val) == 50


def test_anchored_start_fixed():
    parts = all_parts("anchored", n=1000, train_window=500, test_window=50, step=50)
    assert len(parts) == 10
    sizes = [len(t) for t, _, _ in parts]
    assert all(t[0] == 0 for t, _, _ in parts)
    assert sizes == sorted(sizes) and sizes[-1] > sizes[0]


def test_final_holdout_not_seen():
    # Mirrors execute_research dev/test boundary: partitions over x_dev must
    # stay strictly below the holdout start b.
    n, train_ratio, gap = 1000, .65, 2
    b = int(n * (train_ratio + .15))
    dev_end = b - gap
    for method in ("holdout", "walk_forward", "purged_kfold", "rolling", "anchored"):
        kw = {} if method in ("holdout", "walk_forward", "purged_kfold") else \
            {"train_window": 200, "test_window": 20, "step": 40}
        for train, val, _ in splits(dev_end, method, train_ratio, 3, gap, **kw):
            assert val.max() < b, method


def test_insufficient_data_is_domain_error():
    from backend.platform.schema import DomainError
    with pytest.raises(DomainError):
        splits(30, "rolling", .65, 3, 2, train_window=500, test_window=50, step=50)


def test_purged_kfold_class_interface():
    kf = PurgedKFold(n_splits=5, purge_window=5, embargo_pct=0.01)
    folds = list(kf.split(np.arange(600)))
    assert len(folds) == 5
    with pytest.raises(ValueError):
        PurgedKFold(n_splits=1)
    with pytest.raises(ValueError):
        PurgedKFold(embargo_pct=0.9)


def test_count_splits_budget_accounting():
    from backend.platform.schema import ExperimentSpec
    base = ExperimentSpec.model_validate({"name": "x", "dataset_id": "demo", "models": ["ridge"],
        "features": {"groups": ["technical"], "names": []},
        "optimization": {"algorithm": "none", "population": 4, "generations": 2, "elitism": 1,
                         "min_features": 3, "max_features": 10, "max_drawdown": .9},
        "validation": {"method": "walk_forward", "train_ratio": .65, "folds": 2, "gap": 2, "locked_test": True},
        "backtest": {"capital": 10000, "cost_bps": .5, "slippage_bps": .2}})
    assert count_splits(base, 2000) == 2
    purged = base.model_copy(update={"validation": base.validation.model_copy(update={"method": "purged_kfold"})})
    assert count_splits(purged, 2000) == 2
    rolling = base.model_copy(update={"validation": base.validation.model_copy(
        update={"method": "rolling", "train_window": 500, "test_window": 50, "step": 50})})
    assert count_splits(rolling, 2000) == 30
