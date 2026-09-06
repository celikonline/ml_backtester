import numpy as np
import pandas as pd

from backend.quant.clustering import cluster_features, prune_redundant_features


def test_highly_correlated_features_same_cluster():
    rng = np.random.default_rng(0)
    base = rng.normal(size=200)
    X = pd.DataFrame({"a": base, "a_copy": base + rng.normal(scale=1e-6, size=200),
                      "b": rng.normal(size=200)})
    clusters = cluster_features(X, threshold=0.85)
    group_of = {f: cid for cid, ms in clusters.items() for f in ms}
    assert group_of["a"] == group_of["a_copy"]


def test_independent_features_separate():
    rng = np.random.default_rng(2)
    X = pd.DataFrame({f"f{i}": rng.normal(size=300) for i in range(4)})
    clusters = cluster_features(X, threshold=0.85)
    assert len(clusters) == 4


def test_prune_selects_highest_ic():
    X = pd.DataFrame(np.random.default_rng(3).normal(size=(50, 3)), columns=["a", "b", "c"])
    metrics = pd.DataFrame([
        {"feature": "a", "abs_ic": 0.5, "sign_consistency": 0.6, "missing_ratio": 0.0},
        {"feature": "b", "abs_ic": 0.1, "sign_consistency": 1.0, "missing_ratio": 0.0},
        {"feature": "c", "abs_ic": 0.9, "sign_consistency": 0.5, "missing_ratio": 0.0},
    ])
    selected = prune_redundant_features(X, metrics, {"cluster_1": ["a", "b", "c"]})
    assert selected == ["c"]
