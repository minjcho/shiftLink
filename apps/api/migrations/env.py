from alembic import context
from app.core.config import load_settings
from app.core.database import make_engine
from app.core.schema import metadata

if context.is_offline_mode():
    context.configure(dialect_name="postgresql", target_metadata=metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    provided = context.config.attributes.get("connection")
    if provided is not None:
        context.configure(connection=provided, target_metadata=metadata)
        with context.begin_transaction():
            context.run_migrations()
    else:
        engine = make_engine(load_settings())
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=metadata)
            with context.begin_transaction():
                context.run_migrations()
        engine.dispose()
