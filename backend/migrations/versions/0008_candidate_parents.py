"""GA candidate lineage: which evaluated candidates bred each child."""
from alembic import op
import sqlalchemy as sa
revision = "0008_candidate_parents"
down_revision = "0007_workspace_budgets"
branch_labels = depends_on = None
def upgrade():
    op.create_table("candidate_parents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("child_id", sa.String(36), sa.ForeignKey("optimization_candidates.id"), nullable=False),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("optimization_candidates.id"), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False))
    op.create_index("ix_candidate_parents_child", "candidate_parents", ["child_id", "parent_id"], unique=True)
def downgrade():
    op.drop_index("ix_candidate_parents_child", table_name="candidate_parents")
    op.drop_table("candidate_parents")
