import json
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse

from backend.platform import assistants as ai
from backend.platform.api import router
from backend.platform.schema import DomainError, ExperimentSpec
from backend.platform.scope import workspace_scope
from backend.platform.service import ExperimentService


WHO = {"id": "tester", "source": "REST", "request_id": "assistant-test"}


@pytest.fixture
def manager(tmp_path):
    service = ExperimentService(url="sqlite:///" + (tmp_path / "registry.db").as_posix(), storage=tmp_path / "artifacts")
    token = workspace_scope.set(None)
    yield ai.AssistantService(service)
    workspace_scope.reset(token)
    service.close()


def test_templates_persistence_and_workspace_isolation(manager):
    assert len(manager.list()) == 4
    config = ai.AssistantConfig(name="Analyst", system_prompt="Review validation")
    with pytest.raises(DomainError) as error:
        manager.save(config, WHO, "template-research")
    assert error.value.status == 403
    first = manager.experiments.create_workspace({"name": "First"}, WHO)
    second = manager.experiments.create_workspace({"name": "Second"}, WHO)
    workspace_scope.set(first["id"])
    item = manager.save(config, WHO)
    assert ai.AssistantService(manager.experiments).get(item["id"])["name"] == "Analyst"
    workspace_scope.set(second["id"])
    assert len(manager.list()) == 4
    with pytest.raises(DomainError):
        manager.save(config, WHO, item["id"])
    workspace_scope.set(None)
    with pytest.raises(DomainError):
        manager.get(item["id"])


def test_task_permissions_context_and_failures(manager, monkeypatch):
    monkeypatch.setenv("REGIMELAB_AI_MODEL", "test-model")
    messages = []
    monkeypatch.setattr(ai, "complete", lambda value, **_: messages.extend(value) or "Evidence-based review")
    monkeypatch.setattr(manager.experiments, "get", lambda identifier: {
        "id": identifier, "name": "Study", "status": "COMPLETED", "workspace_id": None,
        "specification": {"seed": 42}, "run": {"metrics": {"sharpe": 1.2}}, "snapshot": {"path": "PRIVATE"}})
    item = manager.save(ai.AssistantConfig(name="No metrics", system_prompt="Review", permissions=["experiments"]), WHO)
    task = manager.run(ai.TaskInput(assistant_id=item["id"], prompt="Review this", experiment_id="example"))
    manager.advance(task["id"])
    task = manager.get_task(task["id"])
    assert task["status"] == "COMPLETED"
    assert "sharpe" not in json.dumps(messages)
    assert "PRIVATE" not in json.dumps(messages)
    assert "seed" in json.dumps(messages)
    manager.save(ai.AssistantConfig(name="No access", system_prompt="Review", permissions=[]), WHO, item["id"])
    with pytest.raises(DomainError) as error:
        manager.run(ai.TaskInput(assistant_id=item["id"], prompt="Review", experiment_id="example"))
    assert error.value.status == 403
    assert len(manager.list_tasks()) == 1

    def fail(_, **kwargs):
        raise DomainError("Provider unavailable", 502)
    monkeypatch.setattr(ai, "complete", fail)
    failed = manager.run(ai.TaskInput(assistant_id=item["id"], prompt="New idea"))
    manager.advance(failed["id"])
    failed = manager.get_task(failed["id"])
    assert failed["status"] == "FAILED"
    assert manager.list_tasks()[0]["output"] == "Provider unavailable"
    workspace = manager.experiments.create_workspace({"name": "Other"}, WHO)
    workspace_scope.set(workspace["id"])
    assert manager.list_tasks() == []
    with pytest.raises(DomainError):
        manager.run(ai.TaskInput(assistant_id="template-research", prompt="Review", experiment_id="example"))


def test_provider_missing_and_http_contract(manager, monkeypatch):
    monkeypatch.delenv("REGIMELAB_AI_MODEL", raising=False)
    with pytest.raises(DomainError) as error:
        manager.run(ai.TaskInput(assistant_id="template-research", prompt="Review"))
    assert error.value.status == 503
    assert manager.list_tasks() == []
    monkeypatch.setenv("REGIMELAB_AI_MODEL", "test-model")
    captured = {}

    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self, limit): return b'{"message":{"content":"Model answer"}}'

    def open_request(request, timeout):
        captured.update(json.loads(request.data))
        assert timeout == 90
        return Response()

    monkeypatch.setattr(ai.urllib.request, "urlopen", open_request)
    assert ai.complete([{"role": "user", "content": "Hello"}]) == "Model answer"
    assert captured["stream"] is False
    assert captured["model"] == "test-model"


