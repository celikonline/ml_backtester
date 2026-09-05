"""Candidate fold metrics become durable rows instead of living only in result.json."""
from alembic import op
import sqlalchemy as sa
revision = "0014_candidate_fold_metrics"
down_revision = "0013_auth"
branch_labels = depends_on = None


def upgrade():
    bind = op.get_bind()
    if not any(c["name"] == "fold_metrics" for c in sa.inspect(bind).get_columns("optimization_candidates")):
        op.add_column("optimization_candidates", sa.Column("fold_metrics", sa.JSON))


def downgrade():
    op.drop_column("optimization_candidates", "fold_metrics")
