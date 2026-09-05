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

from backend.engine import read_prices
from .db import connect, migrate, snapshots, experiments, runs, events, audits, ROOT, STORAGE
from .schema import ExperimentSpec, DomainError, POLICY, STAGES, TERMINAL, check_policy
from .families import family_for_column


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

    def audit(self, con, operation, entity, actor, details=None):
        con.execute(audits.insert().values(actor=actor.get("id","local-user"), source=actor.get("source","REST"),operation=operation,
            entity_id=entity,request_id=actor.get("request_id",uid()),details=details or {},created_at=now()))

    def log(self, con, exp_id, run_id, kind, payload):
        con.execute(events.insert().values(experiment_id=exp_id,run_id=run_id,type=kind,payload=payload,created_at=now()))

    def snapshot(self, dataset_id):
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
        meta = {"dataset_id":dataset_id,"name":name,"demo":demo,"rows":len(df),"columns":list(df.columns),
                "start":df.index[0].isoformat(),"end":df.index[-1].isoformat(),"missing_values":int(df.isna().sum().sum()),
                "median_bar_seconds":float(gaps.median().total_seconds()),"irregular_intervals":int((gaps!=gaps.median()).sum()),
                "timezone":"UTC normalized","point_in_time":point_in_time,"external_series":external,
                "availability_verified":verified,"availability_unverified":unverified,"late_availability_rows":late,
                "revision":"not supplied","survivorship":"not applicable to fixed EURUSD series",
                "dst_audit":"source timezone/release provenance unavailable","gap_provenance":"weekend and missing-source gaps not distinguished"}
        record = {"id":identifier,"sha256":digest,"path":str(path.relative_to(self.storage)),"details":meta,"created_at":now()}
        with self.engine.begin() as con: con.execute(snapshots.insert().values(**record))
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

    def create(self, spec, actor, parent_id=None, snapshot_id=None):
        spec = ExperimentSpec.model_validate(spec)
        snapshot = self.get_snapshot(snapshot_id) if snapshot_id else self.snapshot(spec.dataset_id)
        check_policy(spec,snapshot["details"]["rows"])
        from .research import registry
        names = {f["id"] for f in registry(self.load_snapshot(snapshot["id"]))}
        if not set(spec.features.names)<=names: raise DomainError("Bilinmeyen özellik adı.",422,"invalid_feature")
        identifier = uid()
        record = {"id":identifier,"code":f"EXP-{datetime.now().year}-{identifier[:8].upper()}","parent_id":parent_id,"snapshot_id":snapshot["id"],
                  "name":spec.name,"status":"DRAFT","specification":spec.model_dump(),"owner":actor.get("id","local-user"),"created_at":now(),"updated_at":now()}
        with self.engine.begin() as con:
            con.execute(experiments.insert().values(**record))
            self.audit(con,"experiment.clone" if parent_id else "experiment.create",identifier,actor,{"parent_id":parent_id,"snapshot_hash":snapshot["sha256"]})
            self.log(con,identifier,None,"experiment.created",{"status":"DRAFT"})
        return self.get(identifier)

    def get(self, identifier):
        with self.engine.connect() as con:
            row = con.execute(select(experiments).where((experiments.c.id==identifier)|(experiments.c.code==identifier))).mappings().first()
            if not row: raise DomainError("Deney bulunamadı.",404,"not_found")
            item = dict(row)
            run = con.execute(select(runs).where(runs.c.experiment_id==item["id"])).mappings().first()
            item["run"] = dict(run) if run else None
        item["snapshot"] = self.get_snapshot(item["snapshot_id"])
        return item

    def list(self, query="", status=None, model=None, optimizer=None, tag=None):
        with self.engine.connect() as con:
            rows = con.execute(select(experiments.c.id).order_by(experiments.c.created_at.desc())).scalars().all()
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
        return self.create(spec,actor,parent["id"],parent["snapshot_id"])

    def patch(self, identifier, spec, actor):
        item = self.get(identifier)
        if item["status"]!="DRAFT": raise DomainError("Çalıştırılmış deney sabittir; klon oluşturun.",409,"frozen_experiment")
        if spec.dataset_id!=item["specification"]["dataset_id"]: raise DomainError("Veri değişikliği yeni deney gerektirir.",422)
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
        estimate=check_policy(ExperimentSpec.model_validate(item["specification"]),item["snapshot"]["details"]["rows"])
        run_id=uid()
        record={"id":run_id,"experiment_id":item["id"],"idempotency_key":scoped_key,"status":"QUEUED","progress":0,"message":"Sıraya alındı", "created_at":now(),"cancel_requested":0,"runtime":{"estimate":estimate}}
        try:
            with self.engine.begin() as con:
                queue=con.execute(select(func.count()).select_from(runs).where(runs.c.status=="QUEUED")).scalar()
                if queue>=POLICY["max_queued_jobs"]: raise DomainError("İş kuyruğu dolu.",429,"queue_full")
                changed=con.execute(update(experiments).where(experiments.c.id==item["id"],experiments.c.status=="DRAFT").values(status="QUEUED",updated_at=now()))
                if changed.rowcount!=1: raise DomainError("Her deney bir kez çalıştırılır. Yeni çalışma için klonlayın.",409,"test_already_exposed")
                con.execute(runs.insert().values(**record))
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
        signatures={(i["experiment"]["snapshot"]["sha256"],i["result"]["split"]["test_start"],i["result"]["split"]["test_end"],json.dumps(i["experiment"]["specification"]["backtest"],sort_keys=True)) for i in items}
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
