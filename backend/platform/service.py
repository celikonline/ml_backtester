import hashlib
import json
import os
import platform
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError

from backend.engine import read_prices, audit_calendar
from .db import connect, migrate, snapshots, experiments, runs, events, audits, test_seals, test_access_events, research_budgets, research_trial_events, experiment_edges, search_spaces, optimization_candidates, feature_evaluations, feature_stability_runs, workspaces, ROOT, STORAGE
from .schema import ExperimentSpec, SearchSpaceDefinition, WorkspaceCreate, WorkspacePatch, DomainError, POLICY, STAGES, TERMINAL, RESEARCH_BUDGET, check_policy, estimate_research_risk
from .scope import workspace_scope
from .families import family_for_column


DEFAULT_WORKSPACE_CODE = "WS-DEFAULT"


def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return str(uuid.uuid4())


def atomic_json(path, data):
    temporary = path.with_name(path.name + "." + uid() + ".tmp")
    temporary.write_text(json.dumps(data,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    temporary.replace(path)


class ExperimentService:
    def __init__(self, dataset_loader=None, url=None, storage=None, initialize=True):
        self.storage = Path(storage or STORAGE).resolve()
        self.storage.mkdir(parents=True,exist_ok=True)
        self.engine = connect(url)
        self.dataset_loader = dataset_loader
        self.stop_event = threading.Event()
        self.thread = None
        self.process = None
        if initialize: migrate(self.engine)

    def _budget_usage(self, con, budget_id):
        rows = con.execute(select(research_trial_events.c.event_type, func.coalesce(func.sum(research_trial_events.c.quantity), 0)).where(research_trial_events.c.budget_id == budget_id).group_by(research_trial_events.c.event_type)).all()
        values = {kind: int(quantity) for kind, quantity in rows}
        return {"experiments": values.get("experiment_created", 0), "candidates": values.get("candidate_planned", 0),
                "backtests": values.get("backtest_planned", 0), "sealed_test_accesses": values.get("sealed_test_opened", 0)}

    def _ensure_budget(self, con, workspace_id):
        row = con.execute(select(research_budgets).where(research_budgets.c.workspace_id == workspace_id)).mappings().first()
        if not row:
            record = {"id": uid(), "limits": dict(RESEARCH_BUDGET), "workspace_id": workspace_id, "created_at": now(), "updated_at": now()}
            con.execute(research_budgets.insert().values(**record))
            return record
        return dict(row)

    def _resolve_budget_workspace(self, con, workspace_id=None):
        ws = workspace_id or workspace_scope.get()
        if ws:
            row = con.execute(select(workspaces.c.id).where((workspaces.c.id == ws) | (workspaces.c.code == ws))).first()
            if not row: raise DomainError("Workspace bulunamadı.", 404, "not_found")
            return row[0]
        return self.ensure_default_workspace()["id"]

    def budget_status(self, workspace_id=None):
        with self.engine.begin() as con:
            budget = self._ensure_budget(con, self._resolve_budget_workspace(con, workspace_id))
            return {"id": budget["id"], "workspace_id": budget.get("workspace_id"),
                    "usage": self._budget_usage(con, budget["id"]), "limits": budget["limits"]}

    def update_budget_limits(self, limits, actor, workspace_id=None):
        if not isinstance(limits, dict) or not limits: raise DomainError("Geçersiz bütçe limiti.", 422, "invalid_budget")
        unknown = set(limits) - set(RESEARCH_BUDGET)
        if unknown or any(isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0 for v in limits.values()):
            raise DomainError("Geçersiz bütçe limiti.", 422, "invalid_budget")
        with self.engine.begin() as con:
            budget = self._ensure_budget(con, self._resolve_budget_workspace(con, workspace_id))
            merged = {**budget["limits"], **limits}
            con.execute(update(research_budgets).where(research_budgets.c.id == budget["id"]).values(limits=merged, updated_at=now()))
            self.audit(con, "budget.update", budget["id"], actor, {"limits": merged, "workspace_id": budget.get("workspace_id")})
            return {"id": budget["id"], "workspace_id": budget.get("workspace_id"),
                    "usage": self._budget_usage(con, budget["id"]), "limits": merged}

    def ledger(self, limit=200, workspace_id=None):
        with self.engine.connect() as con:
            stmt = select(research_trial_events).order_by(research_trial_events.c.id.desc()).limit(max(1, min(limit, 500))).offset(0)
            ws = workspace_id or workspace_scope.get()
            if ws:
                row = con.execute(select(workspaces.c.id).where((workspaces.c.id == ws) | (workspaces.c.code == ws))).first()
                if not row: raise DomainError("Workspace bulunamadı.", 404, "not_found")
                budget = con.execute(select(research_budgets.c.id).where(research_budgets.c.workspace_id == row[0])).first()
                stmt = stmt.where(research_trial_events.c.budget_id == (budget[0] if budget else "__none__"))
            return [dict(row) for row in con.execute(stmt).mappings()]

    def estimate(self, spec, snapshot_id=None, workspace_id=None):
        spec = ExperimentSpec.model_validate(spec)
        snapshot = self.get_snapshot(snapshot_id) if snapshot_id else None
        rows = snapshot["details"]["rows"] if snapshot else POLICY["max_rows"]
        return estimate_research_risk(spec, rows, self.budget_status(workspace_id)["usage"])

    def _record_trial(self, con, event_type, quantity=1, experiment_id=None, details=None):
        details = details or {}
        ws = details.get("workspace_id")
        if not ws and experiment_id:
            ws = con.execute(select(experiments.c.workspace_id).where(experiments.c.id == experiment_id)).scalar()
        if not ws:
            ws = self.ensure_default_workspace()["id"]
        budget = self._ensure_budget(con, ws)
        con.execute(research_trial_events.insert().values(budget_id=budget["id"], experiment_id=experiment_id, event_type=event_type, quantity=quantity, details=details, created_at=now()))
        con.execute(update(research_budgets).where(research_budgets.c.id == budget["id"]).values(updated_at=now()))

    def _active_seal(self, con, snapshot_id):
        return con.execute(select(test_seals).where(test_seals.c.test_dataset_id == snapshot_id, test_seals.c.invalidated_at.is_(None)).order_by(test_seals.c.epoch.desc())).mappings().first()

    def _latest_seal(self, con, snapshot_id):
        return con.execute(select(test_seals).where(test_seals.c.test_dataset_id == snapshot_id).order_by(test_seals.c.epoch.desc())).mappings().first()

    def _workspace_counts(self, con, workspace_id):
        exp = con.execute(select(func.count()).select_from(experiments).where(experiments.c.workspace_id == workspace_id)).scalar()
        ds = con.execute(select(func.count()).select_from(snapshots).where(snapshots.c.workspace_id == workspace_id)).scalar()
        return {"experiment_count": exp, "dataset_count": ds}

    def ensure_default_workspace(self):
        with self.engine.begin() as con:
            row = con.execute(select(workspaces).where(workspaces.c.code == DEFAULT_WORKSPACE_CODE)).mappings().first()
            if not row:
                row = {"id": uid(), "code": DEFAULT_WORKSPACE_CODE, "name": "EUR/USD Research", "description": "",
                       "market": "FX", "base_currency": "USD", "timezone": "UTC", "owner": None,
                       "is_archived": 0, "created_at": now(), "updated_at": now(), "archived_at": None}
                con.execute(workspaces.insert().values(**row))
            return dict(row)

    def _resolve_workspace(self, con, workspace_id):
        """Explicit id/code wins; otherwise the default workspace. Archived workspaces refuse new writes."""
        if workspace_id:
            row = con.execute(select(workspaces).where((workspaces.c.id == workspace_id) | (workspaces.c.code == workspace_id))).mappings().first()
            if not row: raise DomainError("Workspace bulunamadı.", 404, "not_found")
        else:
            row = self.ensure_default_workspace()
            row = con.execute(select(workspaces).where(workspaces.c.id == row["id"])).mappings().one()
        if row["is_archived"]: raise DomainError("Arşivlenmiş workspace'e yazılamaz.", 422, "workspace_archived")
        return dict(row)

    def create_workspace(self, data, actor):
        body = WorkspaceCreate.model_validate(data)
        with self.engine.begin() as con:
            record = {"id": uid(), "code": "WS-" + uuid.uuid4().hex[:8].upper(), "name": body.name.strip(),
                      "description": body.description, "market": body.market, "base_currency": body.base_currency,
                      "timezone": body.timezone, "owner": body.owner, "is_archived": 0,
                      "created_at": now(), "updated_at": now(), "archived_at": None}
            con.execute(workspaces.insert().values(**record))
            self.audit(con, "workspace.create", record["id"], actor, {"code": record["code"], "name": record["name"]})
            return {**record, **self._workspace_counts(con, record["id"])}

    def list_workspaces(self, include_archived=False):
        with self.engine.connect() as con:
            query = select(workspaces).order_by(workspaces.c.created_at)
            if not include_archived: query = query.where(workspaces.c.is_archived == 0)
            return [{**dict(row), **self._workspace_counts(con, row["id"])} for row in con.execute(query).mappings()]

    def get_workspace(self, identifier):
        with self.engine.connect() as con:
            row = con.execute(select(workspaces).where((workspaces.c.id == identifier) | (workspaces.c.code == identifier))).mappings().first()
            if not row: raise DomainError("Workspace bulunamadı.", 404, "not_found")
            return {**dict(row), **self._workspace_counts(con, row["id"])}

    def patch_workspace(self, identifier, data, actor):
        body = WorkspacePatch.model_validate(data)
        with self.engine.begin() as con:
            row = con.execute(select(workspaces).where((workspaces.c.id == identifier) | (workspaces.c.code == identifier))).mappings().first()
            if not row: raise DomainError("Workspace bulunamadı.", 404, "not_found")
            values = {k: v for k, v in body.model_dump().items() if v is not None}
            if "name" in values: values["name"] = values["name"].strip()
            if values:
                values["updated_at"] = now()
                con.execute(update(workspaces).where(workspaces.c.id == row["id"]).values(**values))
            self.audit(con, "workspace.update", row["id"], actor, {"updated": sorted(values)})
        return self.get_workspace(identifier)

    def archive_workspace(self, identifier, actor):
        with self.engine.begin() as con:
            row = con.execute(select(workspaces).where((workspaces.c.id == identifier) | (workspaces.c.code == identifier))).mappings().first()
            if not row: raise DomainError("Workspace bulunamadı.", 404, "not_found")
            if row["code"] == DEFAULT_WORKSPACE_CODE: raise DomainError("Varsayılan workspace arşivlenemez.", 422, "workspace_archived")
            con.execute(update(workspaces).where(workspaces.c.id == row["id"]).values(is_archived=1, archived_at=now(), updated_at=now()))
            self.audit(con, "workspace.archive", row["id"], actor, {"code": row["code"]})
        return self.get_workspace(identifier)

    def seal(self, snapshot_id):
        with self.engine.begin() as con:
            record = self._active_seal(con, snapshot_id)
            if not record:
                latest = self._latest_seal(con, snapshot_id)
                epoch = (latest["epoch"] + 1) if latest else 1
                record = {"seal_id":uid(), "test_dataset_id":snapshot_id, "access_count":0, "epoch":epoch, "created_at":now()}
                con.execute(test_seals.insert().values(**record))
            return dict(record)

    def seal_status(self, snapshot_id):
        with self.engine.connect() as con:
            latest = self._latest_seal(con, snapshot_id)
            if latest: return dict(latest)
        return self.seal(snapshot_id)

    def seal_history(self, snapshot_id):
        with self.engine.connect() as con:
            return [dict(row) for row in con.execute(select(test_seals).where(test_seals.c.test_dataset_id == snapshot_id).order_by(test_seals.c.epoch)).mappings()]

    def invalidate_seal(self, seal_id, reason, actor):
        reason = (reason or "").strip()
        if not 1 <= len(reason) <= 500: raise DomainError("Geçersiz kılma nedeni gerekli (1–500 karakter).", 422, "invalid_reason")
        with self.engine.begin() as con:
            seal = con.execute(select(test_seals).where(test_seals.c.seal_id == seal_id)).mappings().first()
            if not seal: raise DomainError("Seal bulunamadı.", 404, "not_found")
            if seal["invalidated_at"]: return dict(seal)
            con.execute(update(test_seals).where(test_seals.c.seal_id == seal_id).values(invalidated_at=now(), invalidation_reason=reason))
            snap_ws = con.execute(select(snapshots.c.workspace_id).where(snapshots.c.id == seal["test_dataset_id"])).scalar()
            self._record_trial(con, "seal_invalidated", details={"seal_id":seal_id, "epoch":seal["epoch"], "reason":reason, "workspace_id": snap_ws})
            self.audit(con, "seal.invalidate", seal_id, actor, {"test_dataset_id":seal["test_dataset_id"], "epoch":seal["epoch"], "reason":reason})
            return dict(con.execute(select(test_seals).where(test_seals.c.seal_id == seal_id)).mappings().one())

    def rotate_seal(self, snapshot_id, reason, actor):
        reason = (reason or "").strip()
        if not 1 <= len(reason) <= 500: raise DomainError("Rotasyon nedeni gerekli (1–500 karakter).", 422, "invalid_reason")
        with self.engine.begin() as con:
            latest = self._latest_seal(con, snapshot_id)
            if not latest: raise DomainError("Seal bulunamadı.", 404, "not_found")
            if latest["invalidated_at"] is None:
                con.execute(update(test_seals).where(test_seals.c.seal_id == latest["seal_id"]).values(invalidated_at=now(), invalidation_reason="rotated: " + reason))
            record = {"seal_id":uid(), "test_dataset_id":snapshot_id, "access_count":0, "epoch":latest["epoch"] + 1, "invalidated_at":None, "invalidation_reason":None, "created_at":now()}
            con.execute(test_seals.insert().values(**record))
            snap_ws = con.execute(select(snapshots.c.workspace_id).where(snapshots.c.id == snapshot_id)).scalar()
            self._record_trial(con, "seal_rotated", details={"seal_id":record["seal_id"], "epoch":record["epoch"], "reason":reason, "supersedes":latest["seal_id"], "workspace_id": snap_ws})
            self.audit(con, "seal.rotate", record["seal_id"], actor, {"test_dataset_id":snapshot_id, "epoch":record["epoch"], "reason":reason, "supersedes":latest["seal_id"]})
            return dict(record)

    def create_search_space(self, definition, actor, workspace_id=None):
        definition=SearchSpaceDefinition.model_validate(definition)
        with self.engine.begin() as con:
            ws = self._resolve_workspace(con, workspace_id)
            record={"id":uid(),"name":definition.name,"version":1,"definition":definition.model_dump(),"owner":actor.get("id","local-user"),"created_at":now(),"workspace_id":ws["id"]}
            con.execute(search_spaces.insert().values(**record)); self.audit(con,"search_space.create",record["id"],actor,{"name":record["name"],"workspace_id":ws["id"]})
        return record

    def list_search_spaces(self, workspace_id=None):
        with self.engine.connect() as con:
            stmt = select(search_spaces).where(search_spaces.c.archived_at.is_(None)).order_by(search_spaces.c.created_at.desc())
            if workspace_id:
                scope = con.execute(select(workspaces.c.id).where((workspaces.c.id==workspace_id)|(workspaces.c.code==workspace_id))).first()
                if not scope: raise DomainError("Workspace bulunamadı.",404,"not_found")
                stmt = stmt.where(search_spaces.c.workspace_id==scope[0])
            return [dict(row) for row in con.execute(stmt).mappings()]

    def get_search_space(self, identifier):
        with self.engine.connect() as con: row=con.execute(select(search_spaces).where(search_spaces.c.id==identifier)).mappings().first()
        if not row: raise DomainError("Search space bulunamadı.",404,"not_found")
        return dict(row)

    def _apply_search_space(self, spec, workspace_id):
        if not spec.search_space_id: return spec
        stored = self.get_search_space(spec.search_space_id)
        if stored.get("workspace_id") and stored["workspace_id"] != workspace_id:
            raise DomainError("Search space bulunamadı.",404,"not_found")
        space=SearchSpaceDefinition.model_validate(stored["definition"])
        features=spec.features.model_copy(update={"groups":space.feature_groups,"names":space.features})
        optimization=spec.optimization.model_copy(update={"min_features":space.min_features,"max_features":space.max_features,"hyperparameters":space.hyperparameters,"max_drawdown":space.max_drawdown,"thresholds_bps":space.thresholds_bps})
        return spec.model_copy(update={"features":features,"models":space.models,"optimization":optimization,"regime_states":space.regime_states})

    def _open_seal_for_final_test(self, con, item, run_id):
        seal = con.execute(select(test_seals).where(test_seals.c.test_dataset_id == item["snapshot_id"], test_seals.c.invalidated_at.is_(None)).order_by(test_seals.c.epoch.desc())).mappings().first()
        if not seal:
            raise DomainError("Test seal'i geçersiz kılınmış; yeni temporal holdout oluşturun.", 409, "seal_invalidated")
        # The worker may open a seal only at this exact frozen-candidate boundary.
        con.execute(test_access_events.insert().values(seal_id=seal["seal_id"], experiment_id=item["id"], run_id=run_id, actor="worker", purpose="final_frozen_candidate_test", created_at=now()))
        con.execute(update(test_seals).where(test_seals.c.seal_id == seal["seal_id"]).values(access_count=seal["access_count"] + 1, first_opened_at=seal["first_opened_at"] or now()))
        self._record_trial(con, "sealed_test_opened", experiment_id=item["id"], details={"seal_id":seal["seal_id"], "run_id":run_id})
        return seal

    def audit(self, con, operation, entity, actor, details=None):
        con.execute(audits.insert().values(actor=actor.get("id","local-user"), source=actor.get("source","REST"),operation=operation,
            entity_id=entity,request_id=actor.get("request_id",uid()),details=details or {},created_at=now()))

    def log(self, con, exp_id, run_id, kind, payload):
        con.execute(events.insert().values(experiment_id=exp_id,run_id=run_id,type=kind,payload=payload,created_at=now()))

    def snapshot(self, dataset_id, workspace_id=None):
        df,name,demo = self.dataset_loader(dataset_id)
        raw = df.to_csv().encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        identifier = uid()
        path = self.storage/"snapshots"/f"{identifier}.csv"
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(raw)
        gaps = df.index.to_series().diff().dropna()
        external = [column for column in df.columns if not column.endswith("__available_at") and family_for_column(column)]
        verified = [column for column in external if f"{column}__available_at" in df]
        unverified = sorted(set(external)-set(verified))
        late = sum(int((df[f"{column}__available_at"].notna() & (df[f"{column}__available_at"] > df.index)).sum()) for column in verified)
        point_in_time = "verified" if external and not unverified and late == 0 else ("partially_verified" if verified else "unverified")
        calendar = audit_calendar(df)
        meta = {"dataset_id":dataset_id,"name":name,"demo":demo,"rows":len(df),"columns":list(df.columns),
                "start":df.index[0].isoformat(),"end":df.index[-1].isoformat(),"missing_values":int(df.isna().sum().sum()),
                "median_bar_seconds":float(gaps.median().total_seconds()),"irregular_intervals":int((gaps!=gaps.median()).sum()),
                "timezone":"UTC normalized","point_in_time":point_in_time,"external_series":external,
                "availability_verified":verified,"availability_unverified":unverified,"late_availability_rows":late,
                "revision":"not supplied","survivorship":"not applicable to fixed EURUSD series",
                "dst_audit":f"source timestamps {calendar['source_timezone']}, normalized to UTC on ingest",
                "gap_provenance":f"{calendar['weekend_gaps']} weekend gaps, {calendar['midweek_gaps']} midweek gaps, {calendar['weekend_bars']} weekend bars",
                "calendar":calendar}
        record = {"id":identifier,"sha256":digest,"path":str(path.relative_to(self.storage)),"details":meta,"created_at":now()}
        with self.engine.begin() as con:
            ws = self._resolve_workspace(con, workspace_id)
            record["workspace_id"] = ws["id"]
            con.execute(snapshots.insert().values(**record))
        return record

    def get_snapshot(self, identifier):
        with self.engine.connect() as con: row = con.execute(select(snapshots).where(snapshots.c.id==identifier)).mappings().first()
        if not row: raise DomainError("Snapshot bulunamadı.",404,"not_found")
        return dict(row)

    def load_snapshot(self, identifier):
        snapshot = self.get_snapshot(identifier)
        raw = self.safe_path(snapshot["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=snapshot["sha256"]: raise DomainError("Snapshot hash doğrulaması başarısız.",409,"snapshot_tampered")
        return read_prices(raw)

    def safe_path(self, relative):
        path = (self.storage/relative).resolve()
        if not path.is_relative_to(self.storage): raise DomainError("Geçersiz artifact yolu.",400)
        return path

    def create(self, spec, actor, parent_id=None, snapshot_id=None, workspace_id=None):
        spec = ExperimentSpec.model_validate(spec)
        with self.engine.begin() as con:
            ws = self._resolve_workspace(con, workspace_id or spec.workspace_id)
        spec = self._apply_search_space(spec, ws["id"])
        if snapshot_id:
            snapshot = self.get_snapshot(snapshot_id)
            if snapshot.get("workspace_id") and snapshot["workspace_id"] != ws["id"]:
                raise DomainError("Snapshot bulunamadı.", 404, "not_found")
        else:
            snapshot = self.snapshot(spec.dataset_id, ws["id"])
        check_policy(spec,snapshot["details"]["rows"])
        risk = self.estimate(spec, snapshot["id"], ws["id"])
        if risk["risk_score"] >= RESEARCH_BUDGET["risk_reject_at"]:
            raise DomainError("Araştırma bütçesi/multiple-testing riski politika sınırını aşıyor.",422,"policy_rejected")
        from .research import registry
        names = {f["id"] for f in registry(self.load_snapshot(snapshot["id"]))}
        if not set(spec.features.names)<=names: raise DomainError("Bilinmeyen özellik adı.",422,"invalid_feature")
        identifier = uid()
        record = {"id":identifier,"code":f"EXP-{datetime.now().year}-{identifier[:8].upper()}","parent_id":parent_id,"snapshot_id":snapshot["id"],"workspace_id":ws["id"],
                  "name":spec.name,"status":"DRAFT","specification":spec.model_dump(),"owner":actor.get("id","local-user"),"created_at":now(),"updated_at":now()}
        with self.engine.begin() as con:
            con.execute(experiments.insert().values(**record))
            if not con.execute(select(test_seals.c.seal_id).where(test_seals.c.test_dataset_id == snapshot["id"], test_seals.c.invalidated_at.is_(None))).first():
                if con.execute(select(test_seals.c.seal_id).where(test_seals.c.test_dataset_id == snapshot["id"])).first():
                    raise DomainError("Test seal'i geçersiz kılınmış; yeni temporal holdout oluşturun.", 409, "seal_invalidated")
                con.execute(test_seals.insert().values(seal_id=uid(), test_dataset_id=snapshot["id"], access_count=0, epoch=1, created_at=now()))
            self._record_trial(con,"experiment_created",experiment_id=identifier,details={"risk":risk})
            if parent_id:
                parent_seal=con.execute(select(test_seals).where(test_seals.c.test_dataset_id==snapshot["id"]).order_by(test_seals.c.epoch.desc())).mappings().first()
                relation="POST_TEST_ITERATION_FROM" if parent_seal["access_count"] else "CLONED_FROM"
                con.execute(experiment_edges.insert().values(from_experiment_id=parent_id,to_experiment_id=identifier,relation_type=relation,reason_code="shared_sealed_dataset",actor_type=actor.get("source","REST"),change_summary={"seal_id":parent_seal["seal_id"]},created_at=now()))
            self.audit(con,"experiment.clone" if parent_id else "experiment.create",identifier,actor,{"parent_id":parent_id,"snapshot_hash":snapshot["sha256"],"workspace_id":ws["id"]})
            self.log(con,identifier,None,"experiment.created",{"status":"DRAFT"})
        return self.get(identifier)

    def get(self, identifier, workspace_id=None):
        with self.engine.connect() as con:
            row = con.execute(select(experiments).where((experiments.c.id==identifier)|(experiments.c.code==identifier))).mappings().first()
            if not row: raise DomainError("Deney bulunamadı.",404,"not_found")
            item = dict(row)
            requested = workspace_id or workspace_scope.get()
            if requested and item.get("workspace_id") != requested:
                scope_row = con.execute(select(workspaces.c.id).where((workspaces.c.id==requested)|(workspaces.c.code==requested))).first()
                if not scope_row or scope_row[0] != item.get("workspace_id"):
                    raise DomainError("Deney bulunamadı.",404,"not_found")
            run = con.execute(select(runs).where(runs.c.experiment_id==item["id"])).mappings().first()
            item["run"] = dict(run) if run else None
        item["snapshot"] = self.get_snapshot(item["snapshot_id"])
        return item

    def list(self, query="", status=None, model=None, optimizer=None, tag=None, workspace_id=None):
        with self.engine.connect() as con:
            stmt = select(experiments.c.id).order_by(experiments.c.created_at.desc())
            if workspace_id:
                scope = con.execute(select(workspaces.c.id).where((workspaces.c.id==workspace_id)|(workspaces.c.code==workspace_id))).first()
                if not scope: raise DomainError("Workspace bulunamadı.",404,"not_found")
                stmt = stmt.where(experiments.c.workspace_id==scope[0])
            rows = con.execute(stmt).scalars().all()
        items = [self.get(identifier) for identifier in rows]
        return [i for i in items if (not query or query.casefold() in (i["name"]+i["code"]).casefold())
                and (not status or i["status"]==status) and (not model or model in i["specification"]["models"])
                and (not optimizer or i["specification"]["optimization"]["algorithm"]==optimizer)
                and (not tag or tag in i["specification"]["tags"])]

    def clone(self, identifier, request, actor):
        parent = self.get(identifier)
        spec = request.specification or ExperimentSpec.model_validate(parent["specification"])
        if spec.dataset_id != parent["specification"]["dataset_id"]:
            raise DomainError("Klon aynı snapshot'ı kullanır. Başka veri için yeni deney oluşturun.",422)
        spec = spec.model_copy(update={"name":request.name or (spec.name[:100]+" · klon")})
        return self.create(spec,actor,parent["id"],parent["snapshot_id"],parent["workspace_id"])

    def patch(self, identifier, spec, actor):
        item = self.get(identifier)
        if item["status"]!="DRAFT": raise DomainError("Çalıştırılmış deney sabittir; klon oluşturun.",409,"frozen_experiment")
        if spec.dataset_id!=item["specification"]["dataset_id"]: raise DomainError("Veri değişikliği yeni deney gerektirir.",422)
        if spec.workspace_id and spec.workspace_id not in (item["workspace_id"],):
            raise DomainError("Workspace uyuşmazlığı.",422,"workspace_mismatch")
        check_policy(spec,item["snapshot"]["details"]["rows"])
        with self.engine.begin() as con:
            changed=con.execute(update(experiments).where(experiments.c.id==item["id"],experiments.c.status=="DRAFT").values(name=spec.name,specification=spec.model_dump(),updated_at=now()))
            if changed.rowcount!=1: raise DomainError("Deney çalıştırılmaya başlandı.",409)
            self.audit(con,"experiment.update",item["id"],actor,{"before":item["specification"],"after":spec.model_dump()})
        return self.get(item["id"])

    def run(self, identifier, key, actor):
        item=self.get(identifier)
        if not key or len(key)>120: raise DomainError("Idempotency-Key başlığı gerekli (1–120 karakter).",422,"missing_idempotency_key")
        scoped_key=hashlib.sha256((actor.get("id","local-user")+":"+key).encode()).hexdigest()
        with self.engine.connect() as con:
            existing=con.execute(select(runs).where(runs.c.idempotency_key==scoped_key)).mappings().first()
        if existing:
            if existing["experiment_id"]!=item["id"]: raise DomainError("Aynı anahtar başka bir deneyde kullanılmış.",409,"idempotency_conflict")
            return dict(existing)
        spec=ExperimentSpec.model_validate(item["specification"])
        estimate=check_policy(spec,item["snapshot"]["details"]["rows"])
        risk=estimate_research_risk(spec,item["snapshot"]["details"]["rows"],self.budget_status(item["workspace_id"])["usage"])
        if risk["risk_score"] >= RESEARCH_BUDGET["risk_reject_at"]: raise DomainError("Araştırma bütçesi/multiple-testing riski politika sınırını aşıyor.",422,"policy_rejected")
        run_id=uid()
        record={"id":run_id,"experiment_id":item["id"],"idempotency_key":scoped_key,"status":"QUEUED","progress":0,"message":"Sıraya alındı", "created_at":now(),"cancel_requested":0,"runtime":{"estimate":estimate}}
        try:
            with self.engine.begin() as con:
                queue=con.execute(select(func.count()).select_from(runs).where(runs.c.status=="QUEUED")).scalar()
                if queue>=POLICY["max_queued_jobs"]: raise DomainError("İş kuyruğu dolu.",429,"queue_full")
                changed=con.execute(update(experiments).where(experiments.c.id==item["id"],experiments.c.status=="DRAFT").values(status="QUEUED",updated_at=now()))
                if changed.rowcount!=1: raise DomainError("Her deney bir kez çalıştırılır. Yeni çalışma için klonlayın.",409,"test_already_exposed")
                con.execute(runs.insert().values(**record))
                self._record_trial(con,"candidate_planned",estimate["candidate_limit"],item["id"],{"run_id":run_id})
                self._record_trial(con,"backtest_planned",risk["estimated_backtests"],item["id"],{"run_id":run_id})
                self.log(con,item["id"],run_id,"experiment.status.changed",{"status":"QUEUED","progress":0})
                self.audit(con,"experiment.run",item["id"],actor,{"run_id":run_id,"estimate":estimate})
        except IntegrityError:
            with self.engine.connect() as con: existing=con.execute(select(runs).where(runs.c.idempotency_key==scoped_key)).mappings().first()
            if existing and existing["experiment_id"]==item["id"]: return dict(existing)
            raise DomainError("Çalıştırma zaten kaydedilmiş.",409)
        return record

    def emit(self, run_id, kind, payload):
        with self.engine.begin() as con:
            row=con.execute(select(runs).where(runs.c.id==run_id)).mappings().one()
            if row["cancel_requested"] or row["status"] in TERMINAL: raise InterruptedError("Çalıştırma durduruldu.")
            if kind=="stage":
                status=payload["status"]
                if status not in STAGES or STAGES.index(status)<STAGES.index(row["status"]): raise ValueError("Geçersiz durum geçişi.")
                values={"status":status,"progress":payload["progress"],"message":payload["message"]}
                con.execute(update(runs).where(runs.c.id==run_id).values(**values))
                con.execute(update(experiments).where(experiments.c.id==row["experiment_id"]).values(status=status,updated_at=now()))
                kind="experiment.status.changed"
            elif kind=="optimization.generation.completed":
                con.execute(update(runs).where(runs.c.id==run_id).values(progress=20+int(45*payload["generation"]/payload["total_generations"]),message=f"Nesil {payload['generation']}/{payload['total_generations']}"))
            self.log(con,row["experiment_id"],run_id,kind,payload)

    def finish(self, run_id, status, message, result_path=None, result_metrics=None):
        with self.engine.begin() as con:
            row=con.execute(select(runs).where(runs.c.id==run_id)).mappings().one()
            if row["status"] in TERMINAL: return
            con.execute(update(runs).where(runs.c.id==run_id).values(status=status,message=message,finished_at=now(),
                progress=100 if status=="COMPLETED" else row["progress"],result_path=result_path,metrics=result_metrics,
                duration_seconds=(datetime.now(timezone.utc)-datetime.fromisoformat(row["started_at"] or row["created_at"])).total_seconds()))
            con.execute(update(experiments).where(experiments.c.id==row["experiment_id"]).values(status=status,updated_at=now()))
            self.log(con,row["experiment_id"],run_id,"experiment.status.changed",{"status":status,"message":message})

    def open_final_test(self, run_id):
        """Worker-only gate; no optimizer code receives a callable test reader."""
        with self.engine.begin() as con:
            row=con.execute(select(experiments).join(runs, runs.c.experiment_id==experiments.c.id).where(runs.c.id==run_id)).mappings().one()
            return self._open_seal_for_final_test(con, row, run_id)

    def lineage(self, identifier):
        item=self.get(identifier)
        with self.engine.connect() as con:
            return [dict(row) for row in con.execute(select(experiment_edges).where((experiment_edges.c.from_experiment_id==item["id"]) | (experiment_edges.c.to_experiment_id==item["id"])).order_by(experiment_edges.c.id)).mappings()]

    def persist_candidates(self, experiment_id, candidates, artifact_ref=None):
        pareto_ids={c["id"] for c in candidates if c.get("pareto")}
        with self.engine.begin() as con:
            for candidate in candidates:
                metrics=candidate["metrics"]
                dominates=sum(1 for other in candidates if other["id"] != candidate["id"] and other["metrics"]["sharpe"] >= metrics["sharpe"] and other["metrics"]["return"] >= metrics["return"] and other["metrics"]["max_drawdown"] >= metrics["max_drawdown"] and any(other["metrics"][k] > metrics[k] for k in ("sharpe","return","max_drawdown")))
                decision="selected" if candidate.get("selected") else ("pareto" if candidate["id"] in pareto_ids else ("rejected_constraint" if not candidate["feasible"] else "not_selected"))
                exists=con.execute(select(optimization_candidates.c.id).where(optimization_candidates.c.experiment_id==experiment_id,optimization_candidates.c.candidate_key==candidate["id"])).first()
                if not exists: con.execute(optimization_candidates.insert().values(id=uid(),experiment_id=experiment_id,candidate_key=candidate["id"],generation=None,genome=candidate["genome"],metrics=metrics,fitness=candidate["fitness"],pareto_rank=0 if candidate["id"] in pareto_ids else None,dominance_count=dominates,decision=decision,artifact_ref=artifact_ref,created_at=now()))

    def candidates(self, identifier):
        item=self.get(identifier)
        with self.engine.connect() as con: return [dict(row) for row in con.execute(select(optimization_candidates).where(optimization_candidates.c.experiment_id==item["id"]).order_by(optimization_candidates.c.fitness.desc())).mappings()]

    def candidate(self, identifier):
        with self.engine.connect() as con: row=con.execute(select(optimization_candidates).where(optimization_candidates.c.id==identifier)).mappings().first()
        if not row: raise DomainError("Aday bulunamadı.",404,"not_found")
        return dict(row)

    def persist_feature_analysis(self, experiment_id, analysis, selected):
        with self.engine.begin() as con:
            for item in analysis["features"]:
                exists=con.execute(select(feature_evaluations.c.id).where(feature_evaluations.c.experiment_id==experiment_id,feature_evaluations.c.feature==item["feature"])).scalar()
                if exists: continue
                evaluation_id=uid()
                con.execute(feature_evaluations.insert().values(id=evaluation_id,experiment_id=experiment_id,feature=item["feature"],ic=item["ic"],sign_consistency=item["sign_consistency"],mutual_information=item["mutual_information"],missingness=0.0,selected=int(item["feature"] in selected),created_at=now()))
                for index, ic in enumerate(item["rolling_ic"]): con.execute(feature_stability_runs.insert().values(id=uid(),feature_evaluation_id=evaluation_id,window_index=index,rolling_ic=ic,created_at=now()))

    def feature_evaluations(self, identifier):
        item=self.get(identifier)
        with self.engine.connect() as con:
            records=[]
            for row in con.execute(select(feature_evaluations).where(feature_evaluations.c.experiment_id==item["id"]).order_by(feature_evaluations.c.feature)).mappings():
                value=dict(row)
                value["stability_runs"]=[dict(r) for r in con.execute(select(feature_stability_runs).where(feature_stability_runs.c.feature_evaluation_id==value["id"]).order_by(feature_stability_runs.c.window_index)).mappings()]
                records.append(value)
            return records

    def cancel(self, identifier, actor):
        item=self.get(identifier)
        if not item["run"] or item["status"] in TERMINAL: raise DomainError("Aktif çalışma yok.",409)
        with self.engine.begin() as con:
            con.execute(update(runs).where(runs.c.id==item["run"]["id"]).values(cancel_requested=1,message="İptal istendi"))
            self.audit(con,"experiment.cancel",item["id"],actor)
        if item["status"]=="QUEUED": self.finish(item["run"]["id"],"CANCELLED","Kuyruktayken iptal edildi")
        return {"status":"cancelling"}

    def logs(self, identifier, after=0):
        item=self.get(identifier)
        with self.engine.connect() as con:
            return [dict(r) for r in con.execute(select(events).where(events.c.experiment_id==item["id"],events.c.id>after).order_by(events.c.id)).mappings()]

    def result(self, identifier):
        item=self.get(identifier)
        if item["status"]!="COMPLETED" or not item["run"]["result_path"]: raise DomainError("Sonuç henüz hazır değil.",409,"result_not_ready")
        return json.loads(self.safe_path(item["run"]["result_path"]).read_text(encoding="utf-8"))

    def compare(self, identifiers):
        if not 2<=len(set(identifiers))<=5 or len(set(identifiers))!=len(identifiers): raise DomainError("2–5 farklı deney seçin.",422)
        items=[]
        for identifier in identifiers:
            item=self.get(identifier); result=self.result(identifier)
            items.append({"experiment":item,"result":result})
        base=items[0]
        differences=[]
        for item in items[1:]:
            left,right=base["experiment"]["specification"],item["experiment"]["specification"]
            differences.append({"code":item["experiment"]["code"],"config":{k:{"before":left.get(k),"after":v} for k,v in right.items() if left.get(k)!=v},
                                "features_added":sorted(set(item["result"]["selected_features"])-set(base["result"]["selected_features"])),
                                "features_removed":sorted(set(base["result"]["selected_features"])-set(item["result"]["selected_features"]))})
        def canonical(value):
            if isinstance(value, dict): return {k: canonical(v) for k,v in value.items()}
            if isinstance(value, list): return [canonical(v) for v in value]
            return float(value) if isinstance(value, (int,float)) and not isinstance(value, bool) else value
        signatures={(i["experiment"]["snapshot"]["sha256"],i["result"]["split"]["test_start"],i["result"]["split"]["test_end"],json.dumps(canonical(i["experiment"]["specification"]["backtest"]),sort_keys=True)) for i in items}
        return {"items":items,"differences":differences,"comparable":len(signatures)==1,
                "warning":None if len(signatures)==1 else "Snapshot, test dönemi veya maliyet/sermaye ayarları farklı; doğrudan performans sıralaması yanıltıcı olabilir."}

    def artifacts(self, identifier):
        item=self.get(identifier)
        if not item["run"]: return []
        folder=self.storage/"runs"/item["run"]["id"]
        allowed={"result.json","specification.json","frozen_candidate.json","model.joblib"}
        return [{"name":p.name,"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()} for p in folder.glob("*") if p.name in allowed]

    def start(self):
        if self.thread: return
        # Single API process deployment: unfinished workers are never silently reported as complete.
        with self.engine.connect() as con: stale=con.execute(select(runs.c.id).where(~runs.c.status.in_(list(TERMINAL|{"QUEUED"})))).scalars().all()
        for run_id in stale: self.finish(run_id,"FAILED","Sunucu yeniden başladı; önceki çalışma kesildi. Klon ile yeniden çalıştırın.")
        self.thread=threading.Thread(target=self._loop,name="regimelab-worker-manager",daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread: self.thread.join(timeout=8)
        self.engine.dispose()

    def _loop(self):
        while not self.stop_event.wait(.25):
            with self.engine.begin() as con:
                job=con.execute(select(runs).where(runs.c.status=="QUEUED",runs.c.cancel_requested==0).order_by(runs.c.created_at).limit(1)).mappings().first()
                if not job: continue
                claimed=con.execute(update(runs).where(runs.c.id==job["id"],runs.c.status=="QUEUED",runs.c.cancel_requested==0).values(status="DATA_PREPARATION",started_at=now(),message="Worker başlıyor"))
                if claimed.rowcount!=1: continue
                con.execute(update(experiments).where(experiments.c.id==job["experiment_id"]).values(status="DATA_PREPARATION",updated_at=now()))
                self.log(con,job["experiment_id"],job["id"],"experiment.status.changed",{"status":"DATA_PREPARATION","progress":3})
            folder=self.storage/"runs"/job["id"]
            folder.mkdir(parents=True,exist_ok=True)
            env=os.environ.copy()
            env.update(REGIMELAB_DATABASE_URL=self.engine.url.render_as_string(hide_password=False),REGIMELAB_STORAGE=str(self.storage),PYTHONIOENCODING="utf-8",OMP_NUM_THREADS="2")
            try:
                with (folder/"worker.log").open("wb") as logfile:
                    self.process=subprocess.Popen([sys.executable,"-m","backend.platform.worker",job["id"]],cwd=ROOT,env=env,stdout=logfile,stderr=logfile,
                        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
                    started=time.monotonic()
                    while self.process.poll() is None:
                        with self.engine.connect() as con: row=con.execute(select(runs).where(runs.c.id==job["id"])).mappings().one()
                        reason="CANCELLED" if row["cancel_requested"] or self.stop_event.is_set() else "TIMEOUT" if time.monotonic()-started>POLICY["max_training_minutes"]*60 else None
                        if reason:
                            self.process.terminate()
                            try: self.process.wait(timeout=3)
                            except subprocess.TimeoutExpired: self.process.kill(); self.process.wait()
                            self.finish(job["id"],reason,"İptal edildi" if reason=="CANCELLED" else "Çalışma süresi sınırı aşıldı")
                            break
                        self.stop_event.wait(.25)
                self.finish(job["id"],"FAILED","Worker sonuç kaydetmeden kapandı.")
            except Exception as exc: self.finish(job["id"],"FAILED",str(exc))
            finally: self.process=None


def runtime_metadata():
    source_files=sorted((ROOT/"backend").rglob("*.py"))
    digest=hashlib.sha256()
    for p in source_files:
        digest.update(str(p.relative_to(ROOT)).encode());digest.update(p.read_bytes())
    return {"python":sys.version,"platform":platform.platform(),"worker_pid":os.getpid(),"code_sha256":digest.hexdigest(),
            "packages":{name:version(name) for name in ["numpy","pandas","scikit-learn","xgboost","lightgbm","hmmlearn"]}}
