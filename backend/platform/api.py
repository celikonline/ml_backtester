import asyncio
import csv
import hashlib
import hmac
import io
import json
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Header, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from sqlalchemy import select, func, func

from .schema import ExperimentSpec, SearchSpaceDefinition, WorkspaceCreate, WorkspacePatch, CloneSpec, CompareSpec, DomainError, POLICY, TERMINAL
from .service import ExperimentService
from .models import MODEL_REGISTRY
from .research import registry
from .families import family_registry
from .db import audits, auth_users, auth_tokens, workspace_partners
from .auth_utils import hash_password, verify_password, create_jwt, decode_jwt


def actor(request:Request):
    key=os.environ.get("REGIMELAB_API_KEY")
    authorization=request.headers.get("authorization","")
    if key and not hmac.compare_digest(authorization,"Bearer "+key):
        raise DomainError("API anahtarı gerekli.",401,"unauthorized")
    if not key and request.client and request.client.host not in {"127.0.0.1","::1","testclient"}:
        raise DomainError("Yerel mod yalnızca localhost istemcilerine açıktır.",403,"local_only")
    origin=request.headers.get("origin")
    if origin:
        from urllib.parse import urlparse
        if urlparse(origin).hostname not in {"127.0.0.1","localhost","::1"}: raise DomainError("Bu Origin izinli değil.",403,"origin_rejected")
    source=request.headers.get("x-regimelab-source","WEB" if origin else "REST")
    return {"id":"api-client" if key else "local-user","source":source if source in {"WEB","REST","MCP"} else "REST",
            "request_id":request.headers.get("x-request-id",str(uuid.uuid4()))[:64]}


def service(request:Request): return request.app.state.experiments
def nb_service(request:Request): return request.app.state.notebooks


