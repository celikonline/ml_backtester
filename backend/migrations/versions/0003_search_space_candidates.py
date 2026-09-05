"""Versioned search spaces and durable candidate registry."""
from alembic import op
import sqlalchemy as sa
revision = "0003_search_space_candidates"
down_revision = "0002_governance"
branch_labels = depends_on = None
def upgrade():
    op.create_table("search_space_definitions", sa.Column("id",sa.String(36),primary_key=True),sa.Column("name",sa.String(120),nullable=False),sa.Column("version",sa.Integer,nullable=False),sa.Column("definition",sa.JSON,nullable=False),sa.Column("owner",sa.String(120),nullable=False),sa.Column("created_at",sa.String(40),nullable=False),sa.Column("archived_at",sa.String(40)))
    op.create_table("optimization_candidates", sa.Column("id",sa.String(36),primary_key=True),sa.Column("experiment_id",sa.String(36),sa.ForeignKey("experiments.id"),nullable=False),sa.Column("candidate_key",sa.String(64),nullable=False),sa.Column("generation",sa.Integer),sa.Column("genome",sa.JSON,nullable=False),sa.Column("metrics",sa.JSON,nullable=False),sa.Column("fitness",sa.Float,nullable=False),sa.Column("pareto_rank",sa.Integer),sa.Column("dominance_count",sa.Integer,nullable=False,server_default="0"),sa.Column("decision",sa.String(40),nullable=False),sa.Column("artifact_ref",sa.Text),sa.Column("created_at",sa.String(40),nullable=False))
    op.create_index("ix_candidates_experiment", "optimization_candidates", ["experiment_id","candidate_key"], unique=True)
def downgrade():
    op.drop_index("ix_candidates_experiment", table_name="optimization_candidates")
    op.drop_table("optimization_candidates")
    op.drop_table("search_space_definitions")
