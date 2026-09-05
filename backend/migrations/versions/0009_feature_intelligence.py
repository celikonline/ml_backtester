"""Durable feature intelligence: regime metrics, selection events, redundancy."""
from alembic import op
import sqlalchemy as sa
revision = "0009_feature_intelligence"
down_revision = "0008_candidate_parents"
branch_labels = depends_on = None
def upgrade():
    op.create_table("feature_regime_metrics",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("feature_evaluation_id", sa.String(36), sa.ForeignKey("feature_evaluations.id"), nullable=False),
        sa.Column("regime", sa.Integer, nullable=False), sa.Column("bars", sa.Integer, nullable=False),
        sa.Column("share", sa.Float, nullable=False), sa.Column("ic", sa.Float, nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False))
    op.create_index("ix_feature_regime_evaluation", "feature_regime_metrics", ["feature_evaluation_id", "regime"], unique=True)
    op.create_table("feature_selection_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("experiment_id", sa.String(36), sa.ForeignKey("experiments.id"), nullable=False),
        sa.Column("feature", sa.String(160), nullable=False), sa.Column("selected", sa.Integer, nullable=False),
        sa.Column("selection_frequency", sa.Float), sa.Column("top_survival", sa.Float),
        sa.Column("fitness_present", sa.Float), sa.Column("fitness_absent", sa.Float),
        sa.Column("created_at", sa.String(40), nullable=False))
    op.create_index("ix_feature_selection_experiment", "feature_selection_events", ["experiment_id", "feature"], unique=True)
    op.create_table("feature_redundancy_pairs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("experiment_id", sa.String(36), sa.ForeignKey("experiments.id"), nullable=False),
        sa.Column("a", sa.String(160), nullable=False), sa.Column("b", sa.String(160), nullable=False),
        sa.Column("correlation", sa.Float, nullable=False), sa.Column("created_at", sa.String(40), nullable=False))
    op.create_index("ix_feature_redundancy_experiment", "feature_redundancy_pairs", ["experiment_id", "a", "b"], unique=True)
def downgrade():
    op.drop_index("ix_feature_redundancy_experiment", table_name="feature_redundancy_pairs")
    op.drop_table("feature_redundancy_pairs")
    op.drop_index("ix_feature_selection_experiment", table_name="feature_selection_events")
    op.drop_table("feature_selection_events")
    op.drop_index("ix_feature_regime_evaluation", table_name="feature_regime_metrics")
    op.drop_table("feature_regime_metrics")
