"""Auth tables: users, tokens, workspace partnerships."""
from alembic import op
import sqlalchemy as sa


revision = "0013_auth"
down_revision = "0012_notebook_lab"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "auth_users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(256), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("password_salt", sa.String(32), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("last_login_at", sa.String(40), nullable=True),
        sa.Column("features", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("workspace_id", sa.String(36), nullable=True),
    )
    op.create_index("ix_auth_users_workspace", "auth_users", ["workspace_id"])

    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("issued_at", sa.String(40), nullable=False),
        sa.Column("expires_at", sa.String(40), nullable=False),
        sa.Column("revoked", sa.Integer, nullable=False, server_default="0"),
        sa.Column("user_agent", sa.String(256), nullable=True),
    )
    op.create_index("ix_auth_tokens_user", "auth_tokens", ["user_id"])
    op.create_index("ix_auth_tokens_expires", "auth_tokens", ["expires_at"])

    op.create_table(
        "workspace_partners",
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="member"),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.PrimaryKeyConstraint("workspace_id", "user_id"),
    )


def downgrade():
    op.drop_table("workspace_partners")
    op.drop_table("auth_tokens")
    op.drop_table("auth_users")