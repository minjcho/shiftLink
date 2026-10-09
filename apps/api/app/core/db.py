from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def create_session_factory(database_url: str, **engine_options):
    if not database_url.startswith("postgresql+"):
        raise ValueError("F1 requires PostgreSQL")
    engine = create_engine(database_url, pool_pre_ping=True, **engine_options)
    return sessionmaker(bind=engine, expire_on_commit=False)
