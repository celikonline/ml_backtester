"""Auth hardening: updated_at column and first-admin bootstrap backfill."""
from alembic import op
import sqlalchemy as sa
revision = "0015_auth_admin"
down_revision = "0014_candidate_fold_metrics"
branch_labels = depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("auth_users"):
        return
    if not any(c["name"] == "updated_at" for c in inspector.get_columns("auth_users")):
        op.add_column("auth_users", sa.Column("updated_at", sa.String(40)))
    admin = bind.execute(sa.text("SELECT id FROM auth_users WHERE role='admin' LIMIT 1")).first()
    if admin is None:
        first = bind.execute(sa.text(
            "SELECT id FROM auth_users WHERE email != 'demo@regimelab.io' ORDER BY created_at LIMIT 1")).first()
        if first is not None:
            bind.execute(sa.text("UPDATE auth_users SET role='admin' WHERE id=:id"), {"id": first[0]})


def downgrade():
    bind = op.get_bind()
    if sa.inspect(bind).has_table("auth_users"):
        op.drop_column("auth_users", "updated_at")

