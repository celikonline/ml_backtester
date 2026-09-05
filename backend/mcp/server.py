"""MCP adapter: all validation, persistence and orchestration remain in REST services."""
import json
import os
import uuid
import httpx
from mcp.server.fastmcp import FastMCP
from backend.platform.schema import ExperimentSpec, SearchSpaceDefinition
from backend.platform.api import DomainError

mcp=FastMCP("RegimeLab")
BASE=os.environ.get("REGIMELAB_API_URL","http://127.0.0.1:8000/api/v1").rstrip("/")

async def call(method,path,body=None,key=None,workspace_id:str|None=None):
    headers={"X-RegimeLab-Source":"MCP","X-Request-ID":str(uuid.uuid4())}
    if os.environ.get("REGIMELAB_API_KEY"): headers["Authorization"]="Bearer "+os.environ["REGIMELAB_API_KEY"]
    if key: headers["Idempotency-Key"]=key
    headers["X-Workspace-Id"]=workspace_id or ""
    async with httpx.AsyncClient(timeout=30,trust_env=False) as client:
        response=await client.request(method,BASE+path,json=body,headers=headers)
        if response.status_code >= 400:
            try:
                err=response.json()
                raise DomainError(err.get("detail",err.get("error",{}).get("message","Bilinmeyen hata")), response.status_code, err.get("code","api_error"))
            except Exception:
                raise DomainError(f"HTTP {response.status_code}", response.status_code, "api_error")
        return response.json()

@mcp.tool()
async def list_workspaces(include_archived:bool=False)->list:
    return await call("GET",f"/workspaces?include_archived={str(include_archived).lower()}")

@mcp.tool()
async def get_workspace(workspace_id:str)->dict:
    return await call("GET",f"/workspaces/{workspace_id}")

@mcp.tool()
async def create_workspace(name:str,description:str="",market:str="",base_currency:str="",timezone:str="UTC")->dict:
    """Create a real workspace record; research scope switches to it explicitly."""
    return await call("POST","/workspaces",{"name":name,"description":description,"market":market,"base_currency":base_currency,"timezone":timezone})

@mcp.tool()
async def patch_workspace(identifier:str,body:dict)->dict:
    """Patch a workspace."""
    return await call("PATCH",f"/workspaces/{identifier}",body)

@mcp.tool()
async def archive_workspace(identifier:str)->dict:
    """Archive a workspace."""
    return await call("POST",f"/workspaces/{identifier}/archive")

@mcp.tool()
async def create_experiment(specification:ExperimentSpec)->dict:
    """Create a draft using the same versioned specification as REST/UI; does not run."""
    return await call("POST","/experiments",specification.model_dump())

@mcp.tool()
async def validate_experiment_spec(specification:ExperimentSpec)->dict:
    """Validate and estimate policy/risk without creating or running an experiment."""
    return await call("POST","/research/estimate",specification.model_dump())

@mcp.tool()
async def list_search_spaces()->list:
    return await call("GET","/search-spaces")

@mcp.tool()
async def create_search_space(definition:SearchSpaceDefinition)->dict:
    """Create a versioned optimizer domain object shared by UI, REST and MCP."""
    return await call("POST","/search-spaces",definition.model_dump())

@mcp.tool()
async def get_research_budget(workspace_id:str|None=None)->dict:
    suffix=f"?workspace_id={workspace_id}" if workspace_id else ""
    return await call("GET",f"/research/budget{suffix}")

@mcp.tool()
async def get_research_ledger(limit:int=200)->list:
    """Read the persistent research trial ledger (budget consumption history)."""
    return await call("GET",f"/research/ledger?limit={limit}")

@mcp.tool()
async def get_test_seal_status(experiment_id:str)->dict:
    return await call("GET",f"/experiments/{experiment_id}/seal")

@mcp.tool()
async def invalidate_test_seal(experiment_id:str,reason:str)->dict:
    """Burn the sealed test for an experiment's dataset; further runs need an explicit rotation."""
    return await call("POST",f"/experiments/{experiment_id}/seal/invalidate",{"reason":reason})

@mcp.tool()
async def rotate_test_seal(experiment_id:str,reason:str)->dict:
    """Open a new seal epoch for an experiment's dataset; the old epoch stays auditable."""
    return await call("POST",f"/experiments/{experiment_id}/seal/rotate",{"reason":reason})

@mcp.tool()
async def run_experiment(experiment_id:str,idempotency_key:str)->dict:
    """Queue a frozen experiment once; returns immediately with a durable job ID."""
    return await call("POST",f"/experiments/{experiment_id}/run",key=idempotency_key)

@mcp.tool()
async def clone_experiment(experiment_id:str,name:str)->dict:
    return await call("POST",f"/experiments/{experiment_id}/clone",{"name":name})

