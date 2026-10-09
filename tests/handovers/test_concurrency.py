"""F3 interleavings on independent real PostgreSQL connections.

Barriers start simultaneous HTTP requests. Ordered races first observe an actual
PostgreSQL row-lock waiter, then release the predecessor; no timing-only sleep is
used to claim which command won. Other-feature mutations are explicit synthetic
inputs, not implementations or end-to-end proof of F2/F4.
"""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from threading import Barrier, Event as ThreadEvent
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.core.auth import Principal, require_owner
from app.core.errors import DomainError
from app.core.models import (Action, AgentRun, CommandReceipt, Event, Handover,
    HandoverAck, HandoverItem, HandoverRevision, Incident, Job, Message, Request,
    ResolutionCase, new_id, utcnow)
from app.core.transactions import bump_incident, enqueue_job, new_event, require_version

from .helpers import ack, ack_body, add_note, count, create, created, error, headers, item_for, read, seed_incident


def concurrent_http(app, account_key, barrier, callback):
    with TestClient(app) as client:
        assert client.post("/api/v1/demo/session", json={"account_key": account_key}, headers=headers()).status_code == 200
        barrier.wait(timeout=10)
        return callback(client)


def wait_for_row_lock(factory, timeout=8):
    """Prove another connection in this test schema has reached a real row lock."""
    with factory() as tx:
        application = tx.scalar(text("SELECT current_setting('application_name')"))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with factory() as tx:
            waiting = tx.scalar(text("""
                SELECT count(*) FROM pg_stat_activity
                WHERE application_name=:application AND pid<>pg_backend_pid()
                  AND wait_event_type='Lock' AND query ILIKE '%FOR UPDATE%'
            """), {"application": application})
        if waiting:
            return
        time.sleep(0.02)
    pytest.fail("The competing PostgreSQL connection never reached the row lock")


@pytest.mark.ac4
@pytest.mark.ac13
def test_concurrent_distinct_keys_create_one_handover_and_item(app, session_factory):
    with session_factory.begin() as tx:
        source = seed_incident(tx)
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(concurrent_http, app, "outgoing_supervisor", barrier, create) for _ in range(2)]
        responses = [f.result(timeout=15) for f in futures]
    assert sorted(r.status_code for r in responses) == [200, 201]
    first, second = [r.json()["data"] for r in responses]
    assert first["id"] == second["id"] and first["cutoff_at"] == second["cutoff_at"]
    assert first["items"][0]["id"] == second["items"][0]["id"]
    with session_factory() as tx:
        assert count(tx, Handover) == count(tx, HandoverItem) == count(tx, HandoverRevision) == 1
        assert count(tx, CommandReceipt) == 2
        assert tx.get(Incident, source["incident"]).version == 4


@pytest.mark.ac12
@pytest.mark.ac13
def test_concurrent_distinct_ack_keys_one_business_effect(app, clients, session_factory):
    with session_factory.begin() as tx:
        seed_incident(tx)
    handover = created(clients())
    item = handover["items"][0]
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(concurrent_http, app, "incoming_supervisor", barrier,
                   lambda actor: ack(actor, handover, item)) for _ in range(2)]
        responses = [f.result(timeout=15) for f in futures]
    assert [r.status_code for r in responses] == [200, 200]
    assert responses[0].json()["data"] == responses[1].json()["data"]
    assert all("Idempotent-Replayed" not in r.headers for r in responses)
    with session_factory() as tx:
        assert count(tx, HandoverAck) == count(tx, Event) == 1
        assert tx.get(Incident, item["incident_id"]).version == 5
        assert count(tx, CommandReceipt) == 3


@pytest.mark.ac12
@pytest.mark.parametrize("operation", ["create", "ack"])
def test_in_progress_receipt_lock_returns_explicit_409_without_effect(operation, clients, session_factory, demo_ids):
    with session_factory.begin() as tx:
        source = seed_incident(tx)
    handover = created(clients()) if operation == "ack" else None
    actor = "incoming_supervisor" if operation == "ack" else "outgoing_supervisor"
    client, key = clients(actor), str(uuid4())
    lock_key = int.from_bytes(sha256(f'{demo_ids["site"]}:{demo_ids[actor]}:{key}'.encode()).digest()[:8], "big", signed=True)
    with session_factory.begin() as tx:
        tx.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
        response = ack(client, handover, handover["items"][0], key=key) if handover else create(client, key=key)
        error(response, 409, "COMMAND_IN_PROGRESS")
    with session_factory() as tx:
        assert tx.get(Incident, source["incident"]).version == 4 and count(tx, HandoverAck) == 0
        assert count(tx, CommandReceipt, CommandReceipt.idempotency_key == key) == 0
    succeeded = ack(client, handover, handover["items"][0], key=key) if handover else create(client, key=key)
    assert succeeded.status_code == (200 if handover else 201)


