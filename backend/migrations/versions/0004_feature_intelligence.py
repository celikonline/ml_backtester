"""Historical feature intelligence records."""
from alembic import op
import sqlalchemy as sa
revision = "0004_feature_intelligence"
down_revision = "0003_search_space_candidates"
branch_labels = depends_on = None
def upgrade():
    op.create_table("feature_evaluations",sa.Column("id",sa.String(36),primary_key=True),sa.Column("experiment_id",sa.String(36),sa.ForeignKey("experiments.id"),nullable=False),sa.Column("feature",sa.String(160),nullable=False),sa.Column("ic",sa.Float,nullable=False),sa.Column("sign_consistency",sa.Float,nullable=False),sa.Column("mutual_information",sa.Float,nullable=False),sa.Column("missingness",sa.Float,nullable=False),sa.Column("selected",sa.Integer,nullable=False),sa.Column("created_at",sa.String(40),nullable=False))
    op.create_table("feature_stability_runs",sa.Column("id",sa.String(36),primary_key=True),sa.Column("feature_evaluation_id",sa.String(36),sa.ForeignKey("feature_evaluations.id"),nullable=False),sa.Column("window_index",sa.Integer,nullable=False),sa.Column("rolling_ic",sa.Float,nullable=False),sa.Column("created_at",sa.String(40),nullable=False))
    op.create_index("ix_feature_evaluations_experiment","feature_evaluations",["experiment_id","feature"])
def downgrade():
    op.drop_index("ix_feature_evaluations_experiment",table_name="feature_evaluations")
    op.drop_table("feature_stability_runs"); op.drop_table("feature_evaluations")