@mcp.tool()
async def cancel_experiment(experiment_id:str)->dict:
    return await call("POST",f"/experiments/{experiment_id}/cancel")

@mcp.tool()
async def list_experiments(workspace_id:str|None=None)->list:
    suffix=f"?workspace_id={workspace_id}" if workspace_id else ""
    return await call("GET",f"/experiments{suffix}")

@mcp.tool()
async def get_search_space(identifier:str)->dict:
    """Get a search space by identifier."""
    return await call("GET",f"/search-spaces/{identifier}")

@mcp.tool()
async def get_models()->list:
    """Get model registry."""
    return await call("GET","/models")

@mcp.tool()
async def get_feature_families()->list:
    """Get feature families."""
    return await call("GET","/feature-families")

@mcp.tool()
async def get_capabilities()->dict:
    """Get MCP/REST capabilities."""
    return await call("GET","/capabilities")

@mcp.tool()
async def get_specification_schema()->dict:
    """Get experiment specification schema."""
    return await call("GET","/specification/schema")

@mcp.tool()
async def get_experiment(experiment_id:str)->dict:
    return await call("GET",f"/experiments/{experiment_id}")

@mcp.tool()
async def get_experiment_status(experiment_id:str)->dict:
    return await call("GET",f"/experiments/{experiment_id}/status")

@mcp.tool()
async def compare_experiments(experiment_ids:list[str])->dict:
    return await call("POST","/experiments/compare",{"experiment_ids":experiment_ids})

@mcp.tool()
async def search_datasets()->list:
    return await call("GET","/datasets")

@mcp.tool()
async def inspect_dataset(dataset_id:str)->dict:
    return await call("GET",f"/datasets/{dataset_id}")

@mcp.tool()
async def list_features()->list:
    return await call("GET","/features")

@mcp.tool()
async def get_optimization_result(experiment_id:str)->dict:
    return await call("GET",f"/experiments/{experiment_id}/optimization")

@mcp.tool()
async def get_candidates(experiment_id:str)->list:
    return await call("GET",f"/experiments/{experiment_id}/candidates")

@mcp.tool()
async def get_experiment_lineage(experiment_id:str)->list:
    return await call("GET",f"/experiments/{experiment_id}/lineage")

@mcp.tool()
async def get_feature_analysis(experiment_id:str)->dict:
    return await call("GET",f"/experiments/{experiment_id}/feature-analysis")

@mcp.tool()
async def get_feature_intelligence(experiment_id:str)->dict:
    return await call("GET",f"/experiments/{experiment_id}/feature-intelligence")

@mcp.tool()
async def get_backtest_results(experiment_id:str)->dict:
    return await call("GET",f"/experiments/{experiment_id}/backtest")

@mcp.tool()
async def patch_experiment(experiment_id:str,specification:ExperimentSpec)->dict:
    """Patch an experiment specification (only DRAFT experiments)."""
    return await call("PATCH",f"/experiments/{experiment_id}",specification.model_dump())

@mcp.tool()
async def get_seal_history(experiment_id:str)->list:
    """Get the seal history for an experiment's dataset."""
    return await call("GET",f"/experiments/{experiment_id}/seal/history")

@mcp.tool()
async def get_logs(experiment_id:str,after:int=0)->list:
    """Get experiment execution logs."""
    return await call("GET",f"/experiments/{experiment_id}/logs?after={after}")

@mcp.tool()
async def get_metrics(experiment_id:str)->dict:
    """Get validation and test metrics for a completed experiment."""
    return await call("GET",f"/experiments/{experiment_id}/metrics")

@mcp.tool()
async def get_artifacts(experiment_id:str)->list:
    return await call("GET",f"/experiments/{experiment_id}/artifacts")

@mcp.tool()
async def get_experiment_result(experiment_id:str)->dict:
    """Get experiment result (only COMPLETED experiments)."""
    return await call("GET",f"/experiments/{experiment_id}/result")

@mcp.tool()
async def get_feature_evaluations(experiment_id:str)->list:
    """Get feature evaluation history."""
    return await call("GET",f"/experiments/{experiment_id}/feature-evaluations")

@mcp.tool()
async def get_candidate(experiment_id:str,identifier:str)->dict:
    """Get a specific candidate."""
    return await call("GET",f"/experiments/{experiment_id}/candidates/{identifier}")

@mcp.tool()
async def get_pareto(experiment_id:str)->dict:
    """Get Pareto front for optimization."""
    return await call("GET",f"/experiments/{experiment_id}/pareto")

@mcp.tool()
async def get_equity(experiment_id:str)->dict:
    """Get equity curve."""
    return await call("GET",f"/experiments/{experiment_id}/equity")

