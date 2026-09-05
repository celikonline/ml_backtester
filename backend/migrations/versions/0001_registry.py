"""Initial experiment registry. Immutable column definitions for upgrade/downgrade."""
from alembic import op
import sqlalchemy as sa
revision = "0001_registry"
down_revision = None
branch_labels = depends_on = None

def upgrade():
    op.create_table("dataset_snapshots", sa.Column("id",sa.String(64),primary_key=True),sa.Column("sha256",sa.String(64),nullable=False),sa.Column("path",sa.Text,nullable=False),sa.Column("details",sa.JSON,nullable=False),sa.Column("created_at",sa.String(40),nullable=False))
    op.create_table("experiments",sa.Column("id",sa.String(36),primary_key=True),sa.Column("code",sa.String(40),unique=True,nullable=False),sa.Column("parent_id",sa.String(36),sa.ForeignKey("experiments.id")),sa.Column("snapshot_id",sa.String(64),sa.ForeignKey("dataset_snapshots.id"),nullable=False),sa.Column("name",sa.String(120),nullable=False),sa.Column("status",sa.String(32),nullable=False),sa.Column("specification",sa.JSON,nullable=False),sa.Column("owner",sa.String(120),nullable=False),sa.Column("created_at",sa.String(40),nullable=False),sa.Column("updated_at",sa.String(40),nullable=False))
    op.create_table("experiment_runs",sa.Column("id",sa.String(36),primary_key=True),sa.Column("experiment_id",sa.String(36),sa.ForeignKey("experiments.id"),unique=True,nullable=False),sa.Column("idempotency_key",sa.String(200),unique=True,nullable=False),sa.Column("status",sa.String(32),nullable=False),sa.Column("progress",sa.Integer,nullable=False),sa.Column("message",sa.Text,nullable=False),sa.Column("created_at",sa.String(40),nullable=False),sa.Column("started_at",sa.String(40)),sa.Column("finished_at",sa.String(40)),sa.Column("cancel_requested",sa.Integer,nullable=False),sa.Column("result_path",sa.Text),sa.Column("runtime",sa.JSON,nullable=False),sa.Column("metrics",sa.JSON),sa.Column("duration_seconds",sa.Float))
    op.create_table("experiment_events",sa.Column("id",sa.Integer,primary_key=True,autoincrement=True),sa.Column("experiment_id",sa.String(36),sa.ForeignKey("experiments.id"),nullable=False),sa.Column("run_id",sa.String(36),sa.ForeignKey("experiment_runs.id")),sa.Column("type",sa.String(80),nullable=False),sa.Column("payload",sa.JSON,nullable=False),sa.Column("created_at",sa.String(40),nullable=False))
    op.create_table("audit_logs",sa.Column("id",sa.Integer,primary_key=True,autoincrement=True),sa.Column("actor",sa.String(120),nullable=False),sa.Column("source",sa.String(40),nullable=False),sa.Column("operation",sa.String(80),nullable=False),sa.Column("entity_id",sa.String(64)),sa.Column("request_id",sa.String(64),nullable=False),sa.Column("details",sa.JSON,nullable=False),sa.Column("created_at",sa.String(40),nullable=False))
    op.create_index("ix_events_experiment_id", "experiment_events", ["experiment_id", "id"])

def downgrade():
    for table in ["audit_logs","experiment_events","experiment_runs","experiments","dataset_snapshots"]:
        op.drop_table(table)
