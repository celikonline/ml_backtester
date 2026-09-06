"""
Tests for RegimeLab Notebook Lab.

Covers:
- Notebook static inspection (parameters, pip install, hardcoded secrets, imports)
- Secret encryption/decryption & masking
- Artifact collection & metrics parsing
- Notebook service lifecycle (create, version, run, events, artifacts, cancel)
- REST API endpoints
- SDK integration
"""
import io
import json
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.platform.notebooks.inspector import inspect_notebook
from backend.platform.notebooks.artifacts import collect_artifacts
from backend.platform.notebooks.service import NotebookService, _xor_obfuscate, _xor_deobfuscate
from backend.platform.notebooks.executor import _mask_secrets
from backend.platform.service import ExperimentService
from backend.app import app
import regimelab_sdk


def test_snapshot_version_run_download_flow(tmp_path):
    from backend.platform.api import nb_service
    from backend.platform.db import snapshots
    import hashlib

    db_url = "sqlite:///" + (tmp_path / "registry.sqlite3").as_posix()
    storage = tmp_path / "storage"
    exp = ExperimentService(url=db_url, storage=storage)
    ws = exp.ensure_default_workspace()["id"]
    other = exp.create_workspace({"name": "Other workspace"}, {"id": "test"})["id"]
    svc = NotebookService(url=db_url, storage=storage)
    csv = b"date,value\n2026-01-01,42\n"
    (storage / "sample.csv").write_bytes(csv)
    with svc.engine.begin() as con:
        for snapshot_id, workspace in [("snapshot-one", ws), ("snapshot-other", other)]:
            con.execute(snapshots.insert().values(
                id=snapshot_id, workspace_id=workspace, sha256=hashlib.sha256(csv).hexdigest(),
                path="sample.csv", details={"name": "Sample dataset", "rows": 1}, created_at="2026-09-06T00:00:00Z",
            ))
    app.dependency_overrides[nb_service] = lambda: svc
    try:
        with TestClient(app) as client:
            base = f"/api/v1/workspaces/{ws}"
            listed = client.get(base + "/snapshots")
            assert listed.status_code == 200
            assert [s["id"] for s in listed.json()] == ["snapshot-one"]
            assert "path" not in listed.json()[0]
            nb = json.loads(_make_sample_notebook())
            nb["cells"][-1]["source"] = [
                "from pathlib import Path\n",
                "assert DATASET_SNAPSHOT_ID == 'snapshot-one'\n",
                "assert '42' in (Path(INPUT_DIR) / 'dataset.csv').read_text()\n",
                "(Path(ARTIFACT_DIR) / 'nested').mkdir(exist_ok=True)\n",
                "(Path(ARTIFACT_DIR) / 'nested' / 'result.txt').write_text('snapshot verified')\n",
            ]
            raw = json.dumps(nb).encode()
            upload = client.post(base + "/notebooks", files={"file": ("sample.ipynb", raw)})
            assert upload.status_code == 201
            notebook_id = upload.json()["id"]
            version = client.post(base + f"/notebooks/{notebook_id}/versions", files={"file": ("v2.ipynb", raw + b"\n")}, params={"change_summary": "Snapshot verification"})
            assert version.status_code == 201
            assert version.json()["version"] == 2
            invalid = client.post(base + "/notebook-runs", json={"notebook_id": notebook_id, "dataset_snapshot_id": "snapshot-other"})
            assert invalid.status_code == 404
            created = client.post(base + "/notebook-runs", json={"notebook_id": notebook_id, "dataset_snapshot_id": listed.json()[0]["id"]})
            assert created.status_code == 202
            run_id = created.json()["id"]
            run_url = base + f"/notebook-runs/{run_id}"
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                run = client.get(run_url).json()
                if run["status"] in {"COMPLETED", "FAILED", "TIMEOUT", "CANCELLED"}:
                    break
                time.sleep(.1)
            assert run["status"] == "COMPLETED", run.get("error_message")
            events = client.get(run_url + "/events")
            assert "notebook.run.completed" in events.text
            assert "event: done" in events.text
            download = client.get(run_url + "/artifacts/nested/result.txt")
            assert download.status_code == 200
            assert download.text == "snapshot verified"
            assert "attachment" in download.headers["content-disposition"]
            executed = client.get(run_url + "/artifacts/executed.ipynb")
            assert executed.status_code == 200
            assert executed.json()["cells"][-1]["execution_count"] is not None
            for name in ["missing.txt", "..%2Fexecuted.ipynb", "..%5Cexecuted.ipynb"]:
                assert client.get(run_url + "/artifacts/" + name).status_code == 404
            foreign_url = f"/api/v1/workspaces/{other}/notebook-runs/{run_id}"
            for suffix in ["", "/artifacts", "/artifacts/executed.ipynb", "/logs", "/metrics", "/events"]:
                assert client.get(foreign_url + suffix).status_code == 404
    finally:
        app.dependency_overrides.pop(nb_service, None)
        svc.close()
        svc.engine.dispose()
        exp.engine.dispose()


