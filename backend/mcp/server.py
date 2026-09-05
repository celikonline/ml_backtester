"""MCP adapter: all validation, persistence and orchestration remain in REST services."""
import json
import os
import uuid
import httpx
from mcp.server.fastmcp import FastMCP
from backend.platform.schema import ExperimentSpec, SearchSpaceDefinition

mcp=FastMCP("RegimeLab")
BASE=os.environ.get("REGIMELAB_API_URL","http://127.0.0.1:8000/api/v1").rstrip("/")

async def call(method,path,body=None,key=None):
    headers={"X-RegimeLab-Source":"MCP","X-Request-ID":str(uuid.uuid4())}
    if os.environ.get("REGIMELAB_API_KEY"): headers["Authorization"]="Bearer "+os.environ["REGIMELAB_API_KEY"]
    if key: headers["Idempotency-Key"]=key
    async with httpx.AsyncClient(timeout=30,trust_env=False) as client:
        response=await client.request(method,BASE+path,json=body,headers=headers)
        response.raise_for_status()
        return response.json()

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
async def get_research_budget()->dict:
    return await call("GET","/research/budget")

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
async def list_experiments()->list:
    return await call("GET","/experiments")

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
async def get_backtest_results(experiment_id:str)->dict:
    return await call("GET",f"/experiments/{experiment_id}/backtest")

@mcp.tool()
async def get_regime_analysis(experiment_id:str)->dict:
    return await call("GET",f"/experiments/{experiment_id}/regimes")

@mcp.tool()
async def get_artifacts(experiment_id:str)->list:
    return await call("GET",f"/experiments/{experiment_id}/artifacts")

@mcp.resource("regimelab://experiments/{experiment_id}")
async def experiment_resource(experiment_id:str)->str:
    return json.dumps(await get_experiment(experiment_id))

@mcp.resource("regimelab://features")
async def feature_resource()->str:
    return json.dumps(await list_features())

if __name__=="__main__": mcp.run(transport="stdio")
