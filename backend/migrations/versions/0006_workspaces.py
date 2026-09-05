"""First-class workspaces: entity, scoping columns, default seed and backfill."""
import uuid
from alembic import op
import sqlalchemy as sa
revision = "0006_workspaces"
down_revision = "0005_seal_epochs"
branch_labels = depends_on = None

DEFAULT_CODE = "WS-DEFAULT"
DEFAULT_NAME = "EUR/USD Research"


def _has_table(bind, name):
    return sa.inspect(bind).has_table(name)


def _has_column(bind, table, column):
    return any(c["name"] == column for c in sa.inspect(bind).get_columns(table))


def _seed_and_backfill():
    bind = op.get_bind()
    stamp = "2026-01-01T00:00:00+00:00"
    ws_id = str(uuid.uuid4())
    existing = bind.execute(sa.text("SELECT id FROM workspaces WHERE code = :code"), {"code": DEFAULT_CODE}).first()
    if not existing:
        bind.execute(sa.text("INSERT INTO workspaces (id, code, name, description, market, base_currency, timezone, owner, is_archived, created_at, updated_at, archived_at)"
            " VALUES (:id, :code, :name, '', 'FX', 'USD', 'UTC', NULL, 0, :now, :now, NULL)"),
            {"id": ws_id, "code": DEFAULT_CODE, "name": DEFAULT_NAME, "now": stamp})
        target = ws_id
    else:
        target = existing[0]
    bind.execute(sa.text("UPDATE experiments SET workspace_id = :w WHERE workspace_id IS NULL"), {"w": target})
    bind.execute(sa.text("UPDATE dataset_snapshots SET workspace_id = :w WHERE workspace_id IS NULL"), {"w": target})
    bind.execute(sa.text("UPDATE search_space_definitions SET workspace_id = :w WHERE workspace_id IS NULL"), {"w": target})


def upgrade():
    bind = op.get_bind()
    if not _has_table(bind, "workspaces"):
        op.create_table("workspaces",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("code", sa.String(24), unique=True, nullable=False),
        sa.Column("name", sa.String(120), nullable=False), sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("market", sa.String(16), nullable=False, server_default=""), sa.Column("base_currency", sa.String(8), nullable=False, server_default=""),
        sa.Column("timezone", sa.String(40), nullable=False, server_default="UTC"), sa.Column("owner", sa.String(120)),
        sa.Column("is_archived", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.String(40), nullable=False), sa.Column("updated_at", sa.String(40), nullable=False), sa.Column("archived_at", sa.String(40)))
    # NOTE: plain columns on SQLite (it cannot ADD COLUMN with REFERENCES);
    # foreign keys are enforced explicitly on other dialects below.
    for table in ("experiments", "dataset_snapshots", "search_space_definitions"):
        if not _has_column(bind, table, "workspace_id"):
            op.add_column(table, sa.Column("workspace_id", sa.String(36)))
    if bind.dialect.name != "sqlite":
        for table in ("experiments", "dataset_snapshots", "search_space_definitions"):
            op.create_foreign_key(f"fk_{table}_workspace", table, "workspaces", ["workspace_id"], ["id"])
    for name, table, column in (("ix_experiments_workspace_id", "experiments", ["workspace_id"]),
                                ("ix_snapshots_workspace_id", "dataset_snapshots", ["workspace_id"]),
                                ("ix_spaces_workspace_id", "search_space_definitions", ["workspace_id"])):
        if name not in {i["name"] for i in sa.inspect(bind).get_indexes(table)}:
            op.create_index(name, table, column)
    _seed_and_backfill()


def downgrade():
    op.drop_index("ix_spaces_workspace_id", table_name="search_space_definitions")
    op.drop_index("ix_snapshots_workspace_id", table_name="dataset_snapshots")
    op.drop_index("ix_experiments_workspace_id", table_name="experiments")
    if op.get_bind().dialect.name != "sqlite":
        for table in ("experiments", "dataset_snapshots", "search_space_definitions"):
            op.drop_constraint(f"fk_{table}_workspace", table, type_="foreignkey")
    op.drop_column("search_space_definitions", "workspace_id")
    op.drop_column("dataset_snapshots", "workspace_id")
    op.drop_column("experiments", "workspace_id")
    op.drop_table("workspaces")
