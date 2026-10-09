"""Real PostgreSQL tool/retry interleavings; no sleep-selected transaction winner."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
from threading import Event as ThreadEvent
import time
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select, text

from app.agent import tools as tool_module
from app.agent.jobs import LostLease, claim_job, prepare_run
from app.core.models import ActionDraft, AgentRun, Evidence, Incident, Job, Message, utcnow
from app.core.ports import FeaturePorts
from app.core.transactions import enqueue_job, new_event
from app.features.intake import service


def prepared(factory, ids):
    with factory.begin() as tx:
        incident = Incident(id=str(uuid4()), display_id=f"LOCK-{uuid4()}", site_id=ids["site"],
            equipment_id=ids["equipment"], reporter_id=ids["reporter"],
            origin_shift_occurrence_id=ids["outgoing_shift"], owner_shift_occurrence_id=ids["outgoing_shift"],
            owner_id=ids["outgoing_supervisor"], status="INVESTIGATING")
        tx.add(incident)
        tx.flush()
        tx.add(Message(site_id=incident.site_id, incident_id=incident.id, author_id=ids["reporter"],
            kind="REPORT", text="CV-03 기록 범위를 확인합니다."))
        enqueue_job(tx, incident, new_event(tx, incident, "REPORT_CREATED"))
    identity = claim_job(factory, mode="fake", model_id="test-lock-order")
    return prepare_run(factory, identity, FeaturePorts())


def arguments(tool, context, ids):
    if tool == "propose_action":
        return {"scope": "기록 범위 확인", "completion_criteria": ["차이를 기록"],
            "source_refs": sorted(context.source_ids)}
    return {"equipment_id": ids["equipment"], "query": "점검"}


def wait_for_database_lock(factory, pid):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with factory() as tx:
            waiting = tx.scalar(text("SELECT wait_event_type = 'Lock' FROM pg_stat_activity WHERE pid=:pid"), {"pid": pid})
        if waiting:
            return
        time.sleep(0.01)
    pytest.fail("The competing connection never reached a PostgreSQL lock wait")


@pytest.mark.ac27
@pytest.mark.ac29
@pytest.mark.ac34
@pytest.mark.parametrize("tool", ["propose_action", "search_documents"])
def test_tool_insert_and_running_retry_follow_one_lock_order(tool, session_factory, demo_ids, client, login, auth_headers, monkeypatch):
    context = prepared(session_factory, demo_ids)
    login("outgoing_supervisor")
    tool_fenced, retry_entered, release_tool = ThreadEvent(), ThreadEvent(), ThreadEvent()
    original_fence, original_lock = tool_module.fence, service.lock_incident
    first_fence, retry_pid, errors = [True], [], []

    def observe_error(ctx):
        errors.append(getattr(ctx.original_exception, "sqlstate", None))

    def pause_after_first_fence(tx, identity):
        result = original_fence(tx, identity)
        if first_fence[0]:
            first_fence[0] = False
            tool_fenced.set()
            assert release_tool.wait(10), "test coordinator did not release the tool"
        return result

    def observe_retry(tx, incident_id, principal):
        retry_pid.append(tx.scalar(text("SELECT pg_backend_pid()")))
        retry_entered.set()
        return original_lock(tx, incident_id, principal)

    monkeypatch.setattr(tool_module, "fence", pause_after_first_fence)
    monkeypatch.setattr(service, "lock_incident", observe_retry)
    engine = session_factory.kw["bind"]
    event.listen(engine, "handle_error", observe_error)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            executor = tool_module.ToolExecutor(session_factory, context, deadline_at=time.monotonic() + 20)
            tool_future = pool.submit(executor, tool, json.dumps(arguments(tool, context, demo_ids)))
            assert tool_fenced.wait(5)
            retry_future = pool.submit(client.post, f"/api/v1/jobs/{context.identity.job_id}/retry", json={},
                headers={**auth_headers, "Idempotency-Key": str(uuid4())})
            try:
                assert retry_entered.wait(5)
                wait_for_database_lock(session_factory, retry_pid[0])
            finally:
                release_tool.set()
            tool_result = tool_future.result(timeout=15)
            retry = retry_future.result(timeout=15)
    finally:
        release_tool.set()
        event.remove(engine, "handle_error", observe_error)
    assert "40P01" not in errors, errors
    assert tool_result["outcome"] == "OK"
    assert retry.status_code == 409, retry.text
    assert retry.json()["error"]["code"] == "INVALID_STATE"
    with session_factory() as tx:
        assert tx.get(Incident, context.identity.incident_id).version == context.identity.input_version
        assert tx.get(Job, context.identity.job_id).status == "RUNNING"
        if tool == "propose_action":
            assert tx.scalar(select(func.count()).select_from(ActionDraft)) == 1
        else:
            assert tool_result["source_refs"]
            assert tx.scalar(select(func.count()).select_from(Evidence)) > len(context.payload["messages"])


@pytest.mark.ac27
@pytest.mark.parametrize("mutation", ["expired", "reclaimed"])
def test_tool_waiting_on_incident_rechecks_lease_before_persisting(mutation, session_factory, demo_ids):
    context = prepared(session_factory, demo_ids)
    identity = context.identity
    entered, pid = ThreadEvent(), []
    # The engine event observes this tool's first Incident lock statement without
    # replacing its result or the lease check. The blocker owns only fixture rows.
    engine = session_factory.kw["bind"]
    def observe_lock(connection, cursor, statement, parameters, execution_context, executemany):
        if "FROM incidents" in statement and "FOR UPDATE" in statement:
            pid.append(connection.exec_driver_sql("SELECT pg_backend_pid()").scalar())
            entered.set()
    event.listen(engine, "before_cursor_execute", observe_lock)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with session_factory.begin() as blocker:
                blocker.execute(text("SELECT id FROM incidents WHERE id=:id FOR UPDATE"), {"id": identity.incident_id})
                pid.clear()
                entered.clear()
                executor = tool_module.ToolExecutor(session_factory, context, deadline_at=time.monotonic() + 20)
                future = pool.submit(executor, "propose_action", json.dumps(arguments("propose_action", context, demo_ids)))
                assert entered.wait(5)
                wait_for_database_lock(session_factory, pid[-1])
                job = blocker.get(Job, identity.job_id)
                if mutation == "expired":
                    job.lease_expires_at = utcnow() - timedelta(seconds=1)
                else:
                    job.attempt += 1
                    job.lease_token = str(uuid4())
                    job.lease_expires_at = utcnow() + timedelta(seconds=90)
            with pytest.raises(LostLease):
                future.result(timeout=15)
    finally:
        event.remove(engine, "before_cursor_execute", observe_lock)
    with session_factory() as tx:
        assert tx.scalar(select(func.count()).select_from(ActionDraft)) == 0
        assert tx.get(AgentRun, identity.run_id).status == "RUNNING"
        assert tx.get(Incident, identity.incident_id).version == identity.input_version
