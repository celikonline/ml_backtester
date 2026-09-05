import asyncio
import csv
import hmac
import io
import json
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, File, Header, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from sqlalchemy import select

from .schema import ExperimentSpec, SearchSpaceDefinition, WorkspaceCreate, WorkspacePatch, CloneSpec, CompareSpec, DomainError, POLICY, TERMINAL
from .service import ExperimentService
from .models import MODEL_REGISTRY
from .research import registry
from .families import family_registry
from .db import audits


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
    def research_ledger(limit:int=200,workspace_id:str|None=None,s=Depends(service)): return s.ledger(limit,workspace_id)

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

    @api.get("/experiments")
    def list_experiments(q:str="",status:str|None=None,model:str|None=None,optimizer:str|None=None,tag:str|None=None,workspace_id:str|None=None,s=Depends(service)):
        return s.list(q,status,model,optimizer,tag,workspace_id)

    @api.post("/experiments",status_code=201)
    def create(spec:ExperimentSpec,workspace_id:str|None=None,s=Depends(service),who=Depends(actor)): return s.create(spec,who,workspace_id=workspace_id)

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
    def activity(s=Depends(service)):
        with s.engine.connect() as con: return [dict(r) for r in con.execute(select(audits).order_by(audits.c.id.desc()).limit(200)).mappings()]

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
        return nbs.cancel_run(run_id, who)

    @api.get("/workspaces/{workspace_id}/notebook-runs/{run_id}/logs")
    def get_notebook_run_logs(workspace_id:str, run_id:str, after:int=0, nbs=Depends(nb_service)):
        return nbs.get_run_logs(run_id, after)

    @api.get("/workspaces/{workspace_id}/notebook-runs/{run_id}/metrics")
    def get_notebook_run_metrics(workspace_id:str, run_id:str, nbs=Depends(nb_service)):
        return nbs.get_run_metrics(run_id)

    @api.get("/workspaces/{workspace_id}/notebook-runs/{run_id}/artifacts")
    def get_notebook_run_artifacts(workspace_id:str, run_id:str, nbs=Depends(nb_service)):
        return nbs.get_run_artifacts(run_id)

    @api.get("/workspaces/{workspace_id}/notebook-runs/{run_id}/events")
    async def notebook_run_event_stream(workspace_id:str, run_id:str, request:Request, after:int=0, nbs=Depends(nb_service)):
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


async def domain_error(request,exc):
    from ..i18n import translate
    message = translate(str(exc), request.headers.get("accept-language", ""))
    return JSONResponse(status_code=exc.status,content={"error":{"code":exc.code,"message":message},"detail":message})
