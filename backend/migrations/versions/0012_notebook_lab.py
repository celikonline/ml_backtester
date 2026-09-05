"""Notebook Lab schemas: environments, notebooks, versions, runs, events, secrets."""
from alembic import op
import sqlalchemy as sa

revision = "0012_notebook_lab"
down_revision = "0011_audit_workspace"
branch_labels = depends_on = None


def _has_table(bind, table):
    return table in sa.inspect(bind).get_table_names()


def upgrade():
    bind = op.get_bind()

    if not _has_table(bind, "notebook_environments"):
        op.create_table(
            "notebook_environments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("environment_code", sa.String(80), unique=True, nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("python_version", sa.String(20), nullable=False, server_default="3.11"),
            sa.Column("image_ref", sa.String(200)),
            sa.Column("package_lock_hash", sa.String(64)),
            sa.Column("requirements", sa.Text),
            sa.Column("supports_gpu", sa.Integer, nullable=False, server_default="0"),
            sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
            sa.Column("created_at", sa.String(40), nullable=False),
            sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id")),
        )
        op.create_index("ix_nb_environments_workspace", "notebook_environments", ["workspace_id"])

    if not _has_table(bind, "notebooks"):
        op.create_table(
            "notebooks",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("notebook_code", sa.String(40), unique=True, nullable=False),
            sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("description", sa.Text, nullable=False, server_default=""),
            sa.Column("source_filename", sa.String(200), nullable=False),
            sa.Column("storage_path", sa.Text, nullable=False),
            sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("version", sa.Integer, nullable=False, server_default="1"),
            sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
            sa.Column("default_environment_id", sa.String(36), sa.ForeignKey("notebook_environments.id")),
            sa.Column("tags", sa.JSON),
            sa.Column("created_by", sa.String(120), nullable=False),
            sa.Column("created_at", sa.String(40), nullable=False),
            sa.Column("updated_at", sa.String(40), nullable=False),
            sa.Column("archived_at", sa.String(40)),
        )
        op.create_index("ix_notebooks_workspace", "notebooks", ["workspace_id"])

    if not _has_table(bind, "notebook_versions"):
        op.create_table(
            "notebook_versions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("notebook_id", sa.String(36), sa.ForeignKey("notebooks.id"), nullable=False),
            sa.Column("version", sa.Integer, nullable=False),
            sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("storage_path", sa.Text, nullable=False),
            sa.Column("change_summary", sa.Text, nullable=False, server_default=""),
            sa.Column("created_by", sa.String(120), nullable=False),
            sa.Column("created_at", sa.String(40), nullable=False),
        )
        op.create_index("ix_nb_versions_notebook", "notebook_versions", ["notebook_id", "version"], unique=True)

    if not _has_table(bind, "notebook_runs"):
        op.create_table(
            "notebook_runs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("run_code", sa.String(40), unique=True, nullable=False),
            sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False),
            sa.Column("notebook_id", sa.String(36), sa.ForeignKey("notebooks.id"), nullable=False),
            sa.Column("notebook_version_id", sa.String(36), sa.ForeignKey("notebook_versions.id"), nullable=False),
            sa.Column("experiment_id", sa.String(36), sa.ForeignKey("experiments.id")),
            sa.Column("dataset_snapshot_id", sa.String(64), sa.ForeignKey("dataset_snapshots.id")),
            sa.Column("environment_id", sa.String(36), sa.ForeignKey("notebook_environments.id")),
            sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
            sa.Column("parameters", sa.JSON, nullable=False),
            sa.Column("runtime_metadata", sa.JSON, nullable=False),
            sa.Column("network_mode", sa.String(30), nullable=False, server_default="SNAPSHOT_ONLY"),
            sa.Column("job_pid", sa.Integer),
            sa.Column("started_at", sa.String(40)),
            sa.Column("completed_at", sa.String(40)),
            sa.Column("duration_seconds", sa.Float),
            sa.Column("exit_code", sa.Integer),
            sa.Column("error_type", sa.String(80)),
            sa.Column("error_message", sa.Text),
            sa.Column("executed_notebook_path", sa.Text),
            sa.Column("metrics", sa.JSON),
            sa.Column("artifact_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("cancel_requested", sa.Integer, nullable=False, server_default="0"),
            sa.Column("created_by", sa.String(120), nullable=False),
            sa.Column("created_at", sa.String(40), nullable=False),
        )
        op.create_index("ix_nb_runs_workspace", "notebook_runs", ["workspace_id"])
        op.create_index("ix_nb_runs_notebook", "notebook_runs", ["notebook_id"])
        op.create_index("ix_nb_runs_experiment", "notebook_runs", ["experiment_id"])

    if not _has_table(bind, "notebook_run_events"):
        op.create_table(
            "notebook_run_events",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("run_id", sa.String(36), sa.ForeignKey("notebook_runs.id"), nullable=False),
            sa.Column("type", sa.String(80), nullable=False),
            sa.Column("payload", sa.JSON, nullable=False),
            sa.Column("created_at", sa.String(40), nullable=False),
        )
        op.create_index("ix_nb_run_events_run", "notebook_run_events", ["run_id", "id"])

    if not _has_table(bind, "workspace_secrets"):
        op.create_table(
            "workspace_secrets",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False),
            sa.Column("key_name", sa.String(120), nullable=False),
            sa.Column("encrypted_value", sa.Text, nullable=False),
            sa.Column("description", sa.Text, nullable=False, server_default=""),
            sa.Column("created_by", sa.String(120), nullable=False),
            sa.Column("created_at", sa.String(40), nullable=False),
            sa.Column("updated_at", sa.String(40), nullable=False),
            sa.UniqueConstraint("workspace_id", "key_name", name="uq_workspace_secrets"),
        )
        op.create_index("ix_workspace_secrets_workspace", "workspace_secrets", ["workspace_id"])


def downgrade():
    op.drop_table("workspace_secrets")
    op.drop_table("notebook_run_events")
    op.drop_table("notebook_runs")
    op.drop_table("notebook_versions")
    op.drop_table("notebooks")
    op.drop_table("notebook_environments")
