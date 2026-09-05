"""Research assistant configurations and task history."""
from alembic import op
import sqlalchemy as sa

revision = "0010_assistants"
down_revision = "0009_feature_intelligence"
branch_labels = depends_on = None


def upgrade():
    op.create_table("ai_assistants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id")),
        sa.Column("config", sa.JSON, nullable=False),
        sa.Column("author", sa.String(120), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False))
    op.create_table("ai_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id")),
        sa.Column("assistant_id", sa.String(80), nullable=False),
        sa.Column("assistant_name", sa.String(120), nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("output", sa.Text, nullable=False),
        sa.Column("details", sa.JSON, nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False))


def downgrade():
    op.drop_table("ai_tasks")
    op.drop_table("ai_assistants")