@mcp.tool()
async def list_assistants()->list:
    """List AI assistants (templates + configured)."""
    return await call("GET","/assistants")

@mcp.tool()
async def create_assistant(config:dict)->dict:
    """Create a new AI assistant configuration."""
    return await call("POST","/assistants",config)

@mcp.tool()
async def update_assistant(identifier:str,config:dict)->dict:
    """Update an existing AI assistant configuration."""
    return await call("PUT",f"/assistants/{identifier}",config)

@mcp.tool()
async def clone_assistant(identifier:str,name:str)->dict:
    """Clone an AI assistant."""
    return await call("POST",f"/assistants/{identifier}/clone",{"name":name})

@mcp.tool()
async def list_tasks()->list:
    """List AI assistant tasks."""
    return await call("GET","/assistant-tasks")

@mcp.tool()
async def get_task(identifier:str)->dict:
    """Get a specific AI task."""
    return await call("GET",f"/assistant-tasks/{identifier}")

@mcp.tool()
async def cancel_task(identifier:str)->dict:
    """Cancel an AI task."""
    return await call("POST",f"/assistant-tasks/{identifier}/cancel")

@mcp.tool()
async def run_task(body:dict)->dict:
    """Run an AI assistant task."""
    return await call("POST","/assistant-tasks",body)

@mcp.resource("regimelab://experiments/{experiment_id}")
async def experiment_resource(experiment_id:str)->str:
    return json.dumps(await get_experiment(experiment_id))

@mcp.resource("regimelab://features")
async def feature_resource()->str:
    return json.dumps(await list_features())

# ── Notebook Lab MCP Tools ───────────────────────────────────────────────

@mcp.tool()
async def list_notebooks(workspace_id:str, include_archived:bool=False)->list:
    """List all notebooks in a workspace. Use workspace_id from list_workspaces."""
    return await call("GET", f"/workspaces/{workspace_id}/notebooks?include_archived={str(include_archived).lower()}")

@mcp.tool()
async def get_notebook(workspace_id:str, notebook_id:str)->dict:
    """Get notebook details including versions and current status."""
    return await call("GET", f"/workspaces/{workspace_id}/notebooks/{notebook_id}")

@mcp.tool()
async def list_notebook_runs(workspace_id:str, notebook_id:str|None=None, experiment_id:str|None=None, limit:int=20)->list:
    """List notebook runs for a workspace, optionally filtered by notebook or experiment."""
    qs = f"?limit={limit}"
    if notebook_id: qs += f"&notebook_id={notebook_id}"
    if experiment_id: qs += f"&experiment_id={experiment_id}"
    return await call("GET", f"/workspaces/{workspace_id}/notebook-runs{qs}")

@mcp.tool()
async def get_notebook_run(workspace_id:str, run_id:str)->dict:
    """Get details of a specific notebook run including status, metrics and artifacts."""
    return await call("GET", f"/workspaces/{workspace_id}/notebook-runs/{run_id}")

@mcp.tool()
async def get_notebook_metrics(workspace_id:str, run_id:str)->dict:
    """Get the metrics logged by a completed notebook run."""
    return await call("GET", f"/workspaces/{workspace_id}/notebook-runs/{run_id}/metrics")

@mcp.tool()
async def get_notebook_artifacts(workspace_id:str, run_id:str)->list:
    """List artifacts produced by a notebook run."""
    return await call("GET", f"/workspaces/{workspace_id}/notebook-runs/{run_id}/artifacts")

@mcp.tool()
async def run_notebook(
    workspace_id:str,
    notebook_id:str,
    experiment_id:str|None=None,
    dataset_snapshot_id:str|None=None,
    environment_id:str|None=None,
    parameters:dict|None=None,
    network_mode:str="SNAPSHOT_ONLY",
)->dict:
    """Queue an approved notebook for async execution. Returns run_id immediately (status=QUEUED)."""
    body = {
        "notebook_id": notebook_id,
        "experiment_id": experiment_id,
        "dataset_snapshot_id": dataset_snapshot_id,
        "environment_id": environment_id,
        "parameters": parameters or {},
        "network_mode": network_mode,
    }
    return await call("POST", f"/workspaces/{workspace_id}/notebook-runs", body)

@mcp.tool()
async def cancel_notebook_run(workspace_id:str, run_id:str)->dict:
    """Request cancellation of a running notebook job."""
    return await call("POST", f"/workspaces/{workspace_id}/notebook-runs/{run_id}/cancel")

@mcp.tool()
async def get_activity()->list:
    """Get recent activity log."""
    return await call("GET","/activity")

if __name__=="__main__": mcp.run(transport="stdio")