@pytest.mark.ac9
@pytest.mark.ac13
@pytest.mark.ac14
@pytest.mark.parametrize("change", ["new_information", "result", "resolved"])
def test_business_change_commits_before_waiting_ack_no_partial_transfer(change, clients, session_factory, app, demo_ids):
    with session_factory.begin() as tx:
        source = seed_incident(tx)
    handover = created(clients())
    item, incoming = handover["items"][0], clients("incoming_supervisor")
    key, started = str(uuid4()), ThreadEvent()
    def send_ack():
        started.set()
        return ack(incoming, handover, item, key=key)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with session_factory.begin() as tx:
            incident = tx.scalar(select(Incident).where(Incident.id == source["incident"]).with_for_update())
            future = pool.submit(send_ack)
            assert started.wait(5)
            wait_for_row_lock(session_factory)
            assert not future.done()
            if change == "resolved":
                incident.status, incident.resolved_at = "RESOLVED", utcnow()
                tx.add(ResolutionCase(incident_id=incident.id, site_id=incident.site_id,
                    equipment_id=incident.equipment_id, title="합성 경합 해결", resolved_version=5,
                    snapshot_json={"owner_id": demo_ids["outgoing_supervisor"], "version": 5}))
            else:
                message = Message(id=new_id(), site_id=incident.site_id, incident_id=incident.id,
                    author_id=demo_ids["maintainer"], kind="ACTION_RESULT" if change == "result" else "NOTE",
                    action_id=source["action"] if change == "result" else None, text="경합 중 확정된 합성 입력")
                tx.add(message)
                tx.flush()
                if change == "result":
                    action = tx.scalar(select(Action).where(Action.id == source["action"]).with_for_update())
                    action.status, action.result_message_id = "COMPLETED", message.id
                    incident.status = "PENDING_VERIFICATION"
            event = new_event(tx, incident, "synthetic_" + change, demo_ids["outgoing_supervisor"])
            bump_incident(tx, incident, event, app.state.ports)
        response = future.result(timeout=10)
    error(response, 409, "INCIDENT_RESOLVED" if change == "resolved" else "HANDOVER_STALE")
    with session_factory() as tx:
        incident = tx.get(Incident, source["incident"])
        assert incident.version == 5 and incident.owner_id == demo_ids["outgoing_supervisor"]
        assert count(tx, HandoverAck) == 0
        assert tx.get(HandoverItem, item["id"]).latest_revision == 2
        assert tx.get(HandoverRevision, (item["id"], 1)).snapshot_json == item["snapshot"]
        assert count(tx, CommandReceipt, CommandReceipt.idempotency_key == key) == (1 if change == "resolved" else 0)
        assert count(tx, Event, Event.type == "rejected_input") == (1 if change == "resolved" else 0)
        if change == "resolved":
            case = tx.scalar(select(ResolutionCase).where(ResolutionCase.incident_id == source["incident"]))
            assert case.snapshot_json == {"owner_id": demo_ids["outgoing_supervisor"], "version": 5}


@pytest.mark.ac13
@pytest.mark.ac14
def test_ack_first_rejects_waiting_old_owner_resolution_input(clients, session_factory, app, demo_ids, monkeypatch):
    from app.features.handovers import service
    with session_factory.begin() as tx:
        source = seed_incident(tx)
    handover = created(clients())
    item = handover["items"][0]
    acknowledged, release = ThreadEvent(), ThreadEvent()
    original = service.acknowledge
    def pause_before_commit(*args, **kwargs):
        result = original(*args, **kwargs)
        acknowledged.set()
        assert release.wait(10), "test coordinator did not release ACK transaction"
        return result
    monkeypatch.setattr(service, "acknowledge", pause_before_commit)
    outgoing = Principal(demo_ids["outgoing_supervisor"], demo_ids["site"], "supervisor", "출발 책임자")
    def synthetic_old_owner_decision():
        try:
            with session_factory.begin() as tx:
                incident = tx.scalar(select(Incident).where(Incident.id == source["incident"]).with_for_update())
                observed = (incident.owner_id, incident.version)
                require_owner(outgoing, incident)
                require_version(incident, 4)
                pytest.fail("old owner and version must never authorize resolution after ACK")
        except DomainError as exc:
            return observed, exc.status_code
    incoming = clients("incoming_supervisor")
    with ThreadPoolExecutor(max_workers=2) as pool:
        ack_future = pool.submit(ack, incoming, handover, item)
        assert acknowledged.wait(5)
        decision_future = pool.submit(synthetic_old_owner_decision)
        try:
            wait_for_row_lock(session_factory)
        finally:
            release.set()
        response = ack_future.result(timeout=10)
        observed, denied = decision_future.result(timeout=10)
    assert response.status_code == 200
    assert observed == (demo_ids["incoming_supervisor"], 5) and denied == 403
    with session_factory() as tx:
        assert tx.get(Incident, source["incident"]).status == "IN_PROGRESS"
        assert count(tx, ResolutionCase, ResolutionCase.incident_id == source["incident"]) == 0
        assert count(tx, HandoverAck) == 1


