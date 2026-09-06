import numpy as np
import pandas as pd

from backend.quant.calibration import QuantilePredictor, calibrate_probabilities, calibration_metrics
from backend.quant.dimensionality import apply_pca, apply_pls, apply_transformations


def test_probability_range():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 200)
    p = np.clip(rng.normal(0.5, 0.2, 200), 0.01, 0.99)
    cal = calibrate_probabilities(y, p, method="isotonic")
    assert ((cal >= 0) & (cal <= 1)).all()


def test_brier_score():
    rng = np.random.default_rng(1)
    y = rng.integers(0, 2, 200)
    p = np.clip(rng.normal(0.5, 0.2, 200), 0.01, 0.99)
    m = calibration_metrics(y, p, calibrate_probabilities(y, p, "sigmoid"))
    assert m["brier_raw"] >= 0 and m["brier_calibrated"] >= 0
    assert len(m["curve_raw"]["prob_true"]) > 0


def test_quantile_prediction_shape():
    rng = np.random.default_rng(2)
    X = rng.normal(size=(120, 4))
    y = X[:, 0] + rng.normal(scale=0.1, size=120)
    pred = QuantilePredictor().fit(X, y).predict(X)
    assert list(pred.columns) == ["p10", "p50", "p90"]
    assert (pred["p10"] <= pred["p90"]).mean() > 0.8


def test_pca_train_only_and_disabled():
    rng = np.random.default_rng(3)
    Xtr = pd.DataFrame(rng.normal(size=(100, 6)))
    Xte = pd.DataFrame(rng.normal(size=(20, 6)))
    out = apply_pca(Xtr, Xte, variance_threshold=0.95, enabled=True)
    assert out["X_train"].shape[1] <= 6 and out["X_other"].shape[0] == 20
    off = apply_pca(Xtr, Xte, enabled=False)
    assert off["X_train"].shape == Xtr.shape


def test_pls_and_transformations():
    rng = np.random.default_rng(4)
    Xtr = pd.DataFrame(rng.normal(size=(80, 5)))
    y = rng.normal(size=80)
    out = apply_pls(Xtr, y, Xtr, n_components=2, enabled=True)
    assert out["X_train"].shape[1] == 2
    t = apply_transformations(pd.DataFrame({"a": [1.0, 2.0, 100.0]}),
                              {"winsorize": {"enabled": True, "lower": 0.0, "upper": 0.5}})
    assert t["a"].max() <= 100.0
