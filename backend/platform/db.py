import os
from pathlib import Path
from sqlalchemy import JSON, Column, Float, ForeignKey, Index, Integer, MetaData, String, Table, Text, UniqueConstraint, create_engine, event

ROOT = Path(__file__).resolve().parents[2]
STORAGE = Path(os.environ.get("REGIMELAB_STORAGE", ROOT / "data" / "platform")).resolve()
DEFAULT_URL = "sqlite:///" + (STORAGE / "registry.sqlite3").as_posix()
metadata = MetaData()
snapshots = Table("dataset_snapshots", metadata,
    Column("id", String(64), primary_key=True), Column("sha256", String(64), nullable=False),
    Column("path", Text, nullable=False), Column("details", JSON, nullable=False), Column("created_at", String(40), nullable=False),
    Column("workspace_id", String(36), ForeignKey("workspaces.id")))
Index("ix_snapshots_workspace_id", snapshots.c.workspace_id)
workspaces = Table("workspaces", metadata,
    Column("id", String(36), primary_key=True), Column("code", String(24), unique=True, nullable=False),
    Column("name", String(120), nullable=False), Column("description", Text, nullable=False, default=""),
    Column("market", String(16), nullable=False, default=""), Column("base_currency", String(8), nullable=False, default=""),
    Column("timezone", String(40), nullable=False, default="UTC"), Column("owner", String(120)),
    Column("is_archived", Integer, nullable=False, default=0),
    Column("created_at", String(40), nullable=False), Column("updated_at", String(40), nullable=False), Column("archived_at", String(40)))
experiments = Table("experiments", metadata,
    Column("id", String(36), primary_key=True), Column("code", String(40), unique=True, nullable=False),
    Column("parent_id", String(36), ForeignKey("experiments.id")), Column("snapshot_id", String(64), ForeignKey("dataset_snapshots.id"), nullable=False),
    Column("workspace_id", String(36), ForeignKey("workspaces.id")),
    Column("name", String(120), nullable=False), Column("status", String(32), nullable=False),
    Column("specification", JSON, nullable=False), Column("owner", String(120), nullable=False),
    Column("created_at", String(40), nullable=False), Column("updated_at", String(40), nullable=False))
Index("ix_experiments_workspace_id", experiments.c.workspace_id)
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
    Column("request_id", String(64), nullable=False), Column("details", JSON, nullable=False), Column("created_at", String(40), nullable=False),
    Column("workspace_id", String(36), ForeignKey("workspaces.id")))
Index("ix_audits_workspace_id", audits.c.workspace_id)
test_seals = Table("test_seals", metadata,
    Column("seal_id", String(36), primary_key=True), Column("test_dataset_id", String(64), ForeignKey("dataset_snapshots.id"), nullable=False),
    Column("access_count", Integer, nullable=False, default=0), Column("first_opened_at", String(40)),
    Column("invalidated_at", String(40)), Column("invalidation_reason", Text), Column("created_at", String(40), nullable=False),
    Column("epoch", Integer, nullable=False, default=1),
    UniqueConstraint("test_dataset_id", "epoch", name="uq_test_seals_dataset_epoch"))
test_access_events = Table("test_access_events", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True), Column("seal_id", String(36), ForeignKey("test_seals.seal_id"), nullable=False),
    Column("experiment_id", String(36), ForeignKey("experiments.id"), nullable=False), Column("run_id", String(36), ForeignKey("experiment_runs.id")),
    Column("actor", String(120), nullable=False), Column("purpose", String(80), nullable=False), Column("created_at", String(40), nullable=False))
research_budgets = Table("research_budgets", metadata,
    Column("id", String(120), primary_key=True), Column("limits", JSON, nullable=False), Column("created_at", String(40), nullable=False), Column("updated_at", String(40), nullable=False),
    Column("workspace_id", String(36), ForeignKey("workspaces.id")))
Index("ix_budgets_workspace_id", research_budgets.c.workspace_id, unique=True)
research_trial_events = Table("research_trial_events", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True), Column("budget_id", String(120), ForeignKey("research_budgets.id"), nullable=False),
    Column("experiment_id", String(36), ForeignKey("experiments.id")), Column("event_type", String(80), nullable=False),
    Column("quantity", Integer, nullable=False, default=1), Column("details", JSON, nullable=False), Column("created_at", String(40), nullable=False))
