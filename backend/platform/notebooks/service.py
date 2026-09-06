"""
Notebook Lab — NotebookService.

Handles:
  - Notebook registry CRUD (workspace-aware)
  - Version management
  - Run lifecycle (create, queue, cancel)
  - Environment registry
  - Workspace secrets (simple XOR-based obfuscation for local mode)
  - Audit logging
"""
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from backend.platform.db import (
    STORAGE, audits, connect, migrate, notebook_environments,
    notebook_run_events, notebook_runs, notebook_versions, notebooks,
    workspace_secrets, workspaces, snapshots, experiments,
)
from backend.platform.schema import DomainError
from backend.platform.scope import workspace_scope


DEFAULT_QUANT_ENV = {
    "environment_code": "regimelab-quant-1.0",
    "name": "Quant Python 3.12",
    "python_version": "3.12",
    "image_ref": None,
    "requirements": "\n".join([
        "numpy", "pandas", "scipy", "scikit-learn",
        "xgboost", "lightgbm", "optuna", "hmmlearn",
        "yfinance", "pandas-datareader", "matplotlib",
        "joblib", "pyarrow", "papermill", "nbclient", "nbformat",
    ]),
    "supports_gpu": 0,
    "status": "ACTIVE",
}

NB_TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "POLICY_REJECTED"}
NB_RUN_POLICY = {
    "max_runtime_minutes": int(os.environ.get("NB_MAX_RUNTIME_MINUTES", "60")),
    "max_memory_mb": int(os.environ.get("NB_MAX_MEMORY_MB", "8192")),
    "max_artifact_count": 200,
}


def _now(): return datetime.now(timezone.utc).isoformat()
def _uid(): return str(uuid.uuid4())


def _xor_obfuscate(value: str) -> str:
    """Very lightweight reversible obfuscation for local mode (not cryptographic)."""
    key = b"regimelab-local-secret"
    encoded = value.encode("utf-8")
    result = bytes(b ^ key[i % len(key)] for i, b in enumerate(encoded))
    return base64.b64encode(result).decode("ascii")


def _xor_deobfuscate(enc: str) -> str:
    key = b"regimelab-local-secret"
    raw = base64.b64decode(enc.encode("ascii"))
    result = bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))
    return result.decode("utf-8")