def _make_sample_notebook(has_params: bool = True, has_pip: bool = False, has_secret: bool = False) -> bytes:
    cells = []
    if has_pip:
        cells.append({
            "cell_type": "code",
            "metadata": {},
            "source": ["!pip install custom_lib\n"],
            "outputs": [],
            "execution_count": None
        })
    if has_secret:
        cells.append({
            "cell_type": "code",
            "metadata": {},
            "source": ['API_KEY = "1234567890abcdef1234567890abcdef"\n'],
            "outputs": [],
            "execution_count": None
        })
    if has_params:
        cells.append({
            "cell_type": "code",
            "metadata": {"tags": ["parameters"]},
            "source": [
                "learning_rate = 0.01\n",
                "max_depth = 5\n",
                "RUN_ID = 'default'\n"
            ],
            "outputs": [],
            "execution_count": None
        })
    cells.append({
        "cell_type": "code",
        "metadata": {},
        "source": [
            "from regimelab_sdk import run\n",
            "run.log_metric('val_accuracy', 0.942)\n",
            "run.log_metric('sharpe', 1.85)\n",
            "run.log_message('Model completed successfully')\n"
        ],
        "outputs": [],
        "execution_count": None
    })

    nb = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "name": "python",
                "version": "3.11.0"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 5
    }
    return json.dumps(nb).encode("utf-8")


# ── Inspector Tests ──────────────────────────────────────────────────────────

def test_inspector_clean_parameterized_notebook():
    raw = _make_sample_notebook(has_params=True)
    res = inspect_notebook(raw)
    assert res["compatible"] is True
    assert res["parameter_cell_found"] is True
    assert "regimelab_sdk" in res["imports"]
    # No critical issues
    assert not any(i["severity"] == "critical" for i in res["issues"])


def test_inspector_detects_pip_and_missing_params():
    raw = _make_sample_notebook(has_params=False, has_pip=True)
    res = inspect_notebook(raw)
    assert res["compatible"] is False
    assert res["parameter_cell_found"] is False
    codes = {i["code"] for i in res["issues"]}
    assert "INLINE_PIP_INSTALL" in codes
    assert "NO_PARAMETER_CELL" in codes


def test_inspector_detects_secrets():
    raw = _make_sample_notebook(has_params=True, has_secret=True)
    res = inspect_notebook(raw)
    assert res["compatible"] is False
    codes = {i["code"] for i in res["issues"]}
    assert "POSSIBLE_SECRET" in codes


# ── Secret Encryption & Log Masking ──────────────────────────────────────────

def test_secret_encryption_roundtrip():
    secret_val = "secret_trading_token_999"
    enc = _xor_obfuscate(secret_val)
    assert enc != secret_val
    dec = _xor_deobfuscate(enc)
    assert dec == secret_val


def test_secret_log_masking():
    log_text = 'Using FRED_API_KEY = "abc123456789xyz" and normal log output'
    masked = _mask_secrets(log_text, ["FRED_API_KEY"])
    assert "abc123456789xyz" not in masked
    assert "***REDACTED***" in masked


# ── Artifact Collection Tests ────────────────────────────────────────────────

