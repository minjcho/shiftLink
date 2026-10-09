"""F2 table constraints on real PostgreSQL; NOT a full F0 adapter integration test.

Set F2_TEST_DATABASE_URL to a disposable PostgreSQL database. Tests create and
drop ONLY a unique f2_test_* schema. Referenced F0 tables are ID-only test stubs.
"""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import Column, MetaData, Table, Uuid, create_engine, func, insert, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateSchema, DropSchema

from app.features.actions.integrity import approval_payload, canonical_hash
from app.features.actions.tables import define_action_tables
from support import NOW, OWNER, fixture_context, uid


def action_row(**updates):
    row = fixture_context().actions[0].model_dump()
    row["evidence_refs"] = [str(ref) for ref in row["evidence_refs"]]
    row["completion_criteria"] = list(row["completion_criteria"])
    return row | updates


@pytest.fixture
def database():
    url = os.environ.get("F2_TEST_DATABASE_URL")
    if not url:
        pytest.skip("F2_TEST_DATABASE_URL not configured; real PostgreSQL not run")
    engine = create_engine(url)
    if engine.dialect.name != "postgresql":
        pytest.fail("PostgreSQL required; SQLite cannot validate this contract")
    schema = "f2_test_" + uuid4().hex
    metadata = MetaData(schema=schema)
    shared = {name: Table(name, metadata, Column("id", Uuid, primary_key=True))
              for name in ("incidents", "events", "agent_runs", "users", "messages", "evidence")}
    actions, approvals = define_action_tables(metadata)
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    try:
        metadata.create_all(engine)
        with engine.begin() as connection:
            for name, ids in {"incidents": [401], "events": [901], "agent_runs": [601], "users": [202, 203]}.items():
                connection.execute(insert(shared[name]), [{"id": uid(n)} for n in ids])
        yield engine, actions, approvals
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        engine.dispose()


@pytest.mark.parametrize("updates", [
    {"action_generation": 2}, {"version": 0}, {"status": "UNKNOWN"}, {"completion_criteria": []},
    {"evidence_refs": []}, {"scope": " "}, {"is_required": False},
    {"status": "COMPLETED"}, {"status": "IN_PROGRESS"}, {"assignee_id": uid(999)},
])
def test_database_rejects_invalid_action(database, updates):
    engine, actions, _ = database
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(insert(actions), action_row(**updates))


def test_rejected_generation_cannot_be_recreated(database):
    engine, actions, _ = database
    with engine.begin() as connection:
        connection.execute(insert(actions), action_row(status="REJECTED"))
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(insert(actions), action_row(id=uuid4()))


def test_concurrent_proposals_have_one_database_winner(database):
    engine, actions, _ = database
    barrier = Barrier(2)
    def propose(_):
        try:
            with engine.begin() as connection:
                connection.execute(text("SET LOCAL lock_timeout = '5s'"))
                barrier.wait(timeout=10)
                connection.execute(insert(actions), action_row(id=uuid4()))
            return "created"
        except IntegrityError:
            return "duplicate"
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(propose, range(2)))
    assert sorted(results) == ["created", "duplicate"]
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(actions)) == 1


def test_one_approval_decision_per_revision(database):
    engine, actions, approvals = database
    payload = approval_payload(fixture_context().actions[0])
    row = {"id": uuid4(), "action_id": uid(501), "action_revision": 1, "decision": "APPROVE",
           "reason": "범위 확인", "payload_hash": canonical_hash(payload),
           "approved_payload_snapshot": payload, "actor_id": OWNER.user_id, "created_at": NOW}
    with engine.begin() as connection:
        connection.execute(insert(actions), action_row())
        connection.execute(insert(approvals), row)
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(insert(approvals), row | {"id": uuid4(), "decision": "REJECT"})
