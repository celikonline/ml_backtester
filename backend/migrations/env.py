from alembic import context
from backend.platform.db import connect, metadata

def apply(connection):
    context.configure(connection=connection, target_metadata=metadata)
    with context.begin_transaction():
        context.run_migrations()

if context.is_offline_mode():
    raise RuntimeError("Use an online migration connection.")
elif context.config.attributes.get("connection") is not None:
    apply(context.config.attributes["connection"])
else:
    with connect().begin() as connection:
        apply(connection)