experiment_edges = Table("experiment_edges", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True), Column("from_experiment_id", String(36), ForeignKey("experiments.id"), nullable=False),
    Column("to_experiment_id", String(36), ForeignKey("experiments.id"), nullable=False), Column("relation_type", String(40), nullable=False), Column("reason_code", String(80)), Column("actor_type", String(40), nullable=False), Column("change_summary", JSON, nullable=False), Column("created_at", String(40), nullable=False))
search_spaces = Table("search_space_definitions", metadata,
    Column("id", String(36), primary_key=True), Column("name", String(120), nullable=False), Column("version", Integer, nullable=False), Column("definition", JSON, nullable=False), Column("owner", String(120), nullable=False), Column("created_at", String(40), nullable=False), Column("archived_at", String(40)), Column("workspace_id", String(36), ForeignKey("workspaces.id")))
Index("ix_spaces_workspace_id", search_spaces.c.workspace_id)
optimization_candidates = Table("optimization_candidates", metadata,
    Column("id", String(36), primary_key=True), Column("experiment_id", String(36), ForeignKey("experiments.id"), nullable=False), Column("candidate_key", String(64), nullable=False), Column("generation", Integer), Column("genome", JSON, nullable=False), Column("metrics", JSON, nullable=False), Column("fitness", Float, nullable=False), Column("pareto_rank", Integer), Column("dominance_count", Integer, nullable=False, default=0), Column("decision", String(40), nullable=False), Column("artifact_ref", Text), Column("created_at", String(40), nullable=False))
Index("ix_candidates_experiment", optimization_candidates.c.experiment_id, optimization_candidates.c.candidate_key, unique=True)
candidate_parents = Table("candidate_parents", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("child_id", String(36), ForeignKey("optimization_candidates.id"), nullable=False),
    Column("parent_id", String(36), ForeignKey("optimization_candidates.id"), nullable=False),
    Column("created_at", String(40), nullable=False))
Index("ix_candidate_parents_child", candidate_parents.c.child_id, candidate_parents.c.parent_id, unique=True)
feature_evaluations = Table("feature_evaluations", metadata,
    Column("id", String(36), primary_key=True), Column("experiment_id", String(36), ForeignKey("experiments.id"), nullable=False), Column("feature", String(160), nullable=False), Column("ic", Float, nullable=False), Column("sign_consistency", Float, nullable=False), Column("mutual_information", Float, nullable=False), Column("missingness", Float, nullable=False), Column("selected", Integer, nullable=False), Column("created_at", String(40), nullable=False))
feature_stability_runs = Table("feature_stability_runs", metadata,
    Column("id", String(36), primary_key=True), Column("feature_evaluation_id", String(36), ForeignKey("feature_evaluations.id"), nullable=False), Column("window_index", Integer, nullable=False), Column("rolling_ic", Float, nullable=False), Column("created_at", String(40), nullable=False))
Index("ix_feature_evaluations_experiment", feature_evaluations.c.experiment_id, feature_evaluations.c.feature)
feature_regime_metrics = Table("feature_regime_metrics", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("feature_evaluation_id", String(36), ForeignKey("feature_evaluations.id"), nullable=False),
    Column("regime", Integer, nullable=False), Column("bars", Integer, nullable=False),
    Column("share", Float, nullable=False), Column("ic", Float, nullable=False),
    Column("created_at", String(40), nullable=False))
Index("ix_feature_regime_evaluation", feature_regime_metrics.c.feature_evaluation_id, feature_regime_metrics.c.regime, unique=True)
feature_selection_events = Table("feature_selection_events", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("experiment_id", String(36), ForeignKey("experiments.id"), nullable=False),
    Column("feature", String(160), nullable=False), Column("selected", Integer, nullable=False),
    Column("selection_frequency", Float), Column("top_survival", Float),
    Column("fitness_present", Float), Column("fitness_absent", Float),
    Column("created_at", String(40), nullable=False))
Index("ix_feature_selection_experiment", feature_selection_events.c.experiment_id, feature_selection_events.c.feature, unique=True)
feature_redundancy_pairs = Table("feature_redundancy_pairs", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("experiment_id", String(36), ForeignKey("experiments.id"), nullable=False),
    Column("a", String(160), nullable=False), Column("b", String(160), nullable=False),
    Column("correlation", Float, nullable=False), Column("created_at", String(40), nullable=False))
Index("ix_feature_redundancy_experiment", feature_redundancy_pairs.c.experiment_id, feature_redundancy_pairs.c.a, feature_redundancy_pairs.c.b, unique=True)


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
