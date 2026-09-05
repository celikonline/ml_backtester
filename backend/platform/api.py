import asyncio
import csv
import hmac
import io
import json
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from sqlalchemy import select

from .schema import ExperimentSpec, SearchSpaceDefinition, CloneSpec, CompareSpec, DomainError, POLICY, TERMINAL
from .service import ExperimentService
from .models import MODEL_REGISTRY, is_available
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


def router(dataset_loader, datasets_list):
    @asynccontextmanager
    async def lifespan(app):
        if not getattr(app.state,"experiments",None): app.state.experiments=ExperimentService(dataset_loader=dataset_loader)
        app.state.experiments.start()
        yield
        app.state.experiments.close()

    api=APIRouter(prefix="/api/v1",dependencies=[Depends(actor)],lifespan=lifespan)

    @api.get("/capabilities")
    def capabilities():
        return {"schema_version":"1.0","models":[{"id":k,**v,"status":"implemented" if is_available(k) else "requires_package"} for k,v in MODEL_REGISTRY.items()],
            "policy":POLICY,"auth_mode":"api_key" if os.environ.get("REGIMELAB_API_KEY") else "local_single_user",
            "unavailable":[{"name":n,"status":"requires_data"} for n in ["ALFRED / vintage macro","FX IV surface","OIS / forward points","Order flow / microstructure"]]+
                          [{"name":n,"status":"planned"} for n in ["TFT / LSTM","Optuna / full genome","Stacking","LLM prompt builder","Champion approval / RBAC"]]}

    @api.get("/specification/schema")
    def schema(): return ExperimentSpec.model_json_schema()

    @api.post("/research/estimate")
    def research_estimate(spec:ExperimentSpec, snapshot_id:str|None=None, s=Depends(service)):
        return s.estimate(spec, snapshot_id)

    @api.get("/research/budget")
    def research_budget(s=Depends(service)): return s.budget_status()

    @api.get("/search-spaces")
    def list_search_spaces(s=Depends(service)): return s.list_search_spaces()

    @api.post("/search-spaces", status_code=201)
    def create_search_space(body:SearchSpaceDefinition,s=Depends(service),who=Depends(actor)): return s.create_search_space(body,who)

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
    def models(): return [{"id":k,**v,"status":"implemented" if is_available(k) else "requires_package"} for k,v in MODEL_REGISTRY.items()]

    @api.get("/experiments")
    def list_experiments(q:str="",status:str|None=None,model:str|None=None,optimizer:str|None=None,tag:str|None=None,s=Depends(service)):
        return s.list(q,status,model,optimizer,tag)

    @api.post("/experiments",status_code=201)
    def create(spec:ExperimentSpec,s=Depends(service),who=Depends(actor)): return s.create(spec,who)

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

    @api.get("/activity")
    def activity(s=Depends(service)):
        with s.engine.connect() as con: return [dict(r) for r in con.execute(select(audits).order_by(audits.c.id.desc()).limit(200)).mappings()]

    return api


async def domain_error(request,exc):
    from ..i18n import translate
    message = translate(str(exc), request.headers.get("accept-language", ""))
    return JSONResponse(status_code=exc.status,content={"error":{"code":exc.code,"message":message},"detail":message})
