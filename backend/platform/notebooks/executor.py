"""
Notebook Lab — Papermill executor.

Runs a .ipynb file in a subprocess using papermill (or nbclient).
Emits progress events for each cell via a callback.
Enforces timeout and cancellation via cancel_event.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable

# Sentinel strings for masking secrets in logs
_SECRET_MASK = "***REDACTED***"
_SECRET_KEY_PATTERN = re.compile(
    r'(api[_\-]?key|token|password|secret|fred_api_key|data_provider_key)',
    re.IGNORECASE,
)


def _mask_secrets(text: str, secret_keys: list[str]) -> str:
    """Replace known secret values with the redaction marker."""
    for key in secret_keys:
        # Match assignment patterns
        text = re.sub(
            rf'({re.escape(key)}\s*[=:]\s*)["\'][^"\']+["\']',
            rf'\1"{_SECRET_MASK}"',
            text, flags=re.IGNORECASE,
        )
    return text


def _build_injected_params(
    run_id: str,
    workspace_id: str,
    experiment_id: str | None,
    dataset_snapshot_id: str | None,
    input_dir: str | None,
    artifact_dir: str,
    extra_params: dict[str, Any],
) -> dict[str, Any]:
    base = {
        "WORKSPACE_ID": workspace_id,
        "EXPERIMENT_ID": experiment_id,
        "DATASET_SNAPSHOT_ID": dataset_snapshot_id,
        "INPUT_DIR": input_dir or "",
        "ARTIFACT_DIR": artifact_dir,
        "RUN_ID": run_id,
    }
    base.update(extra_params)
    return base


def execute_notebook(
    *,
    notebook_path: Path,
    output_path: Path,
    parameters: dict[str, Any],
    env_vars: dict[str, str],
    timeout_seconds: int,
    cancel_event: threading.Event,
    emit: Callable[[str, dict], None],
    artifact_dir: Path,
    run_id: str,
    secret_keys: list[str] | None = None,
) -> dict[str, Any]:
    """
    Execute notebook_path with papermill.
    Returns {exit_code, error_type, error_message, metrics}.
    """
    secret_keys = secret_keys or []
    artifact_dir.mkdir(parents=True, exist_ok=True)

    # Write parameters json for papermill
    params_file = artifact_dir / "nb_params.json"
    params_file.write_text(json.dumps(parameters, ensure_ascii=False), encoding="utf-8")

    # Build papermill command
    cmd = [
        sys.executable, "-m", "papermill",
        str(notebook_path),
        str(output_path),
        "-f", str(params_file),
        "--no-progress-bar",
        "--kernel", "python3",
        "--report-mode",
    ]

    combined_env = {**os.environ.copy(), **env_vars}
    root_str = str(Path(__file__).resolve().parents[3])
    cur_pp = combined_env.get("PYTHONPATH", "")
    combined_env["PYTHONPATH"] = f"{root_str}{os.pathsep}{cur_pp}" if cur_pp else root_str
    combined_env["ARTIFACT_DIR"] = str(artifact_dir)
    combined_env["RUN_ID"] = run_id

    emit("notebook.run.started", {"run_id": run_id, "notebook": str(notebook_path)})

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=combined_env,
            text=True,
            bufsize=1,
        )

        log_lines: list[str] = []
        cell_pattern = re.compile(r"Executing cell (\d+)")
        error_pattern = re.compile(r"(?:Exception|Error|Traceback).*", re.IGNORECASE)

        def reader():
            assert proc.stdout
            for raw_line in proc.stdout:
                line = _mask_secrets(raw_line.rstrip(), secret_keys)
                log_lines.append(line)
                m = cell_pattern.search(line)
                if m:
                    emit("notebook.cell.started", {
                        "run_id": run_id,
                        "cell_index": int(m.group(1)),
                    })

        reader_thread = threading.Thread(target=reader, daemon=True)
        reader_thread.start()

        start = time.monotonic()
        while proc.poll() is None:
            if cancel_event.is_set():
                proc.kill()
                emit("notebook.run.cancelled", {"run_id": run_id})
                return {
                    "exit_code": -1,
                    "error_type": "CANCELLED",
                    "error_message": "Kullanıcı tarafından iptal edildi.",
                    "metrics": {},
                    "logs": log_lines,
                }
            elapsed = time.monotonic() - start
            if elapsed > timeout_seconds:
                proc.kill()
                emit("notebook.run.timeout", {"run_id": run_id, "elapsed_seconds": elapsed})
                return {
                    "exit_code": -2,
                    "error_type": "TIMEOUT",
                    "error_message": f"Notebook {timeout_seconds}s süre sınırını aştı.",
                    "metrics": {},
                    "logs": log_lines,
                }
            time.sleep(0.5)

        reader_thread.join(timeout=5)
        exit_code = proc.returncode

        # Parse metrics.json if it exists
        metrics = _load_metrics(artifact_dir)

        if exit_code == 0:
            emit("notebook.run.completed", {"run_id": run_id, "metrics": metrics})
            return {"exit_code": 0, "error_type": None, "error_message": None, "metrics": metrics, "logs": log_lines}
        else:
            error_msg = next((l for l in reversed(log_lines) if error_pattern.search(l)), log_lines[-1] if log_lines else "Bilinmeyen hata")
            emit("notebook.run.failed", {"run_id": run_id, "error": error_msg})
            return {
                "exit_code": exit_code,
                "error_type": "EXECUTION_ERROR",
                "error_message": error_msg[:2000],
                "metrics": metrics,
                "logs": log_lines,
            }

    except FileNotFoundError:
        # papermill not installed — fallback to nbclient
        return _execute_with_nbclient(
            notebook_path=notebook_path,
            output_path=output_path,
            parameters=parameters,
            env_vars=combined_env,
            timeout_seconds=timeout_seconds,
            cancel_event=cancel_event,
            emit=emit,
            artifact_dir=artifact_dir,
            run_id=run_id,
        )
    except Exception as exc:
        emit("notebook.run.failed", {"run_id": run_id, "error": str(exc)})
        return {
            "exit_code": -99,
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:2000],
            "metrics": {},
            "logs": [],
        }


def _execute_with_nbclient(
    *,
    notebook_path: Path,
    output_path: Path,
    parameters: dict[str, Any],
    env_vars: dict[str, str],
    timeout_seconds: int,
    cancel_event: threading.Event,
    emit: Callable[[str, dict], None],
    artifact_dir: Path,
    run_id: str,
) -> dict[str, Any]:
    """Fallback nbclient execution when papermill is unavailable."""
    try:
        import nbformat
        from nbclient import NotebookClient

        nb = nbformat.read(str(notebook_path), as_version=4)

        # Inject parameters cell
        param_cell_src = "\n".join(f"{k} = {json.dumps(v)}" for k, v in parameters.items())
        param_cell = nbformat.v4.new_code_cell(source=param_cell_src)
        param_cell["metadata"]["tags"] = ["injected-parameters"]
        # insert after first parameters-tagged cell or at top
        inject_at = 0
        for i, cell in enumerate(nb.cells):
            if "parameters" in cell.get("metadata", {}).get("tags", []):
                inject_at = i + 1
                break
        nb.cells.insert(inject_at, param_cell)

        cell_count = len(nb.cells)
        env_bak = dict(os.environ)
        os.environ.update(env_vars)

        client = NotebookClient(
            nb,
            timeout=timeout_seconds,
            kernel_name="python3",
        )

        try:
            client.execute()
        finally:
            os.environ.clear()
            os.environ.update(env_bak)

        nbformat.write(nb, str(output_path))
        metrics = _load_metrics(artifact_dir)
        emit("notebook.run.completed", {"run_id": run_id, "metrics": metrics})
        return {"exit_code": 0, "error_type": None, "error_message": None, "metrics": metrics, "logs": []}

    except Exception as exc:
        emit("notebook.run.failed", {"run_id": run_id, "error": str(exc)})
        return {
            "exit_code": -99,
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:2000],
            "metrics": {},
            "logs": [],
        }


def _load_metrics(artifact_dir: Path) -> dict[str, Any]:
    metrics_path = artifact_dir / "metrics.json"
    if metrics_path.exists():
        try:
            return json.loads(metrics_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}
