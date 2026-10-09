import os
from alembic import context
from sqlalchemy import create_engine
from app.core.models import Base

config = context.config
target_metadata = Base.metadata
url = os.environ.get("DATABASE_URL")
if not url or not url.startswith("postgresql+"):
    raise RuntimeError("DATABASE_URL must explicitly select PostgreSQL")

if context.is_offline_mode():
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with create_engine(url).connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
