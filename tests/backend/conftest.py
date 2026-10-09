import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import Settings
from app.core.db import create_session_factory
from app.core.models import Base
from app.core.ports import FeaturePorts
from app.core.seed import SEED_IDS, seed_demo
from app.main import create_app

TEST_URL = "postgresql+psycopg://f1_test:f1_test_local_only@127.0.0.1:55432/f1_test"


@pytest.fixture
def session_factory():
    url = os.environ.get("TEST_DATABASE_URL", TEST_URL)
    schema = "f1_test_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    factory = create_session_factory(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(factory.kw["bind"])
        with factory.begin() as tx:
            seed_demo(tx)
        yield factory
    finally:
        factory.kw["bind"].dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def settings():
    return Settings(database_url=os.environ.get("TEST_DATABASE_URL", TEST_URL),
        session_secret="test-only-session-secret-at-least-32-bytes",
        allowed_origins=("http://testserver", "http://localhost:5173"), agent_mode="fake")


@pytest.fixture
def ports():
    return FeaturePorts()


@pytest.fixture
def demo_ids():
    return SEED_IDS.copy()


@pytest.fixture
def auth_headers():
    return {"Origin": "http://testserver"}


@pytest.fixture
def client(session_factory, settings, ports):
    with TestClient(create_app(settings=settings, ports=ports, session_factory=session_factory)) as value:
        yield value


@pytest.fixture
def login(client, auth_headers):
    def do_login(account_key="reporter", target_client=None):
        target = target_client or client
        response = target.post("/api/v1/demo/session", json={"account_key": account_key}, headers=auth_headers)
        assert response.status_code == 200, response.text
        return target
    return do_login
