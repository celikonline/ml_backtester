import os
from pathlib import Path
from sqlalchemy import JSON, Column, Float, ForeignKey, Index, Integer, MetaData, String, Table, Text, create_engine, event

ROOT = Path(__file__).resolve().parents[2]
STORAGE = Path(os.environ.get("REGIMELAB_STORAGE", ROOT / "data" / "platform")).resolve()
DEFAULT_URL = "sqlite:///" + (STORAGE / "registry.sqlite3").as_posix()
metadata = MetaData()
snapshots = Table("dataset_snapshots", metadata,
    Column("id", String(64), primary_key=True), Column("sha256", String(64), nullable=False),
    Column("path", Text, nullable=False), Column("details", JSON, nullable=False), Column("created_at", String(40), nullable=False))
experiments = Table("experiments", metadata,
    Column("id", String(36), primary_key=True), Column("code", String(40), unique=True, nullable=False),
    Column("parent_id", String(36), ForeignKey("experiments.id")), Column("snapshot_id", String(64), ForeignKey("dataset_snapshots.id"), nullable=False),
    Column("name", String(120), nullable=False), Column("status", String(32), nullable=False),
    Column("specification", JSON, nullable=False), Column("owner", String(120), nullable=False),
    Column("created_at", String(40), nullable=False), Column("updated_at", String(40), nullable=False))
runs = Table("experiment_runs", metadata,
    Column("id", String(36), primary_key=True), Column("experiment_id", String(36), ForeignKey("experiments.id"), unique=True, nullable=False),
    Column("idempotency_key", String(200), unique=True, nullable=False), Column("status", String(32), nullable=False),
    Column("progress", Integer, nullable=False), Column("message", Text, nullable=False), Column("created_at", String(40), nullable=False),
    Column("started_at", String(40)), Column("finished_at", String(40)), Column("cancel_requested", Integer, nullable=False, default=0),
    Column("result_path", Text), Column("runtime", JSON, nullable=False), Column("metrics", JSON), Column("duration_seconds", Float))
events = Table("experiment_events", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True), Column("experiment_id", String(36), ForeignKey("experiments.id"), nullable=False),
    Column("run_id", String(36), ForeignKey("experiment_runs.id")), Column("type", String(80), nullable=False),
    Column("payload", JSON, nullable=False), Column("created_at", String(40), nullable=False))
Index("ix_events_experiment_id", events.c.experiment_id, events.c.id)
audits = Table("audit_logs", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True), Column("actor", String(120), nullable=False),
    Column("source", String(40), nullable=False), Column("operation", String(80), nullable=False), Column("entity_id", String(64)),
    Column("request_id", String(64), nullable=False), Column("details", JSON, nullable=False), Column("created_at", String(40), nullable=False))


def connect(url=None):
    url = url or os.environ.get("REGIMELAB_DATABASE_URL", DEFAULT_URL)
    kwargs = {"connect_args": {"check_same_thread": False, "timeout": 30}} if url.startswith("sqlite") else {}
    engine = create_engine(url, pool_pre_ping=True, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def pragmas(dbapi, _):
            cur = dbapi.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()
    return engine


def migrate(engine):
    from alembic import command
    from alembic.config import Config
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend" / "migrations"))
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")