def test_rest_auth_validation_clone_and_task(manager, monkeypatch):
    app = FastAPI()
    app.state.experiments = manager.experiments
    app.include_router(router(lambda _: None, lambda: []))

    @app.exception_handler(DomainError)
    async def handle(_, exc):
        return JSONResponse({"detail": str(exc)}, status_code=exc.status)

    monkeypatch.setenv("REGIMELAB_API_KEY", "test-secret")
    monkeypatch.setenv("REGIMELAB_AI_MODEL", "test-model")
    monkeypatch.setattr(ai, "complete", lambda _, **kwargs: "Task output")
    with TestClient(app) as client:
        assert client.get("/api/v1/assistants").status_code == 401
        client.headers["Authorization"] = "Bearer test-secret"
        assert len(client.get("/api/v1/assistants").json()["items"]) == 4
        clone = client.post("/api/v1/assistants/template-research/clone")
        assert clone.status_code == 201
        assert clone.json()["template"] is False
        assert client.post("/api/v1/assistants", json={"name": " ", "system_prompt": " "}).status_code == 422
        response = client.post("/api/v1/assistant-tasks", json={"assistant_id": clone.json()["id"], "prompt": "Review"})
        assert response.status_code == 202
        task_id = response.json()["id"]
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            task = client.get(f"/api/v1/assistant-tasks/{task_id}").json()
            if task["status"] == "COMPLETED": break
            time.sleep(.05)
        assert task["status"] == "COMPLETED"
        assert client.get("/api/v1/assistant-tasks").json()[0]["output"] == "Task output"


def test_chain_order_snapshot_and_invalid_graphs(manager, monkeypatch):
    monkeypatch.setenv("REGIMELAB_AI_MODEL", "test-model")
    leaf = manager.save(ai.AssistantConfig(name="Leaf", system_prompt="leaf"), WHO)
    child = manager.save(ai.AssistantConfig(name="Child", system_prompt="child", chain=[leaf["id"]]), WHO)
    root = manager.save(ai.AssistantConfig(name="Root", system_prompt="root", chain=[child["id"]]), WHO)
    calls = []

    def respond(messages, **kwargs):
        calls.append(messages)
        return f"output-{len(calls)}"

    monkeypatch.setattr(ai, "complete", respond)
    record = manager.run(ai.TaskInput(assistant_id=root["id"], prompt="Research"), WHO)
    # Editing after submission must not change the queued execution plan.
    manager.save(ai.AssistantConfig(name="Changed", system_prompt="new", chain=[]), WHO, child["id"])
    for _ in range(3): manager.advance(record["id"])
    finished = manager.get_task(record["id"])
    assert finished["status"] == "COMPLETED"
    assert [s["config"]["name"] for s in finished["details"]["steps"]] == ["Root", "Child", "Leaf"]
    assert "output-1" in json.dumps(calls[1])
    assert "output-2" in json.dumps(calls[2])
    manager.advance(record["id"])
    assert len(calls) == 3
    with pytest.raises(DomainError) as error:
        manager.save(ai.AssistantConfig(name="Cycle", system_prompt="x", chain=[root["id"]]), WHO, child["id"])
    assert error.value.code == "invalid_chain"
    with pytest.raises(DomainError):
        manager.save(ai.AssistantConfig(name="Missing", system_prompt="x", chain=["missing"]), WHO)
    workspace = manager.experiments.create_workspace({"name": "Other workspace"}, WHO)
    workspace_scope.set(workspace["id"])
    with pytest.raises(DomainError):
        manager.save(ai.AssistantConfig(name="Cross scope", system_prompt="x", chain=[root["id"]]), WHO)