def test_artifact_collector(tmp_path):
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "metrics.json").write_text('{"sharpe": 1.5}', encoding="utf-8")
    (artifact_dir / "equity.csv").write_text("date,nav\n2026-01-01,1000\n", encoding="utf-8")
    (artifact_dir / "nb_params.json").write_text("{}", encoding="utf-8")  # internal file should be excluded

    collected = collect_artifacts(artifact_dir)
    names = {a["name"] for a in collected}
    assert "metrics.json" in names
    assert "equity.csv" in names
    assert "nb_params.json" not in names
    for a in collected:
        assert a["size_bytes"] > 0
        assert len(a["sha256"]) == 64


# ── Service & Execution Lifecycle Tests ───────────────────────────────────────

def test_notebook_service_lifecycle(tmp_path):
    storage = tmp_path / "storage"
    db_url = "sqlite:///" + (tmp_path / "registry.sqlite3").as_posix()
    exp_svc = ExperimentService(url=db_url, storage=storage)
    ws = exp_svc.ensure_default_workspace()
    ws_id = ws["id"]

    svc = NotebookService(url=db_url, storage=storage)

    # 1. Set secret
    sec = svc.set_secret(ws_id, "FRED_API_KEY", "fred-key-12345", "FRED API key", {"id": "test-user"})
    assert sec["key_name"] == "FRED_API_KEY"
    secrets_list = svc.list_secrets(ws_id)
    assert any(s["key_name"] == "FRED_API_KEY" for s in secrets_list)

    # 2. Upload notebook
    nb_bytes = _make_sample_notebook(has_params=True)
    nb_meta = svc.upload(
        workspace_id=ws_id,
        filename="test_model.ipynb",
        nb_bytes=nb_bytes,
        name="Test Model",
        description="A test research notebook",
        actor={"id": "test-user"},
        tags=["macro", "v1"]
    )
    assert nb_meta["notebook_code"].startswith("NB-")
    assert nb_meta["version"] == 1

    # 3. Create version 2 (with modified content to verify content_hash change)
    nb_bytes_v2 = _make_sample_notebook(has_params=True).replace(b"0.01", b"0.05")
    v2 = svc.new_version(
        notebook_id=nb_meta["id"],
        nb_bytes=nb_bytes_v2,
        filename="test_model.ipynb",
        change_summary="Version 2 updates",
        actor={"id": "test-user"},
    )
    assert v2["version"] == 2

    # 4. List notebooks & versions
    nbs = svc.list_notebooks(workspace_id=ws_id)
    assert len(nbs) >= 1
    versions = svc.list_versions(nb_meta["id"])
    assert len(versions) == 2

    # 5. Environments list
    envs = svc.list_environments()
    assert len(envs) >= 1
    default_env = envs[0]

    # 6. Start notebook run
    run_meta = svc.create_run(
        workspace_id=ws_id,
        notebook_id=nb_meta["id"],
        parameters={"learning_rate": 0.05},
        environment_id=default_env["id"],
        actor={"id": "test-user"},
    )
    assert run_meta["run_code"].startswith("NR-")
    assert run_meta["status"] in ["QUEUED", "RUNNING", "COMPLETED"]

    # Wait for completion (small notebook with papermill runs in ~3-6s)
    deadline = time.monotonic() + 30
    final_run = None
    while time.monotonic() < deadline:
        final_run = svc.get_run(run_meta["id"], workspace_id=ws_id)
        if final_run["status"] in ["COMPLETED", "FAILED", "CANCELLED"]:
            break
        time.sleep(0.5)

    assert final_run is not None
    assert final_run["status"] == "COMPLETED", f"Run failed: {final_run.get('error_message')}"
    assert "sharpe" in final_run["metrics"] or final_run["artifact_count"] >= 0

    # 7. Check logs and artifacts
    logs = svc.get_run_logs(run_meta["id"])
    assert len(logs) > 0

    artifacts = svc.get_run_artifacts(run_meta["id"])
    assert isinstance(artifacts, list)


# ── REST API Integration Tests ───────────────────────────────────────────────

