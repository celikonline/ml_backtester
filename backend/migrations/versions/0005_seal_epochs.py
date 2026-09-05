"""Sealed-test epoch rotation: multiple seal generations per dataset."""
from alembic import op
import sqlalchemy as sa
revision = "0005_seal_epochs"
down_revision = "0004_feature_intelligence"
branch_labels = depends_on = None

NEW_TABLE = """CREATE TABLE test_seals (
    seal_id VARCHAR(36) NOT NULL PRIMARY KEY,
    test_dataset_id VARCHAR(64) NOT NULL REFERENCES dataset_snapshots (id),
    access_count INTEGER NOT NULL DEFAULT 0,
    first_opened_at VARCHAR(40),
    invalidated_at VARCHAR(40),
    invalidation_reason TEXT,
    created_at VARCHAR(40) NOT NULL,
    epoch INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT uq_test_seals_dataset_epoch UNIQUE (test_dataset_id, epoch))"""
COPY_SEALS = ("INSERT INTO test_seals (seal_id, test_dataset_id, access_count, first_opened_at,"
    " invalidated_at, invalidation_reason, created_at, epoch) SELECT seal_id, test_dataset_id,"
    " access_count, first_opened_at, invalidated_at, invalidation_reason, created_at, epoch FROM test_seals_legacy")
COPY_EVENTS = ("INSERT INTO test_access_events (id, seal_id, experiment_id, run_id, actor, purpose, created_at)"
    " SELECT id, seal_id, experiment_id, run_id, actor, purpose, created_at FROM test_access_events_legacy")

def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        # SQLite cannot drop the single-column unique constraint in place, and
        # DROP TABLE fails while test_access_events references it. Rebuild both
        # tables; RENAME carries the child FK to the legacy table first so no
        # access event is orphaned mid-migration.
        op.execute(sa.text("ALTER TABLE test_seals RENAME TO test_seals_legacy"))
        op.execute(sa.text(NEW_TABLE))
        op.execute(sa.text("ALTER TABLE test_seals_legacy ADD COLUMN epoch INTEGER NOT NULL DEFAULT 1"))
        op.execute(sa.text(COPY_SEALS))
        op.execute(sa.text("ALTER TABLE test_access_events RENAME TO test_access_events_legacy"))
        op.execute(sa.text("""CREATE TABLE test_access_events (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            seal_id VARCHAR(36) NOT NULL REFERENCES test_seals (seal_id),
            experiment_id VARCHAR(36) NOT NULL REFERENCES experiments (id),
            run_id VARCHAR(36) REFERENCES experiment_runs (id),
            actor VARCHAR(120) NOT NULL, purpose VARCHAR(80) NOT NULL, created_at VARCHAR(40) NOT NULL)"""))
        op.execute(sa.text(COPY_EVENTS))
        op.execute(sa.text("DROP TABLE test_access_events_legacy"))
        op.execute(sa.text("DROP TABLE test_seals_legacy"))
    else:
        op.add_column("test_seals", sa.Column("epoch", sa.Integer(), nullable=False, server_default="1"))
        op.execute(sa.text("ALTER TABLE test_seals DROP CONSTRAINT IF EXISTS test_seals_test_dataset_id_key"))
        op.create_unique_constraint("uq_test_seals_dataset_epoch", "test_seals", ["test_dataset_id", "epoch"])

def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        raise RuntimeError("Downgrade of 0005 requires a single seal epoch per dataset; delete newer epochs first.")
    op.drop_constraint("uq_test_seals_dataset_epoch", "test_seals", type_="unique")
    op.create_unique_constraint("test_seals_test_dataset_id_key", "test_seals", ["test_dataset_id"])
    op.drop_column("test_seals", "epoch")
