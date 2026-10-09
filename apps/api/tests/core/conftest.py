import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from alembic import command
from alembic.config import Config

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.core.config import Settings
from app.core.seed import seed


@pytest.fixture
def database():
    url = os.environ.get("F0_TEST_DATABASE_URL")
    if not url:
        pytest.skip("F0_TEST_DATABASE_URL required: real PostgreSQL only")
    admin = create_engine(url, hide_parameters=True)
    if admin.dialect.name != "postgresql":
        pytest.fail("PostgreSQL is required")
    schema = "f0_test_" + uuid4().hex
    with admin.begin() as c:
        c.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"}, hide_parameters=True)
    try:
        config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        with engine.begin() as c:
            config.attributes["connection"] = c
            command.upgrade(config, "head")
            seed(c)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as c:
            c.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def settings():
    return Settings(database_url="postgresql+psycopg://test:unused@localhost/test",
        session_secret="test-only-" * 5, demo_account_switch_enabled=True)


@pytest.fixture
def client(database, settings):
    from fastapi.testclient import TestClient
    from app.main import create_app
    with TestClient(create_app(settings, database)) as c:
        yield c
