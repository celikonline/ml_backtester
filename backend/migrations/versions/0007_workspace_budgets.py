"""Per-workspace research budgets; legacy global ledger moves to the default workspace."""
import uuid
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa
revision = "0007_workspace_budgets"
down_revision = "0006_workspaces"
branch_labels = depends_on = None


def _has_column(bind, table, column):
    return any(c["name"] == column for c in sa.inspect(bind).get_columns(table))


def upgrade():
    bind = op.get_bind()
    if not _has_column(bind, "research_budgets", "workspace_id"):
        op.add_column("research_budgets", sa.Column("workspace_id", sa.String(36)))
    if "ix_budgets_workspace_id" not in {i["name"] for i in sa.inspect(bind).get_indexes("research_budgets")}:
        op.create_index("ix_budgets_workspace_id", "research_budgets", ["workspace_id"], unique=True)
    default = bind.execute(sa.text("SELECT id FROM workspaces WHERE code = 'WS-DEFAULT'")).first()
    if default:
        default_id = default[0]
        bind.execute(sa.text("UPDATE research_budgets SET workspace_id = :w WHERE workspace_id IS NULL AND id != 'global'"), {"w": default_id})
        ws_row = bind.execute(sa.text("SELECT id FROM research_budgets WHERE workspace_id = :w"), {"w": default_id}).first()
        legacy = bind.execute(sa.text("SELECT limits FROM research_budgets WHERE id = 'global'")).first()
        if legacy and not ws_row:
            new_id = str(uuid.uuid4())
            stamp = datetime.now(timezone.utc).isoformat()
            bind.execute(sa.text("INSERT INTO research_budgets (id, limits, workspace_id, created_at, updated_at)"
                " VALUES (:id, :limits, :w, :now, :now)"),
                {"id": new_id, "limits": legacy[0], "w": default_id, "now": stamp})
            bind.execute(sa.text("UPDATE research_trial_events SET budget_id = :n WHERE budget_id = 'global'"), {"n": new_id})
            bind.execute(sa.text("DELETE FROM research_budgets WHERE id = 'global'"))
        elif legacy and ws_row:
            bind.execute(sa.text("UPDATE research_trial_events SET budget_id = :w WHERE budget_id = 'global'"), {"w": ws_row[0]})
            bind.execute(sa.text("DELETE FROM research_budgets WHERE id = 'global'"))


def downgrade():
    bind = op.get_bind()
    if not bind.execute(sa.text("SELECT id FROM research_budgets WHERE id = 'global'")).first():
        bind.execute(sa.text("INSERT INTO research_budgets (id, limits, created_at, updated_at) VALUES ('global', :limits, :now, :now)")
            .bindparams(sa.bindparam("limits", type_=sa.JSON)),
            {"limits": {"max_experiments": 50, "max_candidates": 2000, "max_backtests": 2500,
                        "max_sealed_test_accesses": 1, "risk_reject_at": 0.9}, "now": "2026-01-01T00:00:00+00:00"})
    default = bind.execute(sa.text("SELECT id FROM workspaces WHERE code = 'WS-DEFAULT'")).first()
    if default:
        bind.execute(sa.text("UPDATE research_trial_events SET budget_id = 'global' WHERE budget_id = :w"), {"w": default[0]})
        bind.execute(sa.text("DELETE FROM research_budgets WHERE id = :w"), {"w": default[0]})
    op.drop_index("ix_budgets_workspace_id", table_name="research_budgets")
    op.drop_column("research_budgets", "workspace_id")