@pytest.mark.ac13
def test_ack_transaction_failure_after_owner_ack_event_rolls_everything_back(clients, session_factory, monkeypatch, demo_ids):
    from app.features.handovers import service
    with session_factory.begin() as tx:
        source = seed_incident(tx)
    handover = created(clients())
    key = str(uuid4())
    original = service.new_event
    def fail_after_event(*args, **kwargs):
        event = original(*args, **kwargs)
        assert event.type == "handover_acknowledged"
        raise DomainError(503, "SERVICE_UNAVAILABLE", "injected transaction failure")
    monkeypatch.setattr(service, "new_event", fail_after_event)
    error(ack(clients("incoming_supervisor"), handover, handover["items"][0], key=key), 503)
    with session_factory() as tx:
        incident = tx.get(Incident, source["incident"])
        assert (incident.owner_id, incident.owner_shift_occurrence_id, incident.version) == (
            demo_ids["outgoing_supervisor"], demo_ids["outgoing_shift"], 4)
        assert count(tx, HandoverAck) == count(tx, Event) == 0
        assert count(tx, CommandReceipt, CommandReceipt.idempotency_key == key) == 0
    monkeypatch.setattr(service, "new_event", original)
    assert ack(clients("incoming_supervisor"), handover, handover["items"][0], key=key).status_code == 200


@pytest.mark.ac9
@pytest.mark.ac13
def test_real_f3_revision_failure_rolls_back_f1_input_job_event_and_receipt(clients, session_factory, app):
    with session_factory.begin() as tx:
        source = seed_incident(tx)
    handover = created(clients())
    item = handover["items"][0]
    original = app.state.ports.handover_refresher
    def fail_after_revision(tx, **kwargs):
        original(tx, **kwargs)
        assert tx.get(HandoverItem, item["id"]).latest_revision == 2
        raise DomainError(503, "SERVICE_UNAVAILABLE", "injected after real revision flush")
    app.state.ports.handover_refresher = fail_after_revision
    with session_factory() as tx:
        initial = tuple(count(tx, model) for model in (Message, Job, Event, CommandReceipt))
    error(add_note(clients("reporter"), source["incident"], 4), 503)
    with session_factory() as tx:
        assert tuple(count(tx, model) for model in (Message, Job, Event, CommandReceipt)) == initial
        assert tx.get(Incident, source["incident"]).version == 4
        assert tx.get(HandoverItem, item["id"]).latest_revision == 1
        assert tx.get(HandoverRevision, (item["id"], 2)) is None
        assert tx.get(HandoverRevision, (item["id"], 1)).snapshot_json == item["snapshot"]


@pytest.mark.ac18
def test_real_f1_finalizer_with_current_lease_superseded_by_actual_http_ack(clients, session_factory, app):
    from app.agent.finalizer import finalize
    from app.agent.jobs import claim_job, prepare_run
    from app.agent.runner import AgentExecution
    from app.agent.schemas import FinalDecision
    with session_factory.begin() as tx:
        source = seed_incident(tx)
        incident = tx.get(Incident, source["incident"])
        trigger = new_event(tx, incident, "synthetic_investigation_requested")
        enqueue_job(tx, incident, trigger)
        original_analysis = incident.analysis.copy()
    identity = claim_job(session_factory, mode="fake", model_id="f3-deterministic-finalizer", metadata={})
    context = prepare_run(session_factory, identity, app.state.ports)
    assert context.identity.input_version == 4
    handover = created(clients())
    assert ack(clients("incoming_supervisor"), handover, handover["items"][0]).status_code == 200
    decision = FinalDecision.model_validate({"facts": [], "hypotheses": [], "missing_information": [],
        "decision": "BLOCKED", "questions": [], "selected_draft_id": None, "existing_request_ids": [],
        "existing_action_ids": [], "source_refs": [], "reason": "deterministic old-version run"})
    result = finalize(session_factory, context.identity,
        AgentExecution(final=decision, mode="fake", model_id="f3-deterministic-finalizer"), app.state.ports)
    assert result["status"] == "SUPERSEDED"
    with session_factory() as tx:
        assert tx.get(AgentRun, identity.run_id).status == "SUPERSEDED"
        assert tx.get(Incident, source["incident"]).analysis == original_analysis
        assert tx.get(Incident, source["incident"]).version == 5
        assert count(tx, Request, Request.incident_id == source["incident"]) == 2
        assert count(tx, Action, Action.incident_id == source["incident"]) == 1
        assert count(tx, HandoverAck) == 1
    current = item_for(read(clients("incoming_supervisor"), handover["id"]), source["incident"])
    assert current["ack_status"] == "ACKNOWLEDGED" and not current["is_stale"]
