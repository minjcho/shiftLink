"""F3 HTTP/real PostgreSQL fixtures, isolated from every F1 test and app schema.

Synthetic rows establish inputs only. Every handover and ACK is created through
the actual HTTP routes; this suite is not browser evidence for AC-1/16/17.
"""
from contextlib import ExitStack
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import Settings
from app.core.db import create_session_factory
from app.core.models import Base
from app.core.seed import SEED_IDS, seed_demo
from app.main import create_app

TEST_URL = "postgresql+psycopg://f1_test:f1_test_local_only@127.0.0.1:55432/f1_test"


@pytest.fixture
def session_factory():
    url = os.environ.get("F3_TEST_DATABASE_URL", TEST_URL)
    schema = "f3_test_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    factory = create_session_factory(url, connect_args={
        "options": f"-csearch_path={schema}", "application_name": schema,
    })
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
    return Settings(database_url=os.environ.get("F3_TEST_DATABASE_URL", TEST_URL),
        session_secret="f3-test-session-secret-at-least-32-bytes",
        allowed_origins=("http://testserver", "http://localhost:5173"), agent_mode="fake")


@pytest.fixture
def demo_ids():
    return SEED_IDS.copy()


@pytest.fixture
def app(session_factory, settings):
    result = create_app(settings=settings, session_factory=session_factory)
    assert "/api/v1/handovers" in result.openapi()["paths"], "F3 routes must be registered in the product app"
    return result


@pytest.fixture
def clients(app):
    with ExitStack() as stack:
        cache = {}
        def for_actor(key="outgoing_supervisor"):
            if key not in cache:
                client = stack.enter_context(TestClient(app))
                if key is not None:
                    response = client.post("/api/v1/demo/session", json={"account_key": key},
                                           headers={"Origin": "http://testserver"})
                    assert response.status_code == 200, response.text
                cache[key] = client
            return cache[key]
        yield for_actor
