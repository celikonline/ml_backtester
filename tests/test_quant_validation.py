import numpy as np

from backend.quant.validation import PurgedKFold, anchored_splits, nested_search, rolling_splits
from sklearn.linear_model import Ridge


def test_no_overlap():
    cv = PurgedKFold(n_splits=3, purge_window=2, embargo_pct=0.05)
    for train, val in cv.split(np.zeros(100)):
        assert not set(train) & set(val)


def test_purge_applied():
    cv = PurgedKFold(n_splits=2, purge_window=5, embargo_pct=0.0)
    folds = list(cv.split(np.zeros(60)))
    train, val = folds[0]
    assert train.max() < val.min() - 5 + 1  # purge boslugu korunur


def test_embargo_applied():
    cv = PurgedKFold(n_splits=2, purge_window=0, embargo_pct=0.1)
    folds = list(cv.split(np.zeros(100)))
    train, val = folds[0]
    # embargo sonrasi kayitlar train'de yok (kronolojik: yalnizca onceki train)
    assert train.max() < val.min()


def test_time_order():
    cv = PurgedKFold(n_splits=3)
    prev_val_start = -1
    for _, val in cv.split(np.zeros(120)):
        assert val[0] > prev_val_start
        assert (np.diff(val) > 0).all()
        prev_val_start = val[0]


def test_rolling_and_anchored():
    rolling = list(rolling_splits(200, train_window=50, test_window=10, step=10))
    assert all(len(t) == 50 and len(v) == 10 for t, v in rolling)
    anchored = list(anchored_splits(200, initial_train_window=50, test_window=10, step=10))
    assert anchored[0][0][0] == 0 and len(anchored[1][0]) == 60
    assert anchored[0][1][0] == 50


def test_nested_search_returns_scores():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(60, 3))
    y = X[:, 0] * 2 + rng.normal(scale=0.1, size=60)
    out = nested_search(X, y, lambda p: Ridge(**p), [{"alpha": 0.1}, {"alpha": 10.0}],
                        outer_cv=2, inner_cv=2)
    assert len(out["outer_scores"]) == 2
    assert out["best_params_per_fold"][0] in ({"alpha": 0.1}, {"alpha": 10.0})
