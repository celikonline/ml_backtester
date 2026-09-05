"""Workspace attribution for audit logs; old rows stay NULL (pre-attribution)."""
from alembic import op
import sqlalchemy as sa
revision = "0011_audit_workspace"
down_revision = "0010_assistants"
branch_labels = depends_on = None


def _has_column(bind, table, column):
    return any(c["name"] == column for c in sa.inspect(bind).get_columns(table))


def upgrade():
    bind = op.get_bind()
    if not _has_column(bind, "audit_logs", "workspace_id"):
        op.add_column("audit_logs", sa.Column("workspace_id", sa.String(36)))
    if "ix_audits_workspace_id" not in {i["name"] for i in sa.inspect(bind).get_indexes("audit_logs")}:
        op.create_index("ix_audits_workspace_id", "audit_logs", ["workspace_id"])


def downgrade():
    op.drop_index("ix_audits_workspace_id", table_name="audit_logs")
    op.drop_column("audit_logs", "workspace_id")
