"""Sealed-test, budget and lineage governance."""
from alembic import op
import sqlalchemy as sa

revision = "0002_governance"
down_revision = "0001_registry"
branch_labels = depends_on = None

def upgrade():
    op.create_table("test_seals", sa.Column("seal_id", sa.String(36), primary_key=True), sa.Column("test_dataset_id", sa.String(64), sa.ForeignKey("dataset_snapshots.id"), unique=True, nullable=False), sa.Column("access_count", sa.Integer, nullable=False, server_default="0"), sa.Column("first_opened_at", sa.String(40)), sa.Column("invalidated_at", sa.String(40)), sa.Column("invalidation_reason", sa.Text), sa.Column("created_at", sa.String(40), nullable=False))
    op.create_table("test_access_events", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True), sa.Column("seal_id", sa.String(36), sa.ForeignKey("test_seals.seal_id"), nullable=False), sa.Column("experiment_id", sa.String(36), sa.ForeignKey("experiments.id"), nullable=False), sa.Column("run_id", sa.String(36), sa.ForeignKey("experiment_runs.id")), sa.Column("actor", sa.String(120), nullable=False), sa.Column("purpose", sa.String(80), nullable=False), sa.Column("created_at", sa.String(40), nullable=False))
    op.create_table("research_budgets", sa.Column("id", sa.String(120), primary_key=True), sa.Column("limits", sa.JSON, nullable=False), sa.Column("created_at", sa.String(40), nullable=False), sa.Column("updated_at", sa.String(40), nullable=False))
    op.create_table("research_trial_events", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True), sa.Column("budget_id", sa.String(120), sa.ForeignKey("research_budgets.id"), nullable=False), sa.Column("experiment_id", sa.String(36), sa.ForeignKey("experiments.id")), sa.Column("event_type", sa.String(80), nullable=False), sa.Column("quantity", sa.Integer, nullable=False, server_default="1"), sa.Column("details", sa.JSON, nullable=False), sa.Column("created_at", sa.String(40), nullable=False))
    op.create_table("experiment_edges", sa.Column("id", sa.Integer, primary_key=True, autoincrement=True), sa.Column("from_experiment_id", sa.String(36), sa.ForeignKey("experiments.id"), nullable=False), sa.Column("to_experiment_id", sa.String(36), sa.ForeignKey("experiments.id"), nullable=False), sa.Column("relation_type", sa.String(40), nullable=False), sa.Column("reason_code", sa.String(80)), sa.Column("actor_type", sa.String(40), nullable=False), sa.Column("change_summary", sa.JSON, nullable=False), sa.Column("created_at", sa.String(40), nullable=False))

def downgrade():
    for table in ["experiment_edges", "research_trial_events", "research_budgets", "test_access_events", "test_seals"]: op.drop_table(table)