def test_chain_limit_and_permissions(manager, monkeypatch):
    from pydantic import ValidationError
    monkeypatch.setenv("REGIMELAB_AI_MODEL", "test-model")
    with pytest.raises(ValidationError):
        ai.AssistantConfig(name="Invalid", system_prompt="x", auto_backtest=True)
    with pytest.raises(ValidationError):
        ai.AssistantConfig(name="Duplicate", system_prompt="x", chain=["template-research"] * 2)
    parent = None
    for index in range(8):
        parent = manager.save(ai.AssistantConfig(name=str(index), system_prompt="x", chain=[parent["id"]] if parent else []), WHO)
    with pytest.raises(DomainError) as error:
        manager.save(ai.AssistantConfig(name="Too long", system_prompt="x", chain=[parent["id"]]), WHO)
    assert error.value.code == "chain_limit"
    child = manager.save(ai.AssistantConfig(name="Limited", system_prompt="x", permissions=["experiments"]), WHO)
    root = manager.save(ai.AssistantConfig(name="Reader", system_prompt="x", chain=[child["id"]]), WHO)
    monkeypatch.setattr(manager.experiments, "get", lambda _: {"id": "exp", "workspace_id": None})
    with pytest.raises(DomainError) as error:
        manager.run(ai.TaskInput(assistant_id=root["id"], experiment_id="exp", prompt="Review"))
    assert error.value.status == 403
    with pytest.raises(DomainError):
        manager.run(ai.TaskInput(assistant_id="template-backtest", prompt="Backtest", run_backtest=True))


def test_cancel_and_failed_step_stop_the_chain(manager, monkeypatch):
    monkeypatch.setenv("REGIMELAB_AI_MODEL", "test-model")
    root = manager.save(ai.AssistantConfig(name="Root", system_prompt="x", chain=["template-validation"]), WHO)
    record = manager.run(ai.TaskInput(assistant_id=root["id"], prompt="Review"))
    calls = []

    def cancel_during_response(messages, **kwargs):
        calls.append(messages)
        manager.cancel(record["id"], WHO)
        return "Late response"

    monkeypatch.setattr(ai, "complete", cancel_during_response)
    manager.advance(record["id"])
    manager.advance(record["id"])
    assert manager.get_task(record["id"])["status"] == "CANCELLED"
    assert len(calls) == 1

    def fail(*args, **kwargs):
        raise DomainError("Model unavailable", 502)

    monkeypatch.setattr(ai, "complete", fail)
    failed = manager.run(ai.TaskInput(assistant_id=root["id"], prompt="Review"))
    manager.advance(failed["id"])
    manager.advance(failed["id"])
    result = manager.get_task(failed["id"])
    assert result["status"] == "FAILED"
    assert result["details"]["steps"][1]["status"] == "PENDING"


def test_automatic_backtest_real_worker_and_reuse(manager, monkeypatch):
    from backend.engine import demo_prices
    from backend.platform.db import runs
    from sqlalchemy import select

    monkeypatch.setenv("REGIMELAB_AI_MODEL", "test-model")
    captured = []
    monkeypatch.setattr(ai, "complete", lambda messages, **_: captured.append(messages) or "Measured result")
    manager.experiments.dataset_loader = lambda _: (demo_prices(700), "AI demo", True)
    ws = manager.experiments.ensure_default_workspace()
    workspace_scope.set(ws["id"])
    experiment = manager.experiments.create(ExperimentSpec.model_validate({
        "name": "Automated backtest", "dataset_id": "demo", "models": ["ridge"],
        "optimization": {"algorithm": "none"},
        "validation": {"method": "holdout", "train_ratio": .65, "folds": 2, "gap": 2, "locked_test": True},
    }), WHO, workspace_id=ws["id"])
    second = manager.save(ai.AssistantConfig(name="Second backtest review", system_prompt="Review", auto_backtest=True,
                                           permissions=["experiments", "metrics", "backtest_run"]), WHO)
    root = manager.save(ai.AssistantConfig(name="Research pipeline", system_prompt="Plan", chain=["template-backtest", second["id"]]), WHO)
    task = manager.run(ai.TaskInput(assistant_id=root["id"], experiment_id=experiment["id"], prompt="Run and review", run_backtest=True), WHO)
    # First assistant runs, then the automation step queues a real experiment and yields.
    manager.advance(task["id"])
    manager.advance(task["id"])
    waiting = manager.get_task(task["id"])
    assert waiting["status"] == "WAITING_BACKTEST"
    assert len(captured) == 1
    manager.experiments.start()
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        final = manager.get_task(task["id"])
        if final["status"] in {"COMPLETED", "FAILED"}: break
        time.sleep(.1)
    assert final["status"] == "COMPLETED", final
    assert len(captured) == 3
    measured = manager.experiments.result(experiment["id"])
    context = json.loads(captured[1][1]["content"].split("\n", 1)[1])
    assert context["metrics"] == measured["metrics"]
    assert context["status"] == "COMPLETED"
    assert final["details"]["steps"][1]["run_id"] == final["details"]["steps"][2]["run_id"]
    with manager.engine.connect() as con:
        assert len(con.execute(select(runs).where(runs.c.experiment_id == experiment["id"])).all()) == 1