def router(dataset_loader, datasets_list):
    @asynccontextmanager
    async def lifespan(app):
        if not getattr(app.state,"experiments",None): app.state.experiments=ExperimentService(dataset_loader=dataset_loader)
        # Authentication tables were introduced after the initial migration chain.
        # Create them idempotently so existing local databases can still log in.
        from .db import metadata
        metadata.create_all(app.state.experiments.engine, tables=[auth_users, auth_tokens, workspace_partners])
        app.state.experiments.start()
        from .notebooks.service import NotebookService
        if not getattr(app.state,"notebooks",None): app.state.notebooks=NotebookService()
        yield
        app.state.experiments.close()
        app.state.notebooks.close()

    api=APIRouter(prefix="/api/v1",dependencies=[Depends(actor)],lifespan=lifespan)
    from .assistants import assistant_router
    api.include_router(assistant_router(service, actor))

    @api.get("/capabilities")
    def capabilities():
        return {"schema_version":"1.0","models":[{"id":k,**v,"status":"implemented"} for k,v in MODEL_REGISTRY.items()],
            "policy":POLICY,"auth_mode":"api_key" if os.environ.get("REGIMELAB_API_KEY") else "local_single_user",
            "unavailable":[{"name":n,"status":"requires_data"} for n in ["ALFRED / vintage macro","FX IV surface","OIS / forward points","Order flow / microstructure"]]+
                          [{"name":n,"status":"planned"} for n in ["TFT / LSTM","Optuna / full genome","Stacking","LLM prompt builder","Champion approval / RBAC"]]}

    @api.get("/specification/schema")
    def schema(): return ExperimentSpec.model_json_schema()

    @api.post("/research/estimate")
    def research_estimate(spec:ExperimentSpec,snapshot_id:str|None=None,workspace_id:str|None=None,s=Depends(service)):
        return s.estimate(spec, snapshot_id, workspace_id)

    @api.get("/research/budget")
    def research_budget(workspace_id:str|None=None,s=Depends(service)): return s.budget_status(workspace_id)

    @api.patch("/research/budget")
    def update_budget(body:dict,workspace_id:str|None=None,s=Depends(service),who=Depends(actor)):
        return s.update_budget_limits(body.get("limits", {}),who,workspace_id)

    @api.get("/research/ledger")
    def research_ledger(page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=500), workspace_id: str|None=None,s=Depends(service)):
        with s.engine.connect() as con:
            total = con.execute(select(func.count()).select_from(s.research_trial_events)).scalar()
        offset = (page - 1) * page_size
        with s.engine.connect() as con:
            rows = con.execute(select(s.research_trial_events).order_by(s.research_trial_events.c.id.desc()).limit(page_size).offset(offset)).mappings().all()
        return {"page": page, "page_size": page_size, "total": total or 0, "items": [dict(r) for r in rows]}

    @api.get("/workspaces")
    def list_workspaces(include_archived:bool=False,s=Depends(service)): return s.list_workspaces(include_archived)

    @api.post("/workspaces",status_code=201)
    def create_workspace(body:WorkspaceCreate,s=Depends(service),who=Depends(actor)): return s.create_workspace(body,who)

    @api.get("/workspaces/{identifier}")
    def get_workspace(identifier:str,s=Depends(service)): return s.get_workspace(identifier)

    @api.patch("/workspaces/{identifier}")
    def patch_workspace(identifier:str,body:WorkspacePatch,s=Depends(service),who=Depends(actor)): return s.patch_workspace(identifier,body,who)

    @api.post("/workspaces/{identifier}/archive")
    def archive_workspace(identifier:str,s=Depends(service),who=Depends(actor)): return s.archive_workspace(identifier,who)

    @api.get("/search-spaces")
    def list_search_spaces(workspace_id:str|None=None,s=Depends(service)): return s.list_search_spaces(workspace_id)

    @api.post("/search-spaces", status_code=201)
    def create_search_space(body:SearchSpaceDefinition,workspace_id:str|None=None,s=Depends(service),who=Depends(actor)): return s.create_search_space(body,who,workspace_id)

    @api.get("/search-spaces/{identifier}")
    def get_search_space(identifier:str,s=Depends(service)): return s.get_search_space(identifier)

    @api.get("/datasets")
    def datasets(): return datasets_list()

    @api.get("/datasets/{identifier}")
    def inspect_dataset(identifier:str):
        from backend.engine import describe
        df,name,demo=dataset_loader(identifier)
        return describe(df,identifier,name,demo)

    @api.get("/features")
    def features(q:str="",dataset_id:str|None=None):
        df = dataset_loader(dataset_id)[0] if dataset_id else None
        return [f for f in registry(df) if q.lower() in f["name"].lower()]

    @api.get("/feature-families")
    def feature_families(): return family_registry()

    @api.get("/models")
    def models(): return [{"id":k,**v} for k,v in MODEL_REGISTRY.items()]

    @api.get("/past-experiments")
    def list_past_experiments(q:str="",status:str|None=None,model:str|None=None,optimizer:str|None=None,tag:str|None=None,workspace_id:str|None=None,s=Depends(service)):
        return s.list(q,status,model,optimizer,tag,workspace_id)

    @api.post("/experiments",status_code=201)
    def create(spec:ExperimentSpec,workspace_id:str|None=None,s=Depends(service),who=Depends(actor)): return s.create(spec,who,workspace_id=workspace_id)

    @api.get("/experiments")
    def list_experiments(q:str="", status:str|None=None, model:str|None=None,
                         optimizer:str|None=None, tag:str|None=None,
                         workspace_id:str|None=None, s=Depends(service)):
        return s.list(q, status, model, optimizer, tag, workspace_id)

    @api.post("/experiments/compare")
    def compare(body:CompareSpec,s=Depends(service),who=Depends(actor)):
        report=s.compare(body.experiment_ids)
        with s.engine.begin() as con: s.audit(con,"experiments.compare",None,who,{"ids":body.experiment_ids})
        return report

    @api.get("/experiments/{identifier}")
    def get(identifier:str,s=Depends(service)): return s.get(identifier)

    @api.get("/experiments/{identifier}/seal")
    def seal(identifier:str,s=Depends(service)):
        item=s.get(identifier)
        return s.seal_status(item["snapshot_id"])

    @api.get("/experiments/{identifier}/seal/history")
    def seal_history(identifier:str,s=Depends(service)):
        item=s.get(identifier)
        return s.seal_history(item["snapshot_id"])

    @api.post("/experiments/{identifier}/seal/invalidate")
    def invalidate_seal(identifier:str,payload:dict,s=Depends(service),who=Depends(actor)):
        item=s.get(identifier)
        return s.invalidate_seal(s.seal_status(item["snapshot_id"])["seal_id"],payload.get("reason",""),who)

    @api.post("/experiments/{identifier}/seal/rotate")
    def rotate_seal(identifier:str,payload:dict,s=Depends(service),who=Depends(actor)):
        item=s.get(identifier)
        return s.rotate_seal(item["snapshot_id"],payload.get("reason",""),who)

    @api.get("/experiments/{identifier}/lineage")
    def lineage(identifier:str,s=Depends(service)): return s.lineage(identifier)

    @api.patch("/experiments/{identifier}")
    def patch(identifier:str,body:ExperimentSpec,s=Depends(service),who=Depends(actor)): return s.patch(identifier,body,who)

    @api.post("/experiments/{identifier}/clone",status_code=201)
    def clone(identifier:str,body:CloneSpec,s=Depends(service),who=Depends(actor)): return s.clone(identifier,body,who)

    @api.post("/experiments/{identifier}/run",status_code=202)
    def run(identifier:str,idempotency_key:str|None=Header(default=None),s=Depends(service),who=Depends(actor)):
        return s.run(identifier,idempotency_key,who)

    @api.post("/experiments/{identifier}/cancel")
    def cancel(identifier:str,s=Depends(service),who=Depends(actor)): return s.cancel(identifier,who)

    @api.get("/experiments/{identifier}/status")
    def status(identifier:str,s=Depends(service)):
        item=s.get(identifier)
        return {"id":item["id"],"status":item["status"],"run":item["run"]}

    @api.get("/experiments/{identifier}/logs")
    def logs(identifier:str,after:int=0,s=Depends(service)): return s.logs(identifier,after)

    @api.get("/experiments/{identifier}/events")
    async def event_stream(identifier:str,request:Request,after:int=0,s=Depends(service)):
        s.get(identifier)
        try: cursor=max(after,int(request.headers.get("last-event-id","0")))
        except ValueError: raise DomainError("Geçersiz event cursor.",422)
        async def stream():
            last=cursor
            while not await request.is_disconnected():
                records=await asyncio.to_thread(s.logs,identifier,last)
                for record in records:
                    last=record["id"]
                    yield f"id: {last}\ndata: {json.dumps(record,ensure_ascii=False)}\n\n"
                current=await asyncio.to_thread(s.get,identifier)
                if current["status"] in TERMINAL:
                    yield "event: done\ndata: {}\n\n"
                    break
                yield ": heartbeat\n\n"
                await asyncio.sleep(.75)
        return StreamingResponse(stream(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

    @api.get("/experiments/{identifier}/result")
    def result(identifier:str,s=Depends(service)): return s.result(identifier)

    @api.get("/experiments/{identifier}/metrics")
    def metrics(identifier:str,s=Depends(service)):
        r=s.result(identifier)
        return {"validation":r["validation_metrics"],"test":r["metrics"],"sharpe_delta":r["validation_test_sharpe_delta"]}

    @api.get("/experiments/{identifier}/feature-analysis")
    def feature_analysis(identifier:str,s=Depends(service)): return s.result(identifier)["feature_analysis"]

    @api.get("/experiments/{identifier}/feature-evaluations")
    def feature_evaluation_history(identifier:str,s=Depends(service)): return s.feature_evaluations(identifier)

    @api.get("/experiments/{identifier}/feature-intelligence")
    def feature_intelligence(identifier:str,s=Depends(service)): return s.feature_intelligence(identifier)

    @api.get("/experiments/{identifier}/optimization")
    def optimization(identifier:str,s=Depends(service)):
        if s.get(identifier)["status"]=="COMPLETED": return s.result(identifier)["optimization"]
        return {"generations":[e["payload"] for e in s.logs(identifier) if e["type"]=="optimization.generation.completed"]}

    @api.get("/experiments/{identifier}/candidates")
    def candidates(identifier:str,s=Depends(service)): return s.candidates(identifier)

    @api.get("/candidates/{identifier}")
    def candidate(identifier:str,s=Depends(service)): return s.candidate(identifier)

    @api.get("/experiments/{identifier}/pareto")
    def pareto(identifier:str,s=Depends(service)): return s.result(identifier)["optimization"]["pareto"]

    @api.get("/experiments/{identifier}/backtest")
    def backtest(identifier:str,s=Depends(service)):
        r=s.result(identifier)
        return {"metrics":r["metrics"],"cost_sensitivity":r["cost_sensitivity"],"curve":r["curve"]}

    @api.get("/experiments/{identifier}/regimes")
    def regimes(identifier:str,s=Depends(service)):
        r=s.result(identifier)
        return {"states":r["regimes"],"transition":r["transition"]}

    @api.get("/experiments/{identifier}/equity")
    def equity(identifier:str,s=Depends(service)): return s.result(identifier)["curve"]

    @api.get("/experiments/{identifier}/artifacts")
    def artifacts(identifier:str,s=Depends(service)): return s.artifacts(identifier)

    @api.get("/experiments/{identifier}/artifacts/{name}")
    def download(identifier:str,name:str,s=Depends(service)):
        if name not in {a["name"] for a in s.artifacts(identifier)}: raise DomainError("Artifact bulunamadı.",404)
        item=s.get(identifier)
        return FileResponse(s.safe_path(f"runs/{item['run']['id']}/{name}"),filename=name)

    @api.get("/experiments/{identifier}/export")
    def export(identifier:str,s=Depends(service)):
        rows=s.result(identifier)["curve"]
        out=io.StringIO();writer=csv.DictWriter(out,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        return Response(out.getvalue(),media_type="text/csv",headers={"Content-Disposition":'attachment; filename="experiment-equity.csv"'})

    # ── Activity ─────────────────────────────────────────────────────────────
    @api.get("/activity")
    def activity(page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=500), s=Depends(service)):
        with s.engine.connect() as con:
            total = con.execute(select(func.count()).select_from(audits)).scalar()
        offset = (page - 1) * page_size
        with s.engine.connect() as con:
            rows = con.execute(select(audits).order_by(audits.c.id.desc()).limit(page_size).offset(offset)).mappings().all()
        return {"page": page, "page_size": page_size, "total": total or 0, "items": [dict(r) for r in rows]}

    # ── Notebook Lab ──────────────────────────────────────────────────────────

    # Environments
    @api.get("/notebook-environments")
    def list_nb_environments(nbs=Depends(nb_service)):
        return nbs.list_environments()

    @api.post("/notebook-environments", status_code=201)
    def create_nb_environment(body:dict, nbs=Depends(nb_service), who=Depends(actor)):
        return nbs.create_environment(body, who)

    @api.get("/notebook-environments/{env_id}")
    def get_nb_environment(env_id:str, nbs=Depends(nb_service)):
        return nbs.get_environment(env_id)

    # Notebooks registry
    @api.post("/workspaces/{workspace_id}/notebooks", status_code=201)
    async def upload_notebook(
        workspace_id:str,
        file:UploadFile=File(...),
        name:str=Query(default=""),
        description:str=Query(default=""),
        tags:str=Query(default=""),
        auto_sanitize:bool=Query(default=False),
        nbs=Depends(nb_service), who=Depends(actor),
    ):
        nb_bytes = await file.read()
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        return nbs.upload(
            workspace_id=workspace_id, filename=file.filename or "notebook.ipynb",
            nb_bytes=nb_bytes, name=name or (file.filename or "notebook.ipynb"),
            description=description, actor=who, tags=tag_list,
            auto_sanitize=auto_sanitize,
        )

    @api.get("/workspaces/{workspace_id}/notebooks")
    def list_workspace_notebooks(workspace_id:str, include_archived:bool=False, nbs=Depends(nb_service)):
        return nbs.list_notebooks(workspace_id=workspace_id, include_archived=include_archived)

    @api.get("/workspaces/{workspace_id}/notebooks/{notebook_id}")
    def get_workspace_notebook(workspace_id:str, notebook_id:str, nbs=Depends(nb_service)):
        return nbs.get_notebook(notebook_id, workspace_id=workspace_id)

    @api.post("/workspaces/{workspace_id}/notebooks/{notebook_id}/archive")
    def archive_workspace_notebook(workspace_id:str, notebook_id:str, nbs=Depends(nb_service), who=Depends(actor)):
        nb = nbs.get_notebook(notebook_id, workspace_id=workspace_id)
        return nbs.archive_notebook(nb["id"], who)

    @api.post("/workspaces/{workspace_id}/notebooks/inspect")
    async def inspect_notebook_upload(workspace_id:str, file:UploadFile=File(...), nbs=Depends(nb_service)):
        nb_bytes = await file.read()
        return nbs.inspect_notebook(nb_bytes)

    @api.post("/workspaces/{workspace_id}/notebooks/sanitize")
    async def sanitize_notebook_upload(workspace_id:str, file:UploadFile=File(...), nbs=Depends(nb_service)):
        nb_bytes = await file.read()
        sanitized_bytes, changes = nbs.sanitize(nb_bytes)
        return Response(
            content=sanitized_bytes,
            media_type="application/x-ipynb+json",
            headers={"Content-Disposition": f'attachment; filename="sanitized_{file.filename or "notebook.ipynb"}"'}
        )

    @api.get("/workspaces/{workspace_id}/notebooks/{notebook_id}/versions")
    def list_notebook_versions(workspace_id:str, notebook_id:str, nbs=Depends(nb_service)):
        nb = nbs.get_notebook(notebook_id, workspace_id=workspace_id)
        return nbs.list_versions(nb["id"])

    @api.post("/workspaces/{workspace_id}/notebooks/{notebook_id}/versions", status_code=201)
    async def create_notebook_version(
        workspace_id:str, notebook_id:str,
        file:UploadFile=File(...),
        change_summary:str=Query(default=""),
        nbs=Depends(nb_service), who=Depends(actor),
    ):
        nb_bytes = await file.read()
        nb = nbs.get_notebook(notebook_id, workspace_id=workspace_id)
        return nbs.new_version(
            notebook_id=nb["id"],
            nb_bytes=nb_bytes,
            filename=file.filename or "notebook.ipynb",
            change_summary=change_summary,
            actor=who,
        )

    @api.get("/workspaces/{workspace_id}/snapshots")
    def list_notebook_snapshots(workspace_id:str, nbs=Depends(nb_service)):
        return nbs.list_snapshots(workspace_id)

    @api.get("/workspaces/{workspace_id}/notebook-runs/{run_id}/artifacts/{name:path}")
    def download_notebook_artifact(workspace_id:str, run_id:str, name:str, nbs=Depends(nb_service)):
        path = nbs.artifact_path(run_id, name, workspace_id)
        return FileResponse(path, filename=path.name)

    # Notebook runs
    @api.post("/workspaces/{workspace_id}/notebook-runs", status_code=202)
    def create_notebook_run(workspace_id:str, body:dict, nbs=Depends(nb_service), who=Depends(actor)):
        return nbs.create_run(
            workspace_id=workspace_id,
            notebook_id=body["notebook_id"],
            experiment_id=body.get("experiment_id"),
            dataset_snapshot_id=body.get("dataset_snapshot_id"),
            environment_id=body.get("environment_id"),
            parameters=body.get("parameters", {}),
            network_mode=body.get("network_mode", "SNAPSHOT_ONLY"),
            actor=who,
        )

    @api.get("/workspaces/{workspace_id}/notebook-runs")
    def list_notebook_runs(workspace_id:str, notebook_id:str|None=None, experiment_id:str|None=None, limit:int=50, nbs=Depends(nb_service)):
        return nbs.list_runs(workspace_id=workspace_id, notebook_id=notebook_id, experiment_id=experiment_id, limit=limit)

    @api.get("/workspaces/{workspace_id}/notebook-runs/{run_id}")
    def get_notebook_run(workspace_id:str, run_id:str, nbs=Depends(nb_service)):
        return nbs.get_run(run_id, workspace_id=workspace_id)

    @api.post("/workspaces/{workspace_id}/notebook-runs/{run_id}/cancel")
    def cancel_notebook_run(workspace_id:str, run_id:str, nbs=Depends(nb_service), who=Depends(actor)):
        nbs.get_run(run_id, workspace_id=workspace_id)
        return nbs.cancel_run(run_id, who)

    @api.get("/workspaces/{workspace_id}/notebook-runs/{run_id}/logs")
    def get_notebook_run_logs(workspace_id:str, run_id:str, after:int=0, nbs=Depends(nb_service)):
        nbs.get_run(run_id, workspace_id=workspace_id)
        return nbs.get_run_logs(run_id, after)

    @api.get("/workspaces/{workspace_id}/notebook-runs/{run_id}/metrics")
    def get_notebook_run_metrics(workspace_id:str, run_id:str, nbs=Depends(nb_service)):
        nbs.get_run(run_id, workspace_id=workspace_id)
        return nbs.get_run_metrics(run_id)

    @api.get("/workspaces/{workspace_id}/notebook-runs/{run_id}/artifacts")
    def get_notebook_run_artifacts(workspace_id:str, run_id:str, nbs=Depends(nb_service)):
        nbs.get_run(run_id, workspace_id=workspace_id)
        return nbs.get_run_artifacts(run_id)

    @api.get("/workspaces/{workspace_id}/notebook-runs/{run_id}/events")
    async def notebook_run_event_stream(workspace_id:str, run_id:str, request:Request, after:int=0, nbs=Depends(nb_service)):
        nbs.get_run(run_id, workspace_id=workspace_id)
        NB_TERMINAL = {"COMPLETED","FAILED","CANCELLED","TIMEOUT","POLICY_REJECTED"}
        try: cursor=max(after,int(request.headers.get("last-event-id","0")))
        except ValueError: raise DomainError("Geçersiz event cursor.",422)
        async def stream():
            last=cursor
            while not await request.is_disconnected():
                records=await asyncio.to_thread(nbs.get_run_logs,run_id,last)
                for record in records:
                    last=record["id"]
                    yield f"id: {last}\ndata: {json.dumps(record,ensure_ascii=False)}\n\n"
                current=await asyncio.to_thread(nbs.get_run,run_id)
                if current["status"] in NB_TERMINAL:
                    yield "event: done\ndata: {}\n\n"
                    break
                yield ": heartbeat\n\n"
                await asyncio.sleep(.75)
        return StreamingResponse(stream(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

    # Workspace secrets
    @api.get("/workspaces/{workspace_id}/secrets")
    def list_workspace_secrets(workspace_id:str, nbs=Depends(nb_service)):
        return nbs.list_secrets(workspace_id)

    @api.put("/workspaces/{workspace_id}/secrets/{key_name}")
    def set_workspace_secret(workspace_id:str, key_name:str, body:dict, nbs=Depends(nb_service), who=Depends(actor)):
        return nbs.set_secret(workspace_id, key_name, body.get("value",""), body.get("description",""), who)

    @api.delete("/workspaces/{workspace_id}/secrets/{key_name}")
    def delete_workspace_secret(workspace_id:str, key_name:str, nbs=Depends(nb_service), who=Depends(actor)):
        return nbs.delete_secret(workspace_id, key_name, who)

    return api


def auth_router():
    """Authentication routes - no actor dependency, JWT-based."""
    auth = APIRouter(prefix="/api/auth")

    @auth.post("/register")
    def register(request: Request, body: dict):
        name = body.get("name", "").strip()
        email = body.get("email", "").strip().lower()
        password = body.get("password", "")
        if not email or not password:
            raise DomainError("İsim, e-posta ve şifre gereklidir.", 422, "validation_error")
        if len(password) < 8:
            raise DomainError("Şifre en az 8 karakter olmalı.", 422, "validation_error")
        salt, pw_hash = hash_password(password)
        user_id = f"user_{secrets.token_urlsafe(16)}"
        now = datetime.now(timezone.utc).isoformat()
        engine = request.app.state.experiments.engine
        with engine.begin() as con:
            existing = con.execute(select(auth_users.c.id).where(auth_users.c.email == email)).scalar()
        if existing:
            raise DomainError("Bu e-posta zaten kayıtlı.", 409, "email_conflict")
        with engine.begin() as con:
            con.execute(auth_users.insert().values(
                id=user_id, email=email, password_hash=pw_hash, password_salt=salt,
                name=name, role="user", is_active=1, created_at=now, last_login_at=None, features={}, workspace_id=None
            ))
        token = create_jwt(user_id, email, name)
        return {"id": user_id, "email": email, "name": name, "token": token}

    @auth.post("/login")
    def login(request: Request, body: dict):
        email = body.get("email", "").strip().lower()
        password = body.get("password", "")
        if not email or not password:
            raise DomainError("E-posta ve şifre gereklidir.", 422, "validation_error")
        engine = request.app.state.experiments.engine
        row = engine.connect().execute(select(auth_users).where(auth_users.c.email == email)).first()
        # The demo account is intentionally available in local development only.
        if not row and email == "demo@regimelab.io" and not os.environ.get("REGIMELAB_API_KEY"):
            salt, pw_hash = hash_password("demo1234")
            demo_id = "user_demo"
            now = datetime.now(timezone.utc).isoformat()
            with engine.begin() as con:
                con.execute(auth_users.insert().values(
                    id=demo_id, email=email, password_hash=pw_hash, password_salt=salt,
                    name="Demo User", role="user", is_active=1, created_at=now,
                    last_login_at=None, features={}, workspace_id=None,
                ))
            row = engine.connect().execute(select(auth_users).where(auth_users.c.email == email)).first()
        if not row or not verify_password(password, row.password_salt, row.password_hash):
            raise DomainError("E-posta veya şifre hatalı.", 401, "invalid_credentials")
        if not row.is_active:
            raise DomainError("Hesap aktif değil.", 403, "inactive")
        now = datetime.now(timezone.utc).isoformat()
        token_id = secrets.token_hex(16)
        expires = datetime.fromtimestamp(datetime.now(tz=timezone.utc).timestamp() + 86400, tz=timezone.utc).isoformat()
        with engine.begin() as con:
            con.execute(auth_users.update().where(auth_users.c.id == row.id).values(last_login_at=now))
            con.execute(auth_tokens.insert().values(
                id=token_id, user_id=row.id,
                token_hash=hashlib.sha256(token_id.encode()).hexdigest(),
                issued_at=now, expires_at=expires, revoked=0, user_agent=str(request.headers.get("user-agent", ""))
            ))
        token = create_jwt(row.id, row.email, row.name, row.role)
        return {"id": row.id, "email": row.email, "name": row.name, "role": row.role, "token": token}

    @auth.get("/me")
    def me(request: Request):
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise DomainError("Yetkilendirme başlığı gerekli.", 401, "unauthorized")
        payload = decode_jwt(auth_header.removeprefix("Bearer "))
        if not payload:
            raise DomainError("Geçersiz token.", 401, "invalid_token")
        engine = request.app.state.experiments.engine
        user = engine.connect().execute(select(auth_users).where(auth_users.c.id == payload["sub"])).first()
        if not user:
            raise DomainError("Kullanıcı bulunamadı.", 404, "not_found")
        return {"id": user.id, "email": user.email, "name": user.name, "role": user.role,
                "created_at": user.created_at, "last_login_at": user.last_login_at}

    @auth.patch("/me")
    def update_me(request: Request, body: dict):
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise DomainError("Yetkilendirme başlığı gerekli.", 401, "unauthorized")
        payload = decode_jwt(auth_header.removeprefix("Bearer "))
        if not payload:
            raise DomainError("Geçersiz token.", 401, "invalid_token")
        name = (body.get("name") or "").strip()
        if not name or len(name) < 2:
            raise DomainError("Ad en az 2 karakter olmalı.", 422, "validation_error")
        engine = request.app.state.experiments.engine
        with engine.begin() as con:
            con.execute(auth_users.update().where(auth_users.c.id == payload["sub"]).values(name=name, updated_at=datetime.now(timezone.utc).isoformat()))
        return {"id": payload["sub"], "name": name, "email": None}

    @auth.post("/password")
    def change_password(request: Request, body: dict):
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise DomainError("Yetkilendirme başlığı gerekli.", 401, "unauthorized")
        payload = decode_jwt(auth_header.removeprefix("Bearer "))
        if not payload:
            raise DomainError("Geçersiz token.", 401, "invalid_token")
        old_pw = body.get("old_password", "")
        new_pw = body.get("new_password", "")
        if not old_pw or not new_pw or len(new_pw) < 8:
            raise DomainError("Eski ve yeni şifre gerekli; yeni şifre en az 8 karakter.", 422, "validation_error")
        engine = request.app.state.experiments.engine
        row = engine.connect().execute(select(auth_users).where(auth_users.c.id == payload["sub"])).first()
        if not row or not verify_password(old_pw, row.password_salt, row.password_hash):
            raise DomainError("Eski şifre hatalı.", 401, "invalid_credentials")
        salt, pw_hash = hash_password(new_pw)
        with engine.begin() as con:
            con.execute(auth_users.update().where(auth_users.c.id == row.id).values(password_hash=pw_hash, password_salt=salt))
            con.execute(auth_tokens.update().where(auth_tokens.c.user_id == row.id).values(revoked=1))
        return {"message": "Şifre değiştirildi; eski tokenlar iptal edildi."}

    @auth.post("/email")
    def change_email(request: Request, body: dict):
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise DomainError("Yetkilendirme başlığı gerekli.", 401, "unauthorized")
        payload = decode_jwt(auth_header.removeprefix("Bearer "))
        if not payload:
            raise DomainError("Geçersiz token.", 401, "invalid_token")
        new_email = (body.get("email") or "").strip().lower()
        password = body.get("password", "")
        if not new_email or not password:
            raise DomainError("E-posta ve şifre gerekli.", 422, "validation_error")
        engine = request.app.state.experiments.engine
        row = engine.connect().execute(select(auth_users).where(auth_users.c.id == payload["sub"])).first()
        if not row or not verify_password(password, row.password_salt, row.password_hash):
            raise DomainError("Şifre hatalı.", 401, "invalid_credentials")
        existing = engine.connect().execute(select(auth_users.c.id).where(auth_users.c.email == new_email)).scalar()
        if existing and existing != row.id:
            raise DomainError("Bu e-posta zaten kullanılıyor.", 409, "email_conflict")
        with engine.begin() as con:
            con.execute(auth_users.update().where(auth_users.c.id == row.id).values(email=new_email))
            con.execute(auth_tokens.update().where(auth_tokens.c.user_id == row.id).values(revoked=1))
        return {"id": row.id, "email": new_email}

    @auth.get("/sessions")
    def sessions(request: Request):
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise DomainError("Yetkilendirme başlığı gerekli.", 401, "unauthorized")
        payload = decode_jwt(auth_header.removeprefix("Bearer "))
        if not payload:
            raise DomainError("Geçersiz token.", 401, "invalid_token")
        engine = request.app.state.experiments.engine
        rows = engine.connect().execute(
            select(auth_tokens).where(auth_tokens.c.user_id == payload["sub"]).order_by(auth_tokens.c.issued_at.desc())
        ).mappings().all()
        now_iso = datetime.now(timezone.utc).isoformat()
        return {"sessions": [
            {"id": r.id, "issued_at": r.issued_at, "expires_at": r.expires_at,
             "last_used": r.issued_at, "user_agent": r.user_agent or "",
             "active": r.revoked == 0 and r.expires_at > now_iso}
            for r in rows]}

    @auth.post("/token/revoke")
    def revoke_token(request: Request, body: dict):
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise DomainError("Yetkilendirme başlığı gerekli.", 401, "unauthorized")
        token_id = (body.get("token_id") or "").strip()
        if not token_id:
            raise DomainError("Token kimliği gerekli.", 422, "validation_error")
        engine = request.app.state.experiments.engine
        with engine.begin() as con:
            con.execute(auth_tokens.update().where(auth_tokens.c.id == token_id).values(revoked=1))
        return {"message": "Token iptal edildi."}

    @auth.get("/stats")
    def user_stats(request: Request):
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            raise DomainError("Yetkilendirme başlığı gerekli.", 401, "unauthorized")
        payload = decode_jwt(auth_header.removeprefix("Bearer "))
        if not payload:
            raise DomainError("Geçersiz token.", 401, "invalid_token")
        engine = request.app.state.experiments.engine
        row = engine.connect().execute(select(auth_users).where(auth_users.c.id == payload["sub"])).first()
        if not row:
            raise DomainError("Kullanıcı bulunamadı.", 404, "not_found")
        with engine.begin() as con:
            project_count = con.execute(select(func.count()).select_from(experiments)).scalar() or 0
            backtest_count = con.execute(select(func.count()).select_from(runs).where(runs.c.status == "COMPLETED")).scalar() or 0
        return {
            "id": row.id, "name": row.name, "email": row.email, "role": row.role,
            "created_at": row.created_at, "last_login_at": row.last_login_at,
            "projects": project_count,
            "backtests": backtest_count,
            "live_volume": 0, "public_algorithms": 0, "live_deployments": 0,
            "lines_of_code": 1,
        }

    return auth


async def domain_error(request,exc):
    from ..i18n import translate
    message = translate(str(exc), request.headers.get("accept-language", ""))
    return JSONResponse(status_code=exc.status,content={"error":{"code":exc.code,"message":message},"detail":message})
