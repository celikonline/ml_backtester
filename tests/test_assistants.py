import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse

from backend.platform import assistants as ai
from backend.platform.api import actor, router
from backend.platform.schema import DomainError
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
    monkeypatch.setattr(ai, "complete", lambda value: messages.extend(value) or "Evidence-based review")
    monkeypatch.setattr(manager.experiments, "get", lambda identifier: {
        "id": identifier, "name": "Study", "status": "COMPLETED", "workspace_id": None,
        "specification": {"seed": 42}, "run": {"metrics": {"sharpe": 1.2}}, "snapshot": {"path": "PRIVATE"}})
    item = manager.save(ai.AssistantConfig(name="No metrics", system_prompt="Review", permissions=["experiments"]), WHO)
    task = manager.run(ai.TaskInput(assistant_id=item["id"], prompt="Review this", experiment_id="example"))
    assert task["status"] == "COMPLETED"
    assert "sharpe" not in json.dumps(messages)
    assert "PRIVATE" not in json.dumps(messages)
    assert "seed" in json.dumps(messages)
    manager.save(ai.AssistantConfig(name="No access", system_prompt="Review", permissions=[]), WHO, item["id"])
    with pytest.raises(DomainError) as error:
        manager.run(ai.TaskInput(assistant_id=item["id"], prompt="Review", experiment_id="example"))
    assert error.value.status == 403
    assert len(manager.list_tasks()) == 1

    def fail(_):
        raise DomainError("Provider unavailable", 502)
    monkeypatch.setattr(ai, "complete", fail)
    failed = manager.run(ai.TaskInput(assistant_id=item["id"], prompt="New idea"))
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
    monkeypatch.setattr(ai, "complete", lambda _: "Task output")
    with TestClient(app) as client:
        assert client.get("/api/v1/assistants").status_code == 401
        client.headers["Authorization"] = "Bearer test-secret"
        assert len(client.get("/api/v1/assistants").json()["items"]) == 4
        clone = client.post("/api/v1/assistants/template-research/clone")
        assert clone.status_code == 201
        assert clone.json()["template"] is False
        assert client.post("/api/v1/assistants", json={"name": " ", "system_prompt": " "}).status_code == 422
        assert client.post("/api/v1/assistant-tasks", json={"assistant_id": clone.json()["id"], "prompt": "Review"}).json()["status"] == "COMPLETED"
        assert client.get("/api/v1/assistant-tasks").json()[0]["output"] == "Task output"