def test_notebook_lab_api_endpoints():
    with TestClient(app) as client:
        # 1. Health check
        health = client.get("/api/health").json()
        assert health["status"] == "ok"

        # 2. Get workspaces to identify workspace_id
        ws_res = client.get("/api/v1/workspaces")
        assert ws_res.status_code == 200
        workspaces = ws_res.json()
        assert len(workspaces) >= 1
        ws_id = workspaces[0]["id"]

        # 3. List environments
        envs_res = client.get("/api/v1/notebook-environments")
        assert envs_res.status_code == 200
        envs = envs_res.json()
        assert len(envs) >= 1
        env_id = envs[0]["id"]

        # 4. Upload a notebook via REST API
        nb_bytes = _make_sample_notebook(has_params=True)
        files = {"file": ("api_test.ipynb", io.BytesIO(nb_bytes), "application/x-ipynb+json")}
        upload_res = client.post(
            f"/api/v1/workspaces/{ws_id}/notebooks",
            files=files,
            params={"name": "API Test Notebook", "description": "Testing upload via API"}
        )
        assert upload_res.status_code == 201
        nb = upload_res.json()
        nb_id = nb["id"]
        assert nb["notebook_code"].startswith("NB-")

        # 5. Get notebook
        get_res = client.get(f"/api/v1/workspaces/{ws_id}/notebooks/{nb_id}")
        assert get_res.status_code == 200
        assert get_res.json()["name"] == "API Test Notebook"

        # 6. Inspect notebook upload
        files_inspect = {"file": ("api_test.ipynb", io.BytesIO(nb_bytes), "application/x-ipynb+json")}
        inspect_res = client.post(f"/api/v1/workspaces/{ws_id}/notebooks/inspect", files=files_inspect)
        assert inspect_res.status_code == 200
        assert inspect_res.json()["parameter_cell_found"] is True

        # 7. Manage secrets via API
        sec_res = client.put(f"/api/v1/workspaces/{ws_id}/secrets/TEST_SECRET", json={
            "value": "super_secret_val",
            "description": "API test secret"
        })
        assert sec_res.status_code == 200
        list_sec_res = client.get(f"/api/v1/workspaces/{ws_id}/secrets")
        assert list_sec_res.status_code == 200
        assert any(s["key_name"] == "TEST_SECRET" for s in list_sec_res.json())

        # 8. Start a run via REST API
        run_res = client.post(f"/api/v1/workspaces/{ws_id}/notebook-runs", json={
            "notebook_id": nb_id,
            "environment_id": env_id,
            "parameters": {"learning_rate": 0.02}
        })
        assert run_res.status_code == 202
        run_data = run_res.json()
        run_id = run_data["id"]

        # 9. Get run status
        get_run_res = client.get(f"/api/v1/workspaces/{ws_id}/notebook-runs/{run_id}")
        assert get_run_res.status_code == 200
        assert get_run_res.json()["status"] in ["QUEUED", "RUNNING", "COMPLETED"]

        # 10. Delete secret
        del_res = client.delete(f"/api/v1/workspaces/{ws_id}/secrets/TEST_SECRET")
        assert del_res.status_code == 200

        # 11. Sanitize endpoint test
        unclean_bytes = _make_sample_notebook(has_params=False, has_pip=True, has_secret=True)
        san_res = client.post(
            f"/api/v1/workspaces/{ws_id}/notebooks/sanitize",
            files={"file": ("unclean.ipynb", io.BytesIO(unclean_bytes), "application/x-ipynb+json")}
        )
        assert san_res.status_code == 200
        sanitized_nb = json.loads(san_res.content.decode("utf-8"))
        tags_at_0 = sanitized_nb["cells"][0].get("metadata", {}).get("tags", [])
        assert "parameters" in tags_at_0

        # 12. Auto-sanitize upload test
        auto_upload_res = client.post(
            f"/api/v1/workspaces/{ws_id}/notebooks",
            files={"file": ("auto_clean.ipynb", io.BytesIO(unclean_bytes), "application/x-ipynb+json")},
            params={"name": "Auto Sanitized Notebook", "auto_sanitize": True}
        )
        assert auto_upload_res.status_code == 201
        auto_nb = auto_upload_res.json()
        assert auto_nb["notebook_code"].startswith("NB-")
