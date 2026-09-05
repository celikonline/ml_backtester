"""Request-scoped workspace enforcement.

The active workspace id is carried in a ContextVar populated per request from
`?workspace_id=` (or the `X-Workspace-Id` header). `ExperimentService.get`
rejects cross-workspace reads when a scope is set, so the backend never relies
on frontend filtering alone. Background workers and tests run without a scope
and keep unscoped access.
"""
from contextvars import ContextVar

workspace_scope: ContextVar[str | None] = ContextVar("regimelab_workspace", default=None)
