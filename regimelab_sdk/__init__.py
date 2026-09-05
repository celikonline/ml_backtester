"""
RegimeLab Notebook SDK

Minimal SDK for use inside notebooks running in the RegimeLab Notebook Lab.
Reads context from environment variables injected by the worker and writes
outputs to ARTIFACT_DIR for collection by the artifact collector.

Usage inside a notebook:

    from regimelab_sdk import run

    run.log_metric("sharpe", 1.87)
    run.log_param("model", "xgboost")
    run.log_artifact("equity_curve.png")
    run.log_message("Training complete")
"""
from __future__ import annotations
import json
import os
import shutil
from pathlib import Path
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunContext:
    """Provides metric/param/artifact logging for a notebook run."""

    def __init__(self):
        self._artifact_dir = Path(os.environ.get("ARTIFACT_DIR", "./artifacts"))
        self._artifact_dir.mkdir(parents=True, exist_ok=True)
        self._run_id = os.environ.get("RUN_ID", "local")
        self._workspace_id = os.environ.get("WORKSPACE_ID", "")
        self._experiment_id = os.environ.get("EXPERIMENT_ID", "")
        self._dataset_snapshot_id = os.environ.get("DATASET_SNAPSHOT_ID", "")
        self._metrics: dict = {}
        self._params: dict = {}
        self._messages: list[str] = []

    @property
    def artifact_dir(self) -> Path:
        return self._artifact_dir

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def workspace_id(self) -> str:
        return self._workspace_id

    @property
    def experiment_id(self) -> str:
        return self._experiment_id

    @property
    def dataset_snapshot_id(self) -> str:
        return self._dataset_snapshot_id

    def log_metric(self, name: str, value: float | int) -> None:
        """Log a scalar metric. Written to metrics.json on flush."""
        self._metrics[name] = value
        self._flush_metrics()

    def log_param(self, name: str, value) -> None:
        """Log a run parameter."""
        self._params[name] = value
        self._flush_params()

    def log_artifact(self, path: str | Path) -> None:
        """Copy a file into ARTIFACT_DIR so it is collected after the run."""
        src = Path(path)
        if not src.exists():
            print(f"[regimelab_sdk] WARNING: artifact {path} not found, skipping.")
            return
        dest = self._artifact_dir / src.name
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        print(f"[regimelab_sdk] Artifact registered: {dest.name}")

    def log_message(self, message: str) -> None:
        """Log a free-text message that appears in the run event stream."""
        self._messages.append(f"[{_now()}] {message}")
        print(f"[regimelab_sdk] {message}")

    def _flush_metrics(self):
        metrics_path = self._artifact_dir / "metrics.json"
        metrics_path.write_text(
            json.dumps(self._metrics, ensure_ascii=False, allow_nan=False),
            encoding="utf-8",
        )

    def _flush_params(self):
        params_path = self._artifact_dir / "params.json"
        params_path.write_text(
            json.dumps(self._params, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    def get_input_path(self, filename: str = "dataset.parquet") -> Path:
        """Return path to the mounted input file (dataset snapshot)."""
        input_dir = Path(os.environ.get("INPUT_DIR", "./input"))
        return input_dir / filename

    def summary(self) -> dict:
        return {
            "run_id": self._run_id,
            "workspace_id": self._workspace_id,
            "experiment_id": self._experiment_id,
            "dataset_snapshot_id": self._dataset_snapshot_id,
            "metrics": self._metrics,
            "params": self._params,
            "artifact_dir": str(self._artifact_dir),
        }


# Module-level singleton — import and use directly
run = RunContext()

__all__ = ["run", "RunContext"]
