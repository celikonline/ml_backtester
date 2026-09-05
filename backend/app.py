from __future__ import annotations

import csv
import io
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .engine import demo_prices, describe, read_prices, run_experiment
from .i18n import translate

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
app = FastAPI(title="Regime Lab", version="1.0.0")


@app.exception_handler(HTTPException)
async def localized_http_error(request: Request, exc: HTTPException):
    lang = request.headers.get("accept-language", "")
    detail = translate(exc.detail, lang) if isinstance(exc.detail, str) else exc.detail
    return JSONResponse(status_code=exc.status_code, content={"detail": detail}, headers=exc.headers)
pool = ThreadPoolExecutor(max_workers=1)
lock = threading.Lock()
jobs = {}


class RunConfig(BaseModel):
    dataset_id: str = "demo"
    interval: Literal["native", "10min", "1h", "4h", "1D"] = "native"
    train_ratio: float = Field(default=0.65, ge=0.50, le=0.75)
    states: int = Field(default=3, ge=2, le=5)
    cost_bps: float = Field(default=0.5, ge=0, le=20)
    capital: float = Field(default=10000, ge=100, le=100000000)


def valid_id(identifier):
    try:
        return str(uuid.UUID(identifier))
    except ValueError:
        raise HTTPException(404, "Kayıt bulunamadı.")


def dataset(identifier):
    if identifier == "demo":
        return demo_prices(), "Sentetik EUR/USD · 4 saat", True
    identifier = valid_id(identifier)
    path = DATA / f"dataset-{identifier}.csv"
    if not path.exists():
        raise HTTPException(404, "Veri seti bulunamadı.")
    meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    return read_prices(path.read_bytes()), meta["name"], False


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/datasets")
def list_datasets():
    df, name, demo = dataset("demo")
    records = [describe(df, "demo", name, demo)]
    for path in DATA.glob("dataset-*.json"):
        records.append(json.loads(path.read_text(encoding="utf-8")))
    return records


@app.post("/api/datasets")
async def upload_dataset(file: UploadFile):
    raw = await file.read(25 * 1024 * 1024 + 1)
    await file.close()
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(413, "En fazla 25 MB CSV yükleyebilirsiniz.")
    try:
        df = read_prices(raw)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    identifier = str(uuid.uuid4())
    meta = describe(df, identifier, (file.filename or "Veri seti.csv")[:150])
    df.to_csv(DATA / f"dataset-{identifier}.csv")
    (DATA / f"dataset-{identifier}.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return meta


@app.get("/api/sample.csv")
def sample():
    return Response(demo_prices().to_csv(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="sentetik-eurusd.csv"'})


@app.get("/api/sample-external.csv")
def sample_external():
    """Synthetic import template for the lagged macro/cross-asset contract."""
    df = demo_prices()
    bars = pd.Series(range(len(df)), index=df.index, dtype=float)
    df["macro__policy_rate"] = 4.5 + (bars // 180) * .25
    df["macro__policy_rate__available_at"] = df.index - pd.Timedelta(hours=1)
    df["cross_asset__dxy"] = 100 * (df.close / df.close.iloc[0])
    df["cross_asset__dxy__available_at"] = df.index - pd.Timedelta(hours=1)
    return Response(df.to_csv(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="sentetik-lagli-harici-seriler.csv"'})


def execute(identifier, df, config):
    def progress(percent, message):
        with lock:
            if jobs[identifier].get("cancel_requested"):
                raise InterruptedError("Çalıştırma iptal edildi.")
            jobs[identifier].update(status="running", progress=percent, message=message)
            jobs[identifier]["logs"].append({"time": datetime.now(timezone.utc).isoformat(), "message": message})
    try:
        result = run_experiment(df, config, progress)
        progress(100, "Deney tamamlandı")
        with lock:
            jobs[identifier].update(status="completed", result=result)
    except InterruptedError as exc:
        with lock:
            jobs[identifier].update(status="cancelled", message=str(exc))
    except Exception as exc:
        with lock:
            jobs[identifier].update(status="failed", message=str(exc))
    finally:
        with lock:
            snapshot = dict(jobs[identifier])
        (DATA / f"run-{identifier}.json").write_text(json.dumps(snapshot, ensure_ascii=False, allow_nan=False), encoding="utf-8")


@app.post("/api/runs", status_code=202)
def create_run(config: RunConfig):
    df, name, demo = dataset(config.dataset_id)
    with lock:
        if any(j["status"] in ["queued", "running"] for j in jobs.values()):
            raise HTTPException(409, "Zaten çalışan bir deney var. Tamamlanmasını bekleyin veya iptal edin.")
        identifier = str(uuid.uuid4())
        job = {"id": identifier, "status": "queued", "progress": 0, "message": "Çalıştırma hazırlanıyor", "logs": [],
               "created_at": datetime.now(timezone.utc).isoformat(), "config": config.model_dump(), "dataset_name": name, "demo": demo}
        jobs[identifier] = job
        response = dict(job)
    pool.submit(execute, identifier, df, config.model_dump())
    return response


@app.get("/api/runs")
def list_runs():
    stored = {}
    for path in DATA.glob("run-*.json"):
        item = json.loads(path.read_text(encoding="utf-8"))
        stored[item["id"]] = {k: v for k, v in item.items() if k != "result"}
    with lock:
        stored.update({key: {k: v for k, v in j.items() if k != "result"} for key, j in jobs.items()})
    return sorted(stored.values(), key=lambda j: j["created_at"], reverse=True)


@app.get("/api/runs/{identifier}")
def get_run(identifier: str):
    identifier = valid_id(identifier)
    with lock:
        if identifier in jobs:
            return dict(jobs[identifier])
    path = DATA / f"run-{identifier}.json"
    if not path.exists():
        raise HTTPException(404, "Deney bulunamadı.")
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/api/runs/{identifier}/cancel")
def cancel_run(identifier: str):
    identifier = valid_id(identifier)
    with lock:
        if identifier not in jobs or jobs[identifier]["status"] not in ["queued", "running"]:
            raise HTTPException(409, "Bu deney şu anda çalışmıyor.")
        jobs[identifier]["cancel_requested"] = True
        jobs[identifier]["message"] = "Mevcut eğitim adımından sonra iptal edilecek"
    return {"status": "cancelling"}


@app.get("/api/runs/{identifier}/export")
def export_run(identifier: str):
    job = get_run(identifier)
    if job["status"] != "completed":
        raise HTTPException(409, "Önce deney tamamlanmalı.")
    out = io.StringIO()
    rows = job["result"]["curve"]
    writer = csv.DictWriter(out, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return Response(out.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="regime-lab-{identifier[:8]}.csv"'})


@app.get("/api/project")
def project():
    # Only names and cell counts are exposed; notebook source may contain credentials.
    return {"notebooks": [{"name": p.name, "cells": len(json.loads(p.read_text(encoding="utf-8"))["cells"])} for p in ROOT.glob("*.ipynb")],
            "scope": "OHLC → teknik özellikler → 3 uzman → Gaussian HMM → doğrulamada ağırlık seçimi → maliyetli test"}


DIST = ROOT / "frontend" / "dist"
from .platform.api import router as experiment_router, domain_error
from .platform.schema import DomainError
app.add_exception_handler(DomainError, domain_error)
app.include_router(experiment_router(dataset, list_datasets))

if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/")
    def index():
        return FileResponse(DIST / "index.html")
