from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def _features(n=60):
    import numpy as np
    rng = np.random.default_rng(0)
    a = rng.normal(size=n)
    return {"a": a.tolist(), "b": rng.normal(size=n).tolist(),
            "target": (a * 0.5 + rng.normal(scale=0.2, size=n)).tolist()}


def test_api_ic_envelope():
    d = _features()
    r = client.post("/api/features/ic", json={"features": {k: v for k, v in d.items() if k != "target"},
                                               "target": d["target"]})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True and body["error"] is None
    assert body["data"][0]["feature"] == "a"


def test_api_purged_no_overlap():
    r = client.post("/api/validation/purged-kfold",
                    json={"n_samples": 100, "n_splits": 3, "purge_window": 2, "embargo_pct": 0.02})
    assert r.status_code == 200
    for fold in r.json()["data"]["folds"]:
        assert not set(fold["train"]) & set(fold["validation"])


def test_api_stress_and_calibration():
    import numpy as np
    rng = np.random.default_rng(1)
    n = 120
    preds = rng.normal(size=n).tolist()
    actuals = (rng.normal(scale=0.001, size=n)).tolist()
    r = client.post("/api/backtest/stress", json={"predictions": preds, "actuals": actuals})
    assert r.status_code == 200
    assert "scenarios" in r.json()["data"]
    y = rng.integers(0, 2, n).tolist()
    p = np.clip(rng.normal(0.5, 0.2, n), 0.01, 0.99).tolist()
    r2 = client.post("/api/calibration/run", json={"y_true": y, "y_prob": p})
    assert r2.status_code == 200
    assert r2.json()["success"] is True


def test_api_quant_config():
    r = client.get("/api/quant/config")
    assert r.status_code == 200
    assert "stress_test" in r.json()["data"]["config"]