class NotebookService:
    def __init__(self, url=None, storage=None, initialize=True):
        self.storage = Path(storage or STORAGE).resolve()
        self.storage.mkdir(parents=True, exist_ok=True)
        self.engine = connect(url)
        self._running: dict[str, threading.Thread] = {}
        self._cancel_events: dict[str, threading.Event] = {}
        if initialize:
            migrate(self.engine)
            self._ensure_default_environment()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _ensure_default_environment(self):
        with self.engine.begin() as con:
            existing = con.execute(
                select(notebook_environments).where(
                    notebook_environments.c.environment_code == DEFAULT_QUANT_ENV["environment_code"]
                )
            ).first()
            if not existing:
                record = {
                    "id": _uid(),
                    **DEFAULT_QUANT_ENV,
                    "package_lock_hash": hashlib.sha256(
                        DEFAULT_QUANT_ENV["requirements"].encode()
                    ).hexdigest(),
                    "workspace_id": None,
                    "created_at": _now(),
                }
                con.execute(notebook_environments.insert().values(**record))

    def _resolve_workspace(self, con, workspace_id=None):
        ws_id = workspace_id or workspace_scope.get()
        if ws_id:
            row = con.execute(
                select(workspaces).where(
                    (workspaces.c.id == ws_id) | (workspaces.c.code == ws_id)
                )
            ).mappings().first()
            if not row:
                raise DomainError("Workspace bulunamadı.", 404, "not_found")
            if row["is_archived"]:
                raise DomainError("Arşivlenmiş workspace'e yazılamaz.", 422, "workspace_archived")
            return dict(row)
        # Fall back to first available workspace
        row = con.execute(select(workspaces).where(workspaces.c.is_archived == 0).limit(1)).mappings().first()
        if not row:
            raise DomainError("Aktif workspace bulunamadı.", 404, "not_found")
        return dict(row)

    def _audit(self, con, operation, entity_id, actor, details=None):
        details = details or {}
        workspace_id = None
        candidate = details.get("workspace_id") or workspace_scope.get()
        if candidate:
            row = con.execute(
                select(workspaces.c.id).where(
                    (workspaces.c.id == candidate) | (workspaces.c.code == candidate)
                )
            ).first()
            workspace_id = row[0] if row else None
        con.execute(audits.insert().values(
            actor=actor.get("id", "local-user"),
            source=actor.get("source", "REST"),
            operation=operation,
            entity_id=entity_id,
            request_id=actor.get("request_id", _uid())[:64],
            details=details,
            workspace_id=workspace_id,
            created_at=_now(),
        ))

    def _emit(self, con, run_id, event_type, payload):
        con.execute(notebook_run_events.insert().values(
            run_id=run_id, type=event_type, payload=payload, created_at=_now()
        ))

    def safe_path(self, relative: str) -> Path:
        path = (self.storage / relative).resolve()
        if not path.is_relative_to(self.storage):
            raise DomainError("Geçersiz artifact yolu.", 400)
        return path

    # ── Environment Registry ──────────────────────────────────────────────────

    def list_environments(self) -> list[dict]:
        with self.engine.connect() as con:
            return [dict(r) for r in con.execute(
                select(notebook_environments)
                .where(notebook_environments.c.status == "ACTIVE")
                .order_by(notebook_environments.c.created_at)
            ).mappings()]

    def get_environment(self, env_id: str) -> dict:
        with self.engine.connect() as con:
            row = con.execute(
                select(notebook_environments).where(
                    (notebook_environments.c.id == env_id) |
                    (notebook_environments.c.environment_code == env_id)
                )
            ).mappings().first()
        if not row:
            raise DomainError("Environment bulunamadı.", 404, "not_found")
        return dict(row)

    def create_environment(self, data: dict, actor: dict) -> dict:
        required = {"environment_code", "name"}
        if not required <= set(data):
            raise DomainError("environment_code ve name zorunludur.", 422)
        record = {
            "id": _uid(),
            "environment_code": data["environment_code"],
            "name": data["name"],
            "python_version": data.get("python_version", "3.12"),
            "image_ref": data.get("image_ref"),
            "requirements": data.get("requirements", ""),
            "supports_gpu": int(data.get("supports_gpu", False)),
            "status": "ACTIVE",
            "workspace_id": data.get("workspace_id"),
            "package_lock_hash": hashlib.sha256(
                data.get("requirements", "").encode()
            ).hexdigest(),
            "created_at": _now(),
        }
        with self.engine.begin() as con:
            con.execute(notebook_environments.insert().values(**record))
            self._audit(con, "notebook_environment.create", record["id"], actor, record)
        return record

    # ── Workspace Secrets ─────────────────────────────────────────────────────

    def list_secrets(self, workspace_id: str) -> list[dict]:
        """Return secret keys (not values) for a workspace."""
        with self.engine.begin() as con:
            ws = self._resolve_workspace(con, workspace_id)
        with self.engine.connect() as con:
            rows = con.execute(
                select(workspace_secrets).where(workspace_secrets.c.workspace_id == ws["id"])
            ).mappings()
            return [{"id": r["id"], "key_name": r["key_name"], "description": r["description"],
                     "created_at": r["created_at"], "updated_at": r["updated_at"]} for r in rows]

    def set_secret(self, workspace_id: str, key_name: str, value: str, description: str, actor: dict) -> dict:
        if not key_name or not key_name.strip():
            raise DomainError("Secret key adı gerekli.", 422)
        key_name = key_name.strip().upper()
        encrypted = _xor_obfuscate(value)
        with self.engine.begin() as con:
            ws = self._resolve_workspace(con, workspace_id)
            existing = con.execute(
                select(workspace_secrets).where(
                    workspace_secrets.c.workspace_id == ws["id"],
                    workspace_secrets.c.key_name == key_name,
                )
            ).first()
            if existing:
                con.execute(
                    update(workspace_secrets)
                    .where(workspace_secrets.c.id == existing[0])
                    .values(encrypted_value=encrypted, description=description, updated_at=_now())
                )
                self._audit(con, "workspace_secret.update", existing[0], actor,
                            {"workspace_id": ws["id"], "key_name": key_name})
                return {"key_name": key_name, "updated": True}
            record = {
                "id": _uid(), "workspace_id": ws["id"], "key_name": key_name,
                "encrypted_value": encrypted, "description": description,
                "created_by": actor.get("id", "local-user"),
                "created_at": _now(), "updated_at": _now(),
            }
            con.execute(workspace_secrets.insert().values(**record))
            self._audit(con, "workspace_secret.create", record["id"], actor,
                        {"workspace_id": ws["id"], "key_name": key_name})
        return {"key_name": key_name, "created": True}

    def delete_secret(self, workspace_id: str, key_name: str, actor: dict) -> dict:
        with self.engine.begin() as con:
            ws = self._resolve_workspace(con, workspace_id)
            row = con.execute(
                select(workspace_secrets).where(
                    workspace_secrets.c.workspace_id == ws["id"],
                    workspace_secrets.c.key_name == key_name.upper(),
                )
            ).first()
            if not row:
                raise DomainError("Secret bulunamadı.", 404, "not_found")
            con.execute(workspace_secrets.delete().where(workspace_secrets.c.id == row[0]))
            self._audit(con, "workspace_secret.delete", row[0], actor,
                        {"workspace_id": ws["id"], "key_name": key_name})
        return {"deleted": True}

    def _resolve_secrets(self, con, workspace_id: str, allowed_keys: list[str]) -> dict[str, str]:
        """Return decrypted env vars for allowed_keys in workspace."""
        if not allowed_keys:
            return {}
        rows = con.execute(
            select(workspace_secrets).where(
                workspace_secrets.c.workspace_id == workspace_id,
                workspace_secrets.c.key_name.in_([k.upper() for k in allowed_keys]),
            )
        ).mappings().all()
        return {r["key_name"]: _xor_deobfuscate(r["encrypted_value"]) for r in rows}

    # ── Notebook Registry ─────────────────────────────────────────────────────

    def sanitize(self, nb_bytes: bytes) -> tuple[bytes, list[str]]:
        from backend.platform.notebooks.migrator import sanitize_notebook
        nb_dict = json.loads(nb_bytes.decode("utf-8"))
        sanitized_dict, changes = sanitize_notebook(nb_dict)
        return json.dumps(sanitized_dict, indent=1, ensure_ascii=False).encode("utf-8"), changes

    def upload(self, *, workspace_id: str, filename: str, nb_bytes: bytes,
               name: str, description: str, actor: dict,
               tags: list | None = None, auto_sanitize: bool = False) -> dict:
        """Upload a new notebook and create initial version."""
        from backend.platform.notebooks.inspector import inspect_notebook
        if auto_sanitize:
            nb_bytes, _ = self.sanitize(nb_bytes)
        content_hash = hashlib.sha256(nb_bytes).hexdigest()

        with self.engine.begin() as con:
            ws = self._resolve_workspace(con, workspace_id)

        # Store file
        nb_id = _uid()
        nb_dir = self.storage / "notebooks" / nb_id
        nb_dir.mkdir(parents=True, exist_ok=True)
        nb_path = nb_dir / "v1" / filename
        nb_path.parent.mkdir(exist_ok=True)
        nb_path.write_bytes(nb_bytes)

        storage_path = str(nb_path.relative_to(self.storage))
        inspection = inspect_notebook(nb_bytes)

        # Version record
        ver_id = _uid()
        ver_record = {
            "id": ver_id,
            "notebook_id": nb_id,
            "version": 1,
            "content_hash": content_hash,
            "storage_path": storage_path,
            "change_summary": "Initial upload",
            "created_by": actor.get("id", "local-user"),
            "created_at": _now(),
        }

        # Notebook record
        nb_code = "NB-" + uuid.uuid4().hex[:8].upper()
        nb_record = {
            "id": nb_id,
            "notebook_code": nb_code,
            "workspace_id": ws["id"],
            "name": name.strip() or filename,
            "description": description,
            "source_filename": filename,
            "storage_path": storage_path,
            "content_hash": content_hash,
            "version": 1,
            "status": "ACTIVE",
            "default_environment_id": None,
            "tags": tags or [],
            "created_by": actor.get("id", "local-user"),
            "created_at": _now(),
            "updated_at": _now(),
            "archived_at": None,
        }

        with self.engine.begin() as con:
            con.execute(notebooks.insert().values(**nb_record))
            con.execute(notebook_versions.insert().values(**ver_record))
            self._audit(con, "NOTEBOOK_UPLOADED", nb_id, actor, {
                "workspace_id": ws["id"], "filename": filename, "hash": content_hash,
            })

        return {**nb_record, "inspection": inspection, "current_version": ver_record}

    def new_version(self, *, notebook_id: str, nb_bytes: bytes, filename: str,
                    change_summary: str, actor: dict) -> dict:
        """Upload a new version of an existing notebook."""
        from backend.platform.notebooks.inspector import inspect_notebook
        nb = self._get_notebook(notebook_id)
        content_hash = hashlib.sha256(nb_bytes).hexdigest()
        if content_hash == nb["content_hash"]:
            raise DomainError("Notebook içeriği değişmemiş.", 422, "no_changes")

        new_ver = nb["version"] + 1
        nb_dir = self.storage / "notebooks" / nb["id"]
        nb_path = nb_dir / f"v{new_ver}" / filename
        nb_path.parent.mkdir(parents=True, exist_ok=True)
        nb_path.write_bytes(nb_bytes)
        storage_path = str(nb_path.relative_to(self.storage))
        inspection = inspect_notebook(nb_bytes)

        ver_id = _uid()
        ver_record = {
            "id": ver_id,
            "notebook_id": nb["id"],
            "version": new_ver,
            "content_hash": content_hash,
            "storage_path": storage_path,
            "change_summary": change_summary or f"Version {new_ver}",
            "created_by": actor.get("id", "local-user"),
            "created_at": _now(),
        }
        with self.engine.begin() as con:
            con.execute(notebook_versions.insert().values(**ver_record))
            con.execute(update(notebooks).where(notebooks.c.id == nb["id"]).values(
                version=new_ver, content_hash=content_hash, storage_path=storage_path,
                source_filename=filename, updated_at=_now(),
            ))
            self._audit(con, "NOTEBOOK_VERSION_CREATED", nb["id"], actor, {
                "workspace_id": nb["workspace_id"], "version": new_ver, "hash": content_hash,
            })
        return {**self._get_notebook(nb["id"]), "inspection": inspection, "new_version": ver_record}

    def save_cells_version(self, *, notebook_id: str, cells: list[dict],
                           change_summary: str, actor: dict) -> dict:
        """Persist editor changes as a new immutable notebook version.

        The original notebook JSON is used as the base so outputs and cell
        metadata survive an edit. Only the explicitly editable cell fields
        are accepted from the browser.
        """
        if not isinstance(cells, list) or not cells or len(cells) > 500:
            raise DomainError("Geçersiz hücre listesi.", 422, "invalid_cells")
        nb = self._get_notebook(notebook_id)
        versions = self.list_versions(nb["id"])
        if not versions:
            raise DomainError("Notebook versiyonu bulunamadı.", 404, "not_found")
        base_path = self.safe_path(versions[0]["storage_path"])
        try:
            notebook = json.loads(base_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DomainError("Notebook içeriği okunamadı.", 422, "invalid_notebook") from exc
        original = notebook.get("cells")
        if not isinstance(original, list):
            raise DomainError("Notebook cells listesi bulunamadı.", 422, "invalid_notebook")
        original_by_id = {str(c.get("id") or f"cell-{i + 1:03d}"): c for i, c in enumerate(original) if isinstance(c, dict)}
        rebuilt = []
        for i, item in enumerate(cells):
            if not isinstance(item, dict):
                raise DomainError("Geçersiz hücre.", 422, "invalid_cells")
            cell_type = str(item.get("cell_type") or "code")
            if cell_type not in {"code", "markdown", "raw"}:
                raise DomainError("Geçersiz hücre tipi.", 422, "invalid_cells")
            cell_id = str(item.get("cell_id") or f"cell-{i + 1:03d}")
            base = dict(original_by_id.get(cell_id) or {})
            base["cell_type"] = cell_type
            source = item.get("source", "")
            base["source"] = source if isinstance(source, list) else str(source)
            metadata = dict(base.get("metadata") or {})
            tags = item.get("tags")
            if isinstance(tags, list):
                metadata["tags"] = [str(tag) for tag in tags[:30]]
            base["metadata"] = metadata
            if cell_type != "code":
                base.pop("execution_count", None)
                base.pop("outputs", None)
            else:
                base.setdefault("execution_count", None)
                base.setdefault("outputs", [])
            if "id" in base or any(isinstance(c, dict) and c.get("id") for c in original):
                base["id"] = cell_id
            rebuilt.append(base)
        notebook["cells"] = rebuilt
        raw = json.dumps(notebook, indent=1, ensure_ascii=False).encode("utf-8")
        return self.new_version(
            notebook_id=nb["id"], nb_bytes=raw,
            filename=nb["source_filename"],
            change_summary=change_summary or "Notebook editörü ile güncellendi",
            actor=actor,
        )

    def version_diff(self, notebook_id: str, from_version: int, to_version: int) -> dict:
        nb = self._get_notebook(notebook_id)
        versions = {v["version"]: v for v in self.list_versions(nb["id"])}
        if from_version not in versions or to_version not in versions:
            raise DomainError("Karşılaştırılacak versiyon bulunamadı.", 404, "not_found")
        def read(v):
            data = json.loads(self.safe_path(v["storage_path"]).read_text(encoding="utf-8"))
            return data.get("cells") or []
        before, after = read(versions[from_version]), read(versions[to_version])
        def key(cell, i): return str(cell.get("id") or f"cell-{i + 1:03d}")
        bmap = {key(c, i): c for i, c in enumerate(before)}
        amap = {key(c, i): c for i, c in enumerate(after)}
        added = [k for k in amap if k not in bmap]
        removed = [k for k in bmap if k not in amap]
        changed = [k for k in amap if k in bmap and json.dumps(bmap[k], sort_keys=True, ensure_ascii=False) != json.dumps(amap[k], sort_keys=True, ensure_ascii=False)]
        return {"from_version": from_version, "to_version": to_version, "added_cells": added, "removed_cells": removed, "changed_cells": changed}

    def restore_version(self, *, notebook_id: str, version: int, actor: dict) -> dict:
        nb = self._get_notebook(notebook_id)
        selected = next((v for v in self.list_versions(nb["id"]) if v["version"] == version), None)
        if not selected:
            raise DomainError("Versiyon bulunamadı.", 404, "not_found")
        raw = self.safe_path(selected["storage_path"]).read_bytes()
        return self.new_version(notebook_id=nb["id"], nb_bytes=raw,
                                filename=nb["source_filename"],
                                change_summary=f"v{version} geri yüklendi", actor=actor)

    def notebook_experiment_preview(self, identifier: str, workspace_id: str | None = None) -> dict:
        nb = self.get_notebook(identifier, workspace_id=workspace_id)
        analysis = self.get_notebook_analysis(nb["id"], workspace_id=workspace_id)
        detected_models = analysis.get("analysis", analysis).get("models", [])
        model_map = {"XGBRegressor": "xgboost", "LightGBM": "lightgbm", "RandomForest": "random_forest", "Ridge": "ridge", "HistGradientBoosting": "hist_gradient_boosting"}
        models = []
        for name in detected_models:
            for label, value in model_map.items():
                if label.lower() in name.lower() and value not in models:
                    models.append(value)
        models = models[:5] or ["ridge"]
        validation = analysis.get("analysis", analysis).get("validation", [])
        method = "walk_forward" if any("walk" in str(v).lower() for v in validation) else "holdout"
        spec = {
            "name": f"{nb['name']} — Experiment",
            "description": "Notebook statik analizinden oluşturulan taslak; çalıştırmadan önce gözden geçirin.",
            "tags": ["notebook", "imported"], "market": "FX", "symbol": "EURUSD",
            "dataset_id": "demo", "workspace_id": nb["workspace_id"], "timeframe": "native",
            "features": {"groups": ["technical"], "families": [], "names": []},
            "models": models, "validation": {"method": method}, "optimization": {"algorithm": "none"},
            "backtest": {}, "seed": 42, "regime_states": 3,
        }
        detected = analysis.get("analysis", analysis)
        return {"notebook": {"id": nb["id"], "name": nb["name"], "version": nb["version"]},
                "dataset": analysis.get("analysis", analysis).get("datasets", []) or ["demo (varsayılan)"],
                "target": detected.get("target") or "Notebook içinden otomatik doğrulanamadı",
                "features": detected.get("features", []),
                "models": detected_models or models, "model_parameters": detected.get("model_parameters", {}),
                "regime_model": detected.get("regime_model"), "validation": validation,
                "backtest": detected.get("backtest", []), "metrics": detected.get("metrics", []), "spec": spec}

    def _get_notebook(self, identifier: str) -> dict:
        with self.engine.connect() as con:
            row = con.execute(
                select(notebooks).where(
                    (notebooks.c.id == identifier) | (notebooks.c.notebook_code == identifier)
                )
            ).mappings().first()
        if not row:
            raise DomainError("Notebook bulunamadı.", 404, "not_found")
        return dict(row)

    def get_notebook(self, identifier: str, workspace_id: str | None = None) -> dict:
        nb = self._get_notebook(identifier)
        if workspace_id:
            with self.engine.connect() as con:
                ws = self._resolve_workspace(con, workspace_id)
            if nb["workspace_id"] != ws["id"]:
                raise DomainError("Notebook bulunamadı.", 404, "not_found")
        versions = self.list_versions(nb["id"])
        return {**nb, "versions": versions}

    def get_notebook_cells(self, identifier: str, workspace_id: str | None = None,
                           version: int | None = None) -> dict:
        """Return read-only parsed cells and existing outputs for the viewer.

        This method never executes notebook code. The version path comes from
        the registry, then the parser clips large text and sanitizes HTML.
        """
        nb = self.get_notebook(identifier, workspace_id=workspace_id)
        versions = nb.get("versions") or []
        selected = next((v for v in versions if version is not None and v["version"] == version), None)
        selected = selected or (versions[0] if versions else None)
        if not selected:
            raise DomainError("Notebook versiyonu bulunamadı.", 404, "not_found")
        from backend.platform.notebooks.parser import parse_notebook_file
        parsed = parse_notebook_file(self.safe_path(selected["storage_path"]))
        return {
            "notebook_id": nb["id"],
            "notebook_code": nb["notebook_code"],
            "version": selected["version"],
            **parsed,
        }

    def get_notebook_analysis(self, identifier: str, workspace_id: str | None = None,
                              version: int | None = None) -> dict:
        nb = self.get_notebook(identifier, workspace_id=workspace_id)
        versions = nb.get("versions") or []
        selected = next((v for v in versions if version is not None and v["version"] == version), None)
        selected = selected or (versions[0] if versions else None)
        if not selected:
            raise DomainError("Notebook versiyonu bulunamadı.", 404, "not_found")
        from backend.platform.notebooks.inspector import inspect_notebook
        result = inspect_notebook(self.safe_path(selected["storage_path"]).read_bytes())
        return {"notebook_id": nb["id"], "version": selected["version"], **result}

    def list_notebooks(self, workspace_id: str | None = None, include_archived: bool = False) -> list[dict]:
        with self.engine.begin() as con:
            ws = self._resolve_workspace(con, workspace_id) if workspace_id else None
        with self.engine.connect() as con:
            stmt = select(notebooks).order_by(notebooks.c.created_at.desc())
            if ws:
                stmt = stmt.where(notebooks.c.workspace_id == ws["id"])
            if not include_archived:
                stmt = stmt.where(notebooks.c.status != "ARCHIVED")
            return [dict(r) for r in con.execute(stmt).mappings()]

    def list_versions(self, notebook_id: str) -> list[dict]:
        with self.engine.connect() as con:
            return [dict(r) for r in con.execute(
                select(notebook_versions)
                .where(notebook_versions.c.notebook_id == notebook_id)
                .order_by(notebook_versions.c.version.desc())
            ).mappings()]

    def archive_notebook(self, identifier: str, actor: dict) -> dict:
        nb = self._get_notebook(identifier)
        with self.engine.begin() as con:
            con.execute(update(notebooks).where(notebooks.c.id == nb["id"]).values(
                status="ARCHIVED", archived_at=_now(), updated_at=_now()
            ))
            self._audit(con, "notebook.archive", nb["id"], actor, {"workspace_id": nb["workspace_id"]})
        return self.get_notebook(nb["id"])

    def inspect_notebook(self, nb_bytes: bytes) -> dict:
        from backend.platform.notebooks.inspector import inspect_notebook
        return inspect_notebook(nb_bytes)

    # ── Run Lifecycle ─────────────────────────────────────────────────────────

    def create_run(self, *, workspace_id: str, notebook_id: str,
                   experiment_id: str | None = None,
                   dataset_snapshot_id: str | None = None,
                   environment_id: str | None = None,
                   parameters: dict | None = None,
                   network_mode: str = "SNAPSHOT_ONLY",
                   execution_mode: str = "all",
                   start_index: int | None = None,
                   actor: dict) -> dict:

        if execution_mode not in {"all", "cell", "from", "restart"}:
            raise DomainError("Geçersiz çalıştırma modu.", 422, "invalid_execution_mode")
        if start_index is not None and (start_index < 0 or start_index > 500):
            raise DomainError("Geçersiz hücre indeksi.", 422, "invalid_cell_index")

        with self.engine.begin() as con:
            ws = self._resolve_workspace(con, workspace_id)

        nb = self._get_notebook(notebook_id)
        if nb["workspace_id"] != ws["id"]:
            raise DomainError("Notebook bu workspace'e ait değil.", 403, "workspace_mismatch")

        # Resolve latest version
        versions = self.list_versions(nb["id"])
        if not versions:
            raise DomainError("Notebook versiyonu bulunamadı.", 404, "not_found")
        latest_ver = versions[0]

        # Resolve environment
        if environment_id:
            env = self.get_environment(environment_id)
        else:
            envs = self.list_environments()
            env = envs[0] if envs else {"id": None}

        # Validate experiment belongs to same workspace
        if experiment_id:
            with self.engine.connect() as con:
                exp_row = con.execute(
                    select(experiments).where(experiments.c.id == experiment_id)
                ).mappings().first()
            if not exp_row or exp_row["workspace_id"] != ws["id"]:
                raise DomainError("Experiment bulunamadı.", 404, "not_found")

        # Validate snapshot belongs to same workspace
        if dataset_snapshot_id:
            with self.engine.connect() as con:
                snap_row = con.execute(
                    select(snapshots).where(snapshots.c.id == dataset_snapshot_id)
                ).mappings().first()
            if not snap_row or (snap_row["workspace_id"] and snap_row["workspace_id"] != ws["id"]):
                raise DomainError("Dataset snapshot bulunamadı.", 404, "not_found")

        run_id = _uid()
        run_code = "NR-" + uuid.uuid4().hex[:8].upper()
        record = {
            "id": run_id,
            "run_code": run_code,
            "workspace_id": ws["id"],
            "notebook_id": nb["id"],
            "notebook_version_id": latest_ver["id"],
            "experiment_id": experiment_id,
            "dataset_snapshot_id": dataset_snapshot_id,
            "environment_id": env.get("id"),
            "status": "QUEUED",
            "parameters": parameters or {},
            "runtime_metadata": {"execution_mode": execution_mode,
                                  "start_index": start_index},
            "network_mode": network_mode,
            "job_pid": None,
            "started_at": None,
            "completed_at": None,
            "duration_seconds": None,
            "exit_code": None,
            "error_type": None,
            "error_message": None,
            "executed_notebook_path": None,
            "metrics": None,
            "artifact_count": 0,
            "cancel_requested": 0,
            "created_by": actor.get("id", "local-user"),
            "created_at": _now(),
        }
        with self.engine.begin() as con:
            con.execute(notebook_runs.insert().values(**record))
            self._emit(con, run_id, "notebook.run.queued", {"status": "QUEUED"})
            self._audit(con, "NOTEBOOK_RUN_CREATED", run_id, actor, {
                "workspace_id": ws["id"], "notebook_id": nb["id"],
                "notebook_version": latest_ver["version"],
                "experiment_id": experiment_id,
                "dataset_snapshot_id": dataset_snapshot_id,
            })

        # Launch async worker
        cancel_event = threading.Event()
        self._cancel_events[run_id] = cancel_event
        thread = threading.Thread(target=self._run_worker, args=(run_id, cancel_event), daemon=True)
        self._running[run_id] = thread
        thread.start()

        return {**record, "notebook": nb, "version": latest_ver}

    def cancel_run(self, run_id: str, actor: dict) -> dict:
        run = self._get_run(run_id)
        if run["status"] in NB_TERMINAL:
            raise DomainError("Run zaten tamamlandı.", 422, "already_terminal")
        event = self._cancel_events.get(run_id)
        if event:
            event.set()
        with self.engine.begin() as con:
            con.execute(update(notebook_runs).where(notebook_runs.c.id == run_id).values(cancel_requested=1))
            self._audit(con, "NOTEBOOK_RUN_CANCELLED", run_id, actor, {"workspace_id": run["workspace_id"]})
        return self._get_run(run_id)

    def _get_run(self, run_id: str) -> dict:
        with self.engine.connect() as con:
            row = con.execute(
                select(notebook_runs).where(
                    (notebook_runs.c.id == run_id) | (notebook_runs.c.run_code == run_id)
                )
            ).mappings().first()
        if not row:
            raise DomainError("Run bulunamadı.", 404, "not_found")
        return dict(row)

    def get_run(self, run_id: str, workspace_id: str | None = None) -> dict:
        run = self._get_run(run_id)
        if workspace_id:
            with self.engine.connect() as con:
                ws = self._resolve_workspace(con, workspace_id)
            if run["workspace_id"] != ws["id"]:
                raise DomainError("Run bulunamadı.", 404, "not_found")
        # Attach artifacts list
        artifact_dir = self.storage / "notebook_runs" / run["id"] / "artifacts"
        from backend.platform.notebooks.artifacts import collect_artifacts
        artifacts = collect_artifacts(artifact_dir) if artifact_dir.exists() else []
        return {**run, "artifacts": artifacts}

    def list_runs(self, workspace_id: str | None = None,
                  notebook_id: str | None = None,
                  experiment_id: str | None = None,
                  limit: int = 50) -> list[dict]:
        with self.engine.connect() as con:
            stmt = select(notebook_runs).order_by(notebook_runs.c.created_at.desc()).limit(min(limit, 200))
            if workspace_id:
                ws = self._resolve_workspace(con, workspace_id)
                stmt = stmt.where(notebook_runs.c.workspace_id == ws["id"])
            if notebook_id:
                stmt = stmt.where(notebook_runs.c.notebook_id == notebook_id)
            if experiment_id:
                stmt = stmt.where(notebook_runs.c.experiment_id == experiment_id)
            return [dict(r) for r in con.execute(stmt).mappings()]

    def get_run_logs(self, run_id: str, after: int = 0) -> list[dict]:
        with self.engine.connect() as con:
            rows = con.execute(
                select(notebook_run_events)
                .where(notebook_run_events.c.run_id == run_id,
                       notebook_run_events.c.id > after)
                .order_by(notebook_run_events.c.id)
                .limit(500)
            ).mappings()
            return [dict(r) for r in rows]

    def get_run_metrics(self, run_id: str) -> dict:
        run = self._get_run(run_id)
        return run.get("metrics") or {}

    def list_snapshots(self, workspace_id: str) -> list[dict]:
        with self.engine.connect() as con:
            ws = self._resolve_workspace(con, workspace_id)
            return [dict(row) for row in con.execute(
                select(snapshots.c.id, snapshots.c.sha256, snapshots.c.details, snapshots.c.created_at)
                .where(snapshots.c.workspace_id == ws["id"])
                .order_by(snapshots.c.created_at.desc())
            ).mappings()]

    def artifact_path(self, run_id: str, name: str, workspace_id: str) -> Path:
        run = self.get_run(run_id, workspace_id=workspace_id)
        root = self.safe_path(f"notebook_runs/{run['id']}")
        if name == "executed.ipynb":
            path = (root / name).resolve()
        else:
            artifact_root = root / "artifacts"
            path = (artifact_root / name).resolve()
            if not path.is_relative_to(artifact_root.resolve()):
                raise DomainError("Invalid artifact path.", 404, "not_found")
            if name not in {a["name"] for a in run["artifacts"]}:
                raise DomainError("Artifact not found.", 404, "not_found")
        if not path.is_relative_to(root) or not path.is_file():
            raise DomainError("Artifact not found.", 404, "not_found")
        return path

    def get_run_artifacts(self, run_id: str) -> list[dict]:
        artifact_dir = self.storage / "notebook_runs" / run_id / "artifacts"
        from backend.platform.notebooks.artifacts import collect_artifacts
        return collect_artifacts(artifact_dir)

    # ── Worker ────────────────────────────────────────────────────────────────

    def _run_worker(self, run_id: str, cancel_event: threading.Event):
        """Background thread that executes the notebook."""
        import time as _time
        start_time = _time.monotonic()

        def emit(event_type: str, payload: dict):
            try:
                with self.engine.begin() as con:
                    self._emit(con, run_id, event_type, payload)
            except Exception:
                pass

        try:
            run = self._get_run(run_id)

            # Prepare directories
            run_dir = self.storage / "notebook_runs" / run_id
            artifact_dir = run_dir / "artifacts"
            input_dir = run_dir / "input"
            artifact_dir.mkdir(parents=True, exist_ok=True)
            input_dir.mkdir(exist_ok=True)

            # Get notebook version path
            with self.engine.connect() as con:
                ver = con.execute(
                    select(notebook_versions).where(
                        notebook_versions.c.id == run["notebook_version_id"]
                    )
                ).mappings().first()
            if not ver:
                raise DomainError("Notebook versiyonu bulunamadı.", 404)

            nb_path = self.safe_path(ver["storage_path"])
            output_path = run_dir / "executed.ipynb"

            # Execution modes operate on a temporary, auditable input copy.
            # Parameter-tagged cells are retained so sliced runs remain usable.
            mode = (run.get("runtime_metadata") or {}).get("execution_mode", "all")
            start_index = (run.get("runtime_metadata") or {}).get("start_index")
            if mode in {"cell", "from"} and start_index is not None:
                source_nb = json.loads(nb_path.read_text(encoding="utf-8"))
                source_cells = source_nb.get("cells") or []
                index = max(0, min(int(start_index), max(0, len(source_cells) - 1)))
                selected_cells = [source_cells[index]] if mode == "cell" else source_cells[index:]
                parameter_cells = [c for c in source_cells[:index]
                                   if "parameters" in ((c.get("metadata") or {}).get("tags") or [])]
                source_nb["cells"] = parameter_cells + selected_cells
                sliced_path = run_dir / "execution_input.ipynb"
                sliced_path.write_text(json.dumps(source_nb, ensure_ascii=False), encoding="utf-8")
                nb_path = sliced_path

            # Build injected parameters
            from backend.platform.notebooks.executor import _build_injected_params
            injected = _build_injected_params(
                run_id=run_id,
                workspace_id=run["workspace_id"],
                experiment_id=run["experiment_id"],
                dataset_snapshot_id=run["dataset_snapshot_id"],
                input_dir=str(input_dir),
                artifact_dir=str(artifact_dir),
                extra_params=run.get("parameters") or {},
            )

            # Mount dataset snapshot if provided
            if run["dataset_snapshot_id"]:
                with self.engine.connect() as con:
                    snap = con.execute(
                        select(snapshots).where(snapshots.c.id == run["dataset_snapshot_id"])
                    ).mappings().first()
                if snap:
                    snap_src = self.safe_path(snap["path"])
                    import shutil
                    shutil.copy2(snap_src, input_dir / "dataset.parquet" if snap_src.suffix == ".parquet"
                                 else input_dir / "dataset.csv")
                    # Write metadata
                    (input_dir / "dataset_metadata.json").write_text(
                        json.dumps({
                            "dataset_snapshot_id": snap["id"],
                            "sha256": snap["sha256"],
                            "details": snap["details"],
                            "created_at": snap["created_at"],
                        }, ensure_ascii=False), encoding="utf-8"
                    )

            # Resolve secrets
            allowed_keys = list((run.get("parameters") or {}).get("_secret_keys", []))
            with self.engine.connect() as con:
                secret_env = self._resolve_secrets(con, run["workspace_id"], allowed_keys)

            # Write run manifest
            manifest = {
                "workspace_id": run["workspace_id"],
                "experiment_id": run["experiment_id"],
                "notebook_id": run["notebook_id"],
                "notebook_version_id": run["notebook_version_id"],
                "dataset_snapshot_id": run["dataset_snapshot_id"],
                "environment_id": run["environment_id"],
                "parameters": {k: v for k, v in injected.items() if not k.startswith("_")},
                "started_at": _now(),
                "status": "RUNNING",
            }
            (artifact_dir / "run_manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, default=str), encoding="utf-8"
            )

            # Mark RUNNING
            with self.engine.begin() as con:
                con.execute(update(notebook_runs).where(notebook_runs.c.id == run_id).values(
                    status="RUNNING", started_at=_now()
                ))
                self._emit(con, run_id, "notebook.run.started", {"status": "RUNNING"})
                self._audit(con, "NOTEBOOK_RUN_STARTED", run_id,
                            {"id": "worker", "source": "WORKER", "request_id": _uid()},
                            {"workspace_id": run["workspace_id"]})

            emit("notebook.run.preparing", {"run_id": run_id})

            # Execute
            from backend.platform.notebooks.executor import execute_notebook
            timeout = NB_RUN_POLICY["max_runtime_minutes"] * 60
            result = execute_notebook(
                notebook_path=nb_path,
                output_path=output_path,
                parameters=injected,
                env_vars=secret_env,
                timeout_seconds=timeout,
                cancel_event=cancel_event,
                emit=emit,
                artifact_dir=artifact_dir,
                run_id=run_id,
                secret_keys=list(secret_env.keys()),
            )

            # Collect artifacts
            with self.engine.begin() as con:
                con.execute(update(notebook_runs).where(notebook_runs.c.id == run_id).values(
                    status="COLLECTING_ARTIFACTS"
                ))
                self._emit(con, run_id, "notebook.collecting_artifacts", {})

            from backend.platform.notebooks.artifacts import collect_artifacts
            artifacts = collect_artifacts(artifact_dir)

            # Determine final status
            error_type = result.get("error_type")
            if error_type == "CANCELLED":
                final_status = "CANCELLED"
            elif error_type == "TIMEOUT":
                final_status = "TIMEOUT"
            elif result.get("exit_code", -1) != 0:
                final_status = "FAILED"
            else:
                final_status = "COMPLETED"

            elapsed = _time.monotonic() - start_time
            exec_path = str(output_path.relative_to(self.storage)) if output_path.exists() else None

            # Update manifest
            manifest["completed_at"] = _now()
            manifest["status"] = final_status
            manifest["metrics"] = result.get("metrics", {})
            (artifact_dir / "run_manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, default=str), encoding="utf-8"
            )

            with self.engine.begin() as con:
                con.execute(update(notebook_runs).where(notebook_runs.c.id == run_id).values(
                    status=final_status,
                    completed_at=_now(),
                    duration_seconds=round(elapsed, 2),
                    exit_code=result.get("exit_code"),
                    error_type=result.get("error_type"),
                    error_message=result.get("error_message"),
                    executed_notebook_path=exec_path,
                    metrics=result.get("metrics") or {},
                    artifact_count=len(artifacts),
                ))
                self._emit(con, run_id, f"notebook.run.{final_status.lower()}",
                           {"status": final_status, "metrics": result.get("metrics"), "artifact_count": len(artifacts)})
                self._audit(con, f"NOTEBOOK_RUN_{final_status}", run_id,
                            {"id": "worker", "source": "WORKER", "request_id": _uid()},
                            {"workspace_id": run["workspace_id"], "elapsed_seconds": round(elapsed, 2)})

        except Exception as exc:
            elapsed = _time.monotonic() - start_time
            try:
                with self.engine.begin() as con:
                    con.execute(update(notebook_runs).where(notebook_runs.c.id == run_id).values(
                        status="FAILED", completed_at=_now(), duration_seconds=round(elapsed, 2),
                        error_type=type(exc).__name__, error_message=str(exc)[:2000],
                    ))
                    self._emit(con, run_id, "notebook.run.failed",
                               {"error_type": type(exc).__name__, "error_message": str(exc)[:500]})
            except Exception:
                pass
        finally:
            self._running.pop(run_id, None)
            self._cancel_events.pop(run_id, None)

    def close(self):
        for event in self._cancel_events.values():
            event.set()
