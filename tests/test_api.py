import time
from fastapi.testclient import TestClient
from backend import app as module


def test_upload_run_export_and_history(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "DATA", tmp_path)
    monkeypatch.setattr(module, "jobs", {})
    with TestClient(module.app) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        assert client.get("/api/datasets").json()[0]["demo"]
        external_sample = client.get("/api/sample-external.csv")
        assert external_sample.status_code == 200
        assert "macro__policy_rate__available_at" in external_sample.text
        external_upload = client.post("/api/datasets", files={"file": ("external.csv", external_sample.content)})
        assert external_upload.status_code == 200
        assert "macro__policy_rate__available_at" in external_upload.json()["columns"]
        assert isinstance(external_upload.json()["preview"][-1]["macro__policy_rate__available_at"], str)
        bad = client.post("/api/datasets", files={"file": ("bad.csv", b"close\n1")})
        assert bad.status_code == 422
        csv = module.demo_prices(700).to_csv()
        uploaded = client.post("/api/datasets", files={"file": ("prices.csv", csv)})
        assert uploaded.status_code == 200
        identifier = uploaded.json()["id"]
        assert client.post("/api/runs", json={"states": 99}).status_code == 422
        response = client.post("/api/runs", json={"dataset_id": identifier})
        assert response.status_code == 202
        run_id = response.json()["id"]
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            job = client.get(f"/api/runs/{run_id}").json()
            if job["status"] in ["completed", "failed"]:
                break
            time.sleep(.1)
        assert job["status"] == "completed", job
        export = client.get(f"/api/runs/{run_id}/export")
        assert export.status_code == 200
        assert "signal_timestamp" in export.text
        assert client.get("/api/runs").json()[0]["id"] == run_id
        # Allow the worker's final persistence to finish, then emulate restart.
        deadline = time.monotonic() + 5
        while not (tmp_path / f"run-{run_id}.json").exists() and time.monotonic() < deadline:
            time.sleep(.05)
        module.jobs.clear()
        assert client.get(f"/api/runs/{run_id}").json()["status"] == "completed"
        assert client.get("/api/runs/not-a-uuid").status_code == 404