def test_backtest_failure_and_analysis_only(manager, monkeypatch):
    monkeypatch.setenv("REGIMELAB_AI_MODEL", "test-model")
    current = {"id": "exp", "name": "Exp", "status": "DRAFT", "workspace_id": None, "specification": {}, "run": None}
    monkeypatch.setattr(manager.experiments, "get", lambda _: dict(current))
    calls = []
    monkeypatch.setattr(ai, "complete", lambda messages, **_: calls.append(messages) or "Draft review")

    def reject(*_):
        raise DomainError("Budget rejected", 422, "policy_rejected")

    monkeypatch.setattr(manager.experiments, "run", reject)
    task = manager.run(ai.TaskInput(assistant_id="template-backtest", experiment_id="exp", prompt="Review"))
    manager.advance(task["id"])
    assert manager.get_task(task["id"])["status"] == "COMPLETED"
    rejected = manager.run(ai.TaskInput(assistant_id="template-backtest", experiment_id="exp", prompt="Run", run_backtest=True))
    manager.advance(rejected["id"])
    assert manager.get_task(rejected["id"])["output"] == "Budget rejected"
    current["status"], current["run"] = "TRAINING", {"id": "run"}
    waiting = manager.run(ai.TaskInput(assistant_id="template-backtest", experiment_id="exp", prompt="Run", run_backtest=True))
    manager.advance(waiting["id"])
    assert manager.get_task(waiting["id"])["status"] == "WAITING_BACKTEST"
    current["status"] = "FAILED"
    manager.advance(waiting["id"])
    assert manager.get_task(waiting["id"])["status"] == "FAILED"
    assert len(calls) == 1


def test_restart_resumes_at_last_step_and_old_configs_remain_valid(manager, monkeypatch):
    from sqlalchemy import select
    monkeypatch.setenv("REGIMELAB_AI_MODEL", "test-model")
    seen = []
    monkeypatch.setattr(ai, "complete", lambda messages, **_: seen.append(messages) or "Persisted output")
    root = manager.save(ai.AssistantConfig(name="Root", system_prompt="x", chain=["template-validation"]), WHO)
    task = manager.run(ai.TaskInput(assistant_id=root["id"], prompt="Review"))
    manager.advance(task["id"])
    assert manager.get_task(task["id"])["details"]["index"] == 1
    with manager.engine.begin() as con:
        con.execute(ai.tasks.update().where(ai.tasks.c.id == task["id"]).values(status="RUNNING"))
        old_config = dict(con.execute(select(ai.assistants.c.config).where(ai.assistants.c.id == root["id"])).scalar_one())
        del old_config["chain"]
        del old_config["auto_backtest"]
        con.execute(ai.assistants.update().where(ai.assistants.c.id == root["id"]).values(config=old_config))
    assert manager.get(root["id"])["chain"] == []
    worker = ai.AssistantWorker(manager.experiments)
    worker.stop.set()  # Exercise recovery deterministically without processing the queue concurrently.
    worker.start()
    worker.close()
    assert manager.get_task(task["id"])["status"] == "QUEUED"
    manager.advance(task["id"])
    final = manager.get_task(task["id"])
    assert final["status"] == "COMPLETED"
    assert len(seen) == 2
    assert "Persisted output" in json.dumps(seen[1])
