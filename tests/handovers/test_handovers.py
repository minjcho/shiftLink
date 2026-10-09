"""F3 contract assertions at real HTTP, PostgreSQL, and shared F1-port boundaries.

Markers AC-1/16/17 in this file cover only the server portion of those criteria.
scripts/check_f3.py additionally requires the real-browser suite for each.
"""
from copy import deepcopy
from datetime import timedelta
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError

from app.core.errors import DomainError
from app.core.models import (Action, AgentRun, Approval, CommandReceipt, Event, Handover,
    HandoverAck, HandoverItem, HandoverRevision, Incident, Job, Message, Request,
    ResolutionCase, Shift, ShiftAssignment, User, new_id, utcnow)
from app.core.transactions import bump_incident, new_event
from app.main import create_app

from .helpers import (ack, ack_body, add_note, count, create, created, error, headers,
                      input_state, item_for, pair, read, seed_incident, seed_waits)


@pytest.mark.ac1
@pytest.mark.ac7
@pytest.mark.ac8
@pytest.mark.ac15
@pytest.mark.ac16
def test_ack_persists_same_identifiers_and_shared_detail_across_app_recreation(
        clients, session_factory, settings, demo_ids):
    with session_factory.begin() as tx:
        source = seed_incident(tx)
        untouched = seed_incident(tx)
    outgoing, incoming = clients(), clients("incoming_supervisor")
    handover = created(outgoing)
    item = item_for(handover, source["incident"])
    with session_factory() as tx:
        before = input_state(tx, source["incident"])
    response = ack(incoming, handover, item)
    assert response.status_code == 200, response.text
    result = response.json()["data"]
    assert result["item_id"] == item["id"]
    assert result["revision"] == item["revision"] == 1
    assert result["snapshot_version"] == 4
    assert result["ack_applied_version"] == result["incident_version"] == 5
    assert result["owner_id"] == result["acknowledged_by"] == demo_ids["incoming_supervisor"]
    assert result["assignee_id"] == demo_ids["maintainer"]
    assert result["acknowledged_at"]
    for current in (read(incoming, handover["id"]), created(outgoing)):
        now = item_for(current, source["incident"])
        assert now["ack_status"] == "ACKNOWLEDGED"
        assert not now["is_stale"] and not now["requires_ack"]
        assert now["current_analysis_is_stale"] is True
        assert now["revision"] == 1 and now["snapshot"] == item["snapshot"]
        assert item_for(current, untouched["incident"])["ack_status"] != "ACKNOWLEDGED"
    # Recreate the ASGI app with a fresh session pool view; browser check separately
    # restarts the real HTTP process, so this is not labeled process-restart proof.
    with TestClient(create_app(settings=settings, session_factory=session_factory)) as restarted:
        assert restarted.post("/api/v1/demo/session", json={"account_key": "incoming_supervisor"},
                              headers=headers()).status_code == 200
        persisted = item_for(read(restarted, handover["id"]), source["incident"])
        assert persisted["snapshot_token"] == item["snapshot_token"]
        assert persisted["ack_applied_version"] == 5
        detail = restarted.get(f'/api/v1/incidents/{source["incident"]}').json()["data"]
        assert detail["owner_id"] == demo_ids["incoming_supervisor"]
        assert detail["actions"][0]["id"] == source["action"]
        assert detail["actions"][0]["assignee_id"] == demo_ids["maintainer"]
        assert detail["handover"]["id"] == handover["id"]
        assert detail["handover"]["item_id"] == item["id"]
        assert detail["handover"]["ack_status"] == "ACKNOWLEDGED"
        assert not detail["handover"]["is_stale"]
        assert detail["analysis"]["is_stale"] is True
    with session_factory() as tx:
        incident = tx.get(Incident, source["incident"])
        assert (incident.owner_id, incident.owner_shift_occurrence_id, incident.version) == (
            demo_ids["incoming_supervisor"], demo_ids["incoming_shift"], 5)
        assert input_state(tx, source["incident"]) == before
        assert tx.get(Incident, untouched["incident"]).version == 4
        assert count(tx, HandoverAck, HandoverAck.item_id == item["id"]) == 1
        events = list(tx.scalars(select(Event).where(Event.incident_id == source["incident"])))
        assert len(events) == 1 and events[0].actor_id == demo_ids["incoming_supervisor"]
        assert count(tx, CommandReceipt) == 3  # create, ACK, refresh under a new key


@pytest.mark.ac2
@pytest.mark.ac3
@pytest.mark.ac5
@pytest.mark.ac15
def test_all_wait_categories_exact_membership_and_no_cross_shift_or_site_leak(
        clients, session_factory, demo_ids):
    cases = seed_waits(session_factory)
    with session_factory.begin() as tx:
        other_shift = seed_incident(tx, owner=demo_ids["incoming_supervisor"], shift=demo_ids["incoming_shift"])
        other_site = seed_incident(tx, site=str(uuid4()))
        resolved = seed_incident(tx, status="RESOLVED", action_status="COMPLETED")
    handover = created(clients())
    assert {item["incident_id"] for item in handover["items"]} == {case["incident"] for case in cases.values()}
    assert not ({other_shift["incident"], other_site["incident"], resolved["incident"]}
                & {item["incident_id"] for item in handover["items"]})
    for label, source in cases.items():
        item = item_for(handover, source["incident"])
        snapshot = item["snapshot"]
        assert {q["id"] for q in snapshot["requests"]} == {source["open_request"], source["answered_request"]}
        assert {q["id"] for q in snapshot["open_requests"]} == {source["open_request"]}
        assert all(q["is_required"] for q in snapshot["requests"])
        with session_factory() as tx:
            before = input_state(tx, source["incident"])
        success = ack(clients("incoming_supervisor"), handover, item)
        assert success.status_code == 200, (label, success.text)
        with session_factory() as tx:
            assert input_state(tx, source["incident"]) == before
    refreshed = created(clients())
    assert {x["incident_id"] for x in refreshed["items"]} == {x["incident_id"] for x in handover["items"]}
    assert all(x["ack_status"] == "ACKNOWLEDGED" and not x["is_stale"] for x in refreshed["items"])
    review = item_for(refreshed, cases["review"]["incident"])
    assert review["snapshot"]["review_required"] is True
    assert review["snapshot"]["actions"][0]["status"] == "REJECTED"
    completed = item_for(refreshed, cases["verification"]["incident"])
    assert completed["snapshot"]["actions"][0]["status"] == "COMPLETED"
    assert completed["snapshot"]["actions"][0]["result_message_id"] == cases["verification"]["result"]


@pytest.mark.ac2
@pytest.mark.ac11
@pytest.mark.parametrize("case", ["reverse", "same", "nonadjacent", "missing_receiver_assignment", "missing_outgoing_assignment",
    "receiver_disabled", "receiver_wrong_role", "from_wrong_site", "to_wrong_site", "worker", "wrong_supervisor"])
def test_invalid_shift_pairs_and_callers_leave_no_handover(case, clients, session_factory, demo_ids):
    body, actor = pair(), "outgoing_supervisor"
    with session_factory.begin() as tx:
        if case == "reverse":
            body = {"from_shift_occurrence_id": demo_ids["incoming_shift"], "to_shift_occurrence_id": demo_ids["outgoing_shift"]}
            actor = "incoming_supervisor"
        elif case == "same":
            body["to_shift_occurrence_id"] = demo_ids["outgoing_shift"]
        elif case == "nonadjacent":
            tx.get(Shift, demo_ids["incoming_shift"]).starts_at += timedelta(hours=1)
        elif case == "missing_receiver_assignment":
            tx.execute(delete(ShiftAssignment).where(ShiftAssignment.shift_occurrence_id == demo_ids["incoming_shift"],
                ShiftAssignment.user_id == demo_ids["incoming_supervisor"]))
        elif case == "missing_outgoing_assignment":
            tx.execute(delete(ShiftAssignment).where(ShiftAssignment.shift_occurrence_id == demo_ids["outgoing_shift"],
                ShiftAssignment.user_id == demo_ids["outgoing_supervisor"]))
        elif case == "receiver_disabled":
            tx.get(User, demo_ids["incoming_supervisor"]).enabled = False
        elif case == "receiver_wrong_role":
            tx.get(User, demo_ids["incoming_supervisor"]).role = "worker"
        elif case == "from_wrong_site":
            tx.get(Shift, demo_ids["outgoing_shift"]).site_id = str(uuid4())
        elif case == "to_wrong_site":
            tx.get(Shift, demo_ids["incoming_shift"]).site_id = str(uuid4())
        elif case == "worker":
            actor = "reporter"
        elif case == "wrong_supervisor":
            actor = "incoming_supervisor"
    response = create(clients(actor), body)
    assert response.status_code in (403, 404, 422), response.text
    with session_factory() as tx:
        assert count(tx, Handover) == count(tx, HandoverItem) == count(tx, HandoverRevision) == 0
        assert count(tx, CommandReceipt) == 0


@pytest.mark.ac4
@pytest.mark.ac12
def test_create_replays_original_201_reuses_with_200_and_never_moves_cutoff(clients, session_factory):
    with session_factory.begin() as tx:
        seed_incident(tx)
    key = str(uuid4())
    first = create(clients(), key=key)
    replay = create(clients(), key=key)
    again = create(clients())
    assert [first.status_code, replay.status_code, again.status_code] == [201, 201, 200]
    assert replay.headers["Idempotent-Replayed"] == "true"
    assert first.json() == replay.json()
    assert "Idempotent-Replayed" not in again.headers
    a, b = first.json()["data"], again.json()["data"]
    assert a["id"] == b["id"] and a["cutoff_at"] == b["cutoff_at"]
    assert a["items"] == b["items"]
    with session_factory() as tx:
        assert count(tx, Handover) == count(tx, HandoverItem) == count(tx, HandoverRevision) == 1


@pytest.mark.ac5
@pytest.mark.ac6
@pytest.mark.ac9
@pytest.mark.ac15
@pytest.mark.ac16
def test_historical_snapshot_token_all_records_immutable_after_note_and_reack(clients, session_factory, demo_ids):
    with session_factory.begin() as tx:
        source = seed_incident(tx, status="PENDING_VERIFICATION", action_status="COMPLETED")
    outgoing, incoming = clients(), clients("incoming_supervisor")
    handover = created(outgoing)
    old = deepcopy(item_for(handover, source["incident"]))
    snapshot = old["snapshot"]
    assert {x["id"] for x in snapshot["messages"]} == {source["report"], source["reply"], source["result"]}
    assert {x["id"] for x in snapshot["evidence"]} == {source["evidence"]}
    assert snapshot["approvals"][0]["id"] == source["approval"]
    answered = next(q for q in snapshot["requests"] if q["id"] == source["answered_request"])
    assert answered["response_message_id"] == source["reply"] and answered["status"] == "ANSWERED"
    assert snapshot["facts"][0]["source_refs"] == [source["evidence"]]
    assert snapshot["facts"][0]["kind"] == "HUMAN_STATEMENT"
    assert snapshot["analysis"]["base_version"] == 4 and snapshot["analysis"]["is_stale"] is False
    assert ack(incoming, handover, old).status_code == 200
    added = add_note(clients("reporter"), source["incident"], 5)
    assert added.status_code == 202, added.text
    with session_factory() as tx:  # no read or refresh may be needed to publish revision
        assert tx.get(HandoverItem, old["id"]).latest_revision == 2
        revision = tx.get(HandoverRevision, (old["id"], 1))
        assert revision.snapshot_json == old["snapshot"] and revision.snapshot_token == old["snapshot_token"]
    current = item_for(read(incoming, handover["id"]), source["incident"])
    assert current["revision"] == 2 and current["snapshot_version"] == 6
    assert current["snapshot_token"] != old["snapshot_token"] and current["requires_ack"]
    assert current["snapshot"]["analysis"]["is_stale"] is True
    assert current["snapshot"]["facts"] == []  # old analysis is not current confirmed fact
    detail = incoming.get(f'/api/v1/incidents/{source["incident"]}')
    assert detail.status_code == 200
    summary = detail.json()["data"]["handover"]
    assert summary["id"] == handover["id"] and summary["item_id"] == old["id"]
    assert summary["revision"] == 2 and summary["snapshot_version"] == 6
    assert summary["previously_acknowledged"] is True and summary["ack_status"] == "PENDING"
    assert summary["is_stale"] is False  # The new snapshot is current; the prior ACK still needs renewal.
    error(ack(incoming, handover, old), 409, "HANDOVER_STALE")
    assert ack(incoming, handover, current).status_code == 200
    historical = read(outgoing, handover["id"], item_id=old["id"], revision=1)
    previous = item_for(historical, source["incident"])
    assert previous["snapshot"] == old["snapshot"] and previous["snapshot_token"] == old["snapshot_token"]
    assert previous["snapshot"]["owner_id"] == demo_ids["outgoing_supervisor"]
    assert previous["current_owner_id"] == demo_ids["incoming_supervisor"]
    assert previous["latest_revision"] == 2 and previous["is_stale"]
    assert not previous["can_ack"]
    with session_factory() as tx:
        assert tx.get(Incident, source["incident"]).version == 7
        acks = list(tx.scalars(select(HandoverAck).where(HandoverAck.item_id == old["id"]).order_by(HandoverAck.revision)))
        assert [record.ack_applied_version for record in acks] == [5, 7]
        assert acks[1].previous_owner_id == acks[1].new_owner_id == demo_ids["incoming_supervisor"]
        assert tx.get(Action, source["action"]).assignee_id == demo_ids["maintainer"]


@pytest.mark.ac6
@pytest.mark.ac18
def test_reads_and_analysis_only_update_have_no_business_or_revision_effect(clients, session_factory):
    with session_factory.begin() as tx:
        source = seed_incident(tx)
    handover = created(clients())
    item = item_for(handover, source["incident"])
    assert ack(clients("incoming_supervisor"), handover, item).status_code == 200
    with session_factory.begin() as tx:
        incident = tx.get(Incident, source["incident"])
        incident.analysis = {"base_version": 5, "facts": [], "reason": "updated analysis only"}
    for _ in range(2):
        current = item_for(read(clients(), handover["id"]), source["incident"])
        historical = read(clients(), handover["id"], item_id=item["id"], revision=1)
        assert current["revision"] == 1 and current["ack_status"] == "ACKNOWLEDGED" and not current["is_stale"]
        assert item_for(historical, source["incident"])["snapshot"] == item["snapshot"]
    refreshed = item_for(created(clients()), source["incident"])
    assert refreshed["revision"] == 1 and refreshed["ack_status"] == "ACKNOWLEDGED"
    assert refreshed["current_analysis_is_stale"] is False and not refreshed["requires_ack"]
    with session_factory() as tx:
        assert tx.get(Incident, source["incident"]).version == 5
        assert count(tx, HandoverAck) == count(tx, HandoverRevision) == count(tx, Event) == 1


@pytest.mark.ac3
@pytest.mark.ac10
@pytest.mark.ac16
def test_new_incident_pending_then_explicitly_included_keeps_cutoff_and_added_flag(clients, session_factory):
    with session_factory.begin() as tx:
        first = seed_incident(tx)
    outgoing, incoming = clients(), clients("incoming_supervisor")
    handover = created(outgoing)
    assert ack(incoming, handover, item_for(handover, first["incident"])).status_code == 200
    with session_factory.begin() as tx:
        extra = seed_incident(tx, created_at=utcnow())
    pending = read(incoming, handover["id"])
    assert {p["incident_id"] for p in pending["pending_additions"]} == {extra["incident"]}
    assert {p["incident_id"] for p in pending["items"]} == {first["incident"]}
    pending_item = pending["pending_additions"][0]
    assert pending_item["added_since_cutoff"] is True
    assert not ({"snapshot_token", "revision", "snapshot", "id"} & set(pending_item))
    refreshed = created(outgoing)
    assert refreshed["cutoff_at"] == handover["cutoff_at"]
    new_item = item_for(refreshed, extra["incident"])
    assert new_item["added_since_cutoff"] and new_item["ack_status"] != "ACKNOWLEDGED"
    assert ack(incoming, refreshed, new_item).status_code == 200
    again = created(outgoing)
    assert again["cutoff_at"] == handover["cutoff_at"]
    assert item_for(again, extra["incident"])["added_since_cutoff"]
    assert item_for(again, extra["incident"])["ack_status"] == "ACKNOWLEDGED"


@pytest.mark.ac9
@pytest.mark.ac13
@pytest.mark.parametrize("change", ["note", "correction", "reply", "new_question", "initial_transition", "action_confirmed", "verification_ready"])
def test_existing_unacked_input_updates_revision_in_same_transaction(change, clients, session_factory, app, demo_ids):
    with session_factory.begin() as tx:
        source = seed_incident(tx)
    handover = created(clients())
    old = item_for(handover, source["incident"])
    if change in {"note", "correction", "reply"}:
        extra = {"correction_of": source["report"]} if change == "correction" else (
            {"reply_to_request_id": source["open_request"]} if change == "reply" else {})
        response = add_note(clients("maintainer" if change == "reply" else "reporter"), source["incident"], 4, **extra)
        assert response.status_code == 202, response.text
    else:  # Synthetic other-feature input calls the real caller-owned F3 port.
        with session_factory.begin() as tx:
            incident = tx.scalar(select(Incident).where(Incident.id == source["incident"]).with_for_update())
            incident.status = {"new_question": "IN_PROGRESS", "initial_transition": "INVESTIGATING", "action_confirmed": "ACTION_REQUIRED",
                               "verification_ready": "PENDING_VERIFICATION"}[change]
            if change == "new_question":
                tx.add(Request(incident_id=incident.id, target_user_id=demo_ids["reporter"],
                    purpose_code="VERIFY_SCOPE", question="추가로 확인된 범위는?", is_required=True,
                    status="OPEN", evidence_refs=[source["evidence"]]))
            if change == "action_confirmed":
                tx.get(Action, source["action"]).status = "APPROVED"
            if change == "verification_ready":
                tx.get(Action, source["action"]).status = "COMPLETED"
            event = new_event(tx, incident, "synthetic_" + change, demo_ids["outgoing_supervisor"])
            bump_incident(tx, incident, event, app.state.ports)
    with session_factory() as tx:
        assert tx.get(HandoverItem, old["id"]).latest_revision == 2
        assert tx.get(HandoverRevision, (old["id"], 2)).snapshot_version == 5
        assert tx.get(HandoverRevision, (old["id"], 1)).snapshot_json == old["snapshot"]
        assert count(tx, HandoverAck) == 0
    error(ack(clients("incoming_supervisor"), handover, old), 409, "HANDOVER_STALE")
    with session_factory() as tx:
        assert tx.get(Incident, source["incident"]).owner_id == demo_ids["outgoing_supervisor"]
        assert count(tx, HandoverAck) == 0


@pytest.mark.ac11
@pytest.mark.parametrize("operation", ["create", "read", "historical", "ack"])
def test_session_required_and_unrelated_actor_scope_no_data_leak(operation, clients, session_factory):
    with session_factory.begin() as tx:
        source = seed_incident(tx)
    handover = created(clients())
    item = item_for(handover, source["incident"])
    def request(actor):
        if operation == "create":
            return create(actor)
        if operation == "ack":
            return ack(actor, handover, item)
        return actor.get(f'/api/v1/handovers/{handover["id"]}',
            params={"item_id": item["id"], "revision": 1} if operation == "historical" else {})
    error(request(clients(None)), 401)
    denied = request(clients("reporter"))
    assert denied.status_code in (403, 404), denied.text
    assert "current_version" not in denied.json()["error"] or denied.json()["error"]["current_version"] is None
    assert item["snapshot_token"] not in denied.text and source["report"] not in denied.text
    with session_factory() as tx:
        assert count(tx, HandoverAck) == 0
        assert tx.get(Incident, source["incident"]).version == 4


@pytest.mark.ac11
def test_forbidden_origins_and_forged_body_fields_have_no_effect(clients, session_factory):
    with session_factory.begin() as tx:
        source = seed_incident(tx)
    outgoing, incoming = clients(), clients("incoming_supervisor")
    error(outgoing.post("/api/v1/handovers", json=pair(), headers={"Origin": "https://attacker.invalid", "Idempotency-Key": str(uuid4())}), 403)
    for field in ("actor_id", "site_id", "role", "owner_id", "assignee_id", "receiver_id", "incident_ids"):
        response = create(outgoing, {**pair(), field: [source["incident"]] if field == "incident_ids" else str(uuid4())})
        error(response, 422, "VALIDATION_ERROR")
    handover = created(outgoing)
    item = handover["items"][0]
    url = f'/api/v1/handovers/{handover["id"]}/items/{item["id"]}/ack'
    for origin in (None, "https://attacker.invalid"):
        response = incoming.post(url, json=ack_body(item), headers={"Idempotency-Key": str(uuid4()), **({"Origin": origin} if origin else {})})
        error(response, 403)
    for field in ("actor_id", "site_id", "role", "owner_id", "assignee_id", "receiver_id"):
        error(ack(incoming, handover, item, body={**ack_body(item), field: str(uuid4())}), 422)
    with session_factory() as tx:
        assert count(tx, HandoverAck) == 0 and tx.get(Incident, source["incident"]).version == 4


@pytest.mark.ac11
def test_cross_site_session_and_item_hierarchy_and_detail_projection(clients, session_factory, demo_ids):
    with session_factory.begin() as tx:
        source = seed_incident(tx)
        target = seed_incident(tx, owner=demo_ids["incoming_supervisor"], shift=demo_ids["incoming_shift"])
        b = tx.get(Shift, demo_ids["incoming_shift"])
        third = Shift(id=new_id(), site_id=demo_ids["site"], label="C", starts_at=b.ends_at,
            ends_at=b.ends_at + timedelta(hours=4), supervisor_id=demo_ids["outgoing_supervisor"])
        tx.add(third)
        tx.flush()
        tx.add(ShiftAssignment(shift_occurrence_id=third.id, user_id=demo_ids["outgoing_supervisor"], duty="SUPERVISOR"))
        third_id = third.id
    handover = created(clients())
    other = created(clients("incoming_supervisor"), {"from_shift_occurrence_id": demo_ids["incoming_shift"], "to_shift_occurrence_id": third_id})
    wrong = item_for(other, target["incident"])
    error(ack(clients("incoming_supervisor"), handover, wrong), 404)
    error(clients().get(f'/api/v1/handovers/{handover["id"]}', params={"item_id": wrong["id"], "revision": 1}), 404)
    public = clients("reporter").get(f'/api/v1/incidents/{source["incident"]}')
    assert public.status_code == 200
    assert public.json()["data"]["handover"] is None
    assert "snapshot_token" not in public.text and wrong["id"] not in public.text
    original = item_for(handover, source["incident"])
    with session_factory.begin() as tx:
        tx.get(User, demo_ids["incoming_supervisor"]).site_id = str(uuid4())
    denied = clients("incoming_supervisor").get(f'/api/v1/handovers/{handover["id"]}')
    error(denied, 404)
    error(ack(clients("incoming_supervisor"), handover, original), 404)
    assert original["snapshot_token"] not in denied.text


@pytest.mark.ac9
@pytest.mark.ac11
@pytest.mark.parametrize("mutation", ["forged", "nonascii_token", "future_revision", "version_ahead", "version_behind"])
def test_invalid_current_snapshot_claim_cannot_transfer_responsibility(mutation, clients, session_factory, demo_ids):
    with session_factory.begin() as tx:
        source = seed_incident(tx)
    handover = created(clients())
    item = handover["items"][0]
    body = ack_body(item)
    if mutation == "forged":
        body["snapshot_token"] = "0" * 64
    elif mutation == "nonascii_token":
        body["snapshot_token"] = "위조" * 32
    elif mutation == "future_revision":
        body["revision"] += 1
    else:
        body["expected_version"] += 1 if mutation == "version_ahead" else -1
    response = ack(clients("incoming_supervisor"), handover, item, body=body)
    assert response.status_code in (403, 409, 422), response.text
    with session_factory() as tx:
        assert tx.get(Incident, source["incident"]).owner_id == demo_ids["outgoing_supervisor"]
        assert tx.get(Incident, source["incident"]).version == 4 and count(tx, HandoverAck) == 0


@pytest.mark.ac12
def test_keys_required_conflicting_payloads_distinct_key_repeat_and_actor_isolation(clients, session_factory):
    with session_factory.begin() as tx:
        seed_incident(tx)
    outgoing, incoming = clients(), clients("incoming_supervisor")
    error(outgoing.post("/api/v1/handovers", json=pair(), headers={"Origin": "http://testserver"}), 422)
    create_key = str(uuid4())
    handover = created(outgoing, key=create_key)
    error(create(outgoing, {**pair(), "to_shift_occurrence_id": str(uuid4())}, key=create_key), 409, "IDEMPOTENCY_CONFLICT")
    # Receipt of the outgoing actor cannot give the incoming actor create authority.
    denied = create(incoming, key=create_key)
    assert denied.status_code in (403, 404) and "Idempotent-Replayed" not in denied.headers
    item, key = handover["items"][0], str(uuid4())
    url = f'/api/v1/handovers/{handover["id"]}/items/{item["id"]}/ack'
    error(incoming.post(url, json=ack_body(item), headers={"Origin": "http://testserver"}), 422)
    first = ack(incoming, handover, item, key=key)
    replay = ack(incoming, handover, item, key=key)
    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json() and replay.headers["Idempotent-Replayed"] == "true"
    error(ack(incoming, handover, item, key=key, body={**ack_body(item), "revision": 2}), 409, "IDEMPOTENCY_CONFLICT")
    repeat = ack(incoming, handover, item)
    assert repeat.status_code == 200 and "Idempotent-Replayed" not in repeat.headers
    assert repeat.json()["data"] == first.json()["data"]
    wrong_actor = ack(outgoing, handover, item, key=key)
    assert wrong_actor.status_code in (403, 404) and "Idempotent-Replayed" not in wrong_actor.headers
    with session_factory() as tx:
        assert count(tx, HandoverAck) == count(tx, Event) == 1
        assert tx.get(Incident, item["incident_id"]).version == 5


@pytest.mark.ac14
@pytest.mark.ac16
def test_resolved_s02_handover_summary_preserves_history_and_ack_on_read(clients, session_factory, app, demo_ids):
    from app.features.intake.service import as_dict
    with session_factory.begin() as tx:
        source = seed_incident(tx)
    outgoing, incoming = clients(), clients("incoming_supervisor")
    handover = created(outgoing)
    item = handover["items"][0]
    assert ack(incoming, handover, item).status_code == 200
    before_resolution = incoming.get(f'/api/v1/incidents/{source["incident"]}')
    assert before_resolution.status_code == 200
    assert before_resolution.json()["data"]["handover"]["is_resolved"] is False
    assert before_resolution.json()["data"]["handover"]["ack_status"] == "ACKNOWLEDGED"

    # This establishes an F4 input state through the real shared transaction hook;
    # it does not implement an F4 endpoint or claim a real final-verification flow.
    with session_factory.begin() as tx:
        incident = tx.scalar(select(Incident).where(Incident.id == source["incident"]).with_for_update())
        incident.status, incident.resolved_at = "RESOLVED", utcnow()
        event = new_event(tx, incident, "synthetic_resolved", demo_ids["incoming_supervisor"])
        bump_incident(tx, incident, event, app.state.ports)

    def stored_state(tx):
        return (
            [as_dict(row) for row in tx.scalars(select(HandoverRevision)
                .where(HandoverRevision.item_id == item["id"]).order_by(HandoverRevision.revision))],
            [as_dict(row) for row in tx.scalars(select(HandoverAck)
                .where(HandoverAck.item_id == item["id"]).order_by(HandoverAck.revision))],
            tuple(count(tx, model) for model in (Event, CommandReceipt)),
        )
    with session_factory() as tx:
        records_before_read = stored_state(tx)
        assert len(records_before_read[0]) == 2 and len(records_before_read[1]) == 1
        assert records_before_read[0][0]["snapshot_json"] == item["snapshot"]
        assert records_before_read[0][0]["snapshot_token"] == item["snapshot_token"]
        assert records_before_read[1][0]["ack_applied_version"] == 5

    for participant in (outgoing, incoming):
        response = participant.get(f'/api/v1/incidents/{source["incident"]}')
        assert response.status_code == 200
        data = response.json()["data"]
        summary = data["handover"]
        assert data["status"] == "RESOLVED"
        assert summary["id"] == handover["id"] and summary["item_id"] == item["id"]
        assert summary["is_resolved"] is True
        assert summary["revision"] == 2 and summary["snapshot_version"] == 6
        assert summary["ack_status"] == "PENDING" and summary["ack_applied_version"] is None
        assert "snapshot" not in summary and "snapshot_token" not in summary
    with session_factory() as tx:
        incident = tx.get(Incident, source["incident"])
        assert incident.version == 6 and incident.owner_id == demo_ids["incoming_supervisor"]
        assert stored_state(tx) == records_before_read


@pytest.mark.ac3
@pytest.mark.ac11
@pytest.mark.ac12
@pytest.mark.ac14
def test_resolved_new_ack_retains_rejected_input_receipt_once_and_old_success_replays(clients, session_factory, app, demo_ids):
    with session_factory.begin() as tx:
        source = seed_incident(tx)
    handover = created(clients())
    item, key = handover["items"][0], str(uuid4())
    incoming = clients("incoming_supervisor")
    success = ack(incoming, handover, item, key=key)
    assert success.status_code == 200
    case_snapshot = {"immutable": "synthetic resolved case", "version": 6}
    with session_factory.begin() as tx:
        incident = tx.scalar(select(Incident).where(Incident.id == source["incident"]).with_for_update())
        incident.status, incident.resolved_at = "RESOLVED", utcnow()
        event = new_event(tx, incident, "synthetic_resolved", demo_ids["incoming_supervisor"])
        bump_incident(tx, incident, event, app.state.ports)
        tx.add(ResolutionCase(incident_id=incident.id, site_id=incident.site_id, equipment_id=incident.equipment_id,
            title="합성 해결 입력", resolved_version=6, snapshot_json=case_snapshot))
    late_key = str(uuid4())
    rejected = ack(incoming, handover, item, key=late_key)
    error(rejected, 409, "INCIDENT_RESOLVED")
    rejected_replay = ack(incoming, handover, item, key=late_key)
    assert rejected.json() == rejected_replay.json() and rejected_replay.headers["Idempotent-Replayed"] == "true"
    success_replay = ack(incoming, handover, item, key=key)
    assert success_replay.status_code == 200 and success_replay.json() == success.json()
    assert success_replay.headers["Idempotent-Replayed"] == "true"
    current = item_for(created(clients()), source["incident"])
    assert current["is_resolved"] and not current["can_ack"]
    public = clients("reporter").get(f'/api/v1/incidents/{source["incident"]}')
    assert public.status_code == 200
    assert item["snapshot_token"] not in public.text and "snapshot_token" not in public.text
    public_rejection = next(event for event in public.json()["data"]["recent_events"] if event["type"] == "rejected_input")
    assert "input" not in public_rejection["payload"]
    with session_factory() as tx:
        incident = tx.get(Incident, source["incident"])
        assert incident.version == 6 and incident.owner_id == demo_ids["incoming_supervisor"]
        rejected_events = list(tx.scalars(select(Event).where(Event.type == "rejected_input")))
        assert len(rejected_events) == 1 and rejected_events[0].payload["input"] == ack_body(item)
        assert count(tx, HandoverAck) == 1
        assert tx.scalar(select(ResolutionCase).where(ResolutionCase.incident_id == source["incident"])).snapshot_json == case_snapshot


@pytest.mark.ac11
@pytest.mark.ac12
def test_completed_receipt_cannot_cross_the_actors_changed_site(clients, session_factory, demo_ids):
    with session_factory.begin() as tx:
        seed_incident(tx)
    handover = created(clients())
    item, incoming, key = handover["items"][0], clients("incoming_supervisor"), str(uuid4())
    assert ack(incoming, handover, item, key=key).status_code == 200
    with session_factory.begin() as tx:
        tx.get(User, demo_ids["incoming_supervisor"]).site_id = str(uuid4())
    denied = ack(incoming, handover, item, key=key)
    error(denied, 404)
    assert "Idempotent-Replayed" not in denied.headers
    assert item["snapshot_token"] not in denied.text
    assert "data" not in denied.json()
    with session_factory() as tx:
        assert count(tx, CommandReceipt, CommandReceipt.idempotency_key == key) == 1
        assert count(tx, HandoverAck) == 1


@pytest.mark.ac15
def test_ack_does_not_delegate_question_answer_permission_or_clear_review(clients, session_factory):
    with session_factory.begin() as tx:
        source = seed_incident(tx, status="ACTION_REQUIRED", action_status="REJECTED", review=True)
    handover = created(clients())
    assert ack(clients("incoming_supervisor"), handover, handover["items"][0]).status_code == 200
    response = add_note(clients("incoming_supervisor"), source["incident"], 5,
                        reply_to_request_id=source["open_request"], text="수신자의 대리 답변")
    error(response, 403)
    with session_factory() as tx:
        q = tx.get(Request, source["open_request"])
        assert q.status == "OPEN" and q.is_required and q.response_message_id is None
        assert tx.get(Incident, source["incident"]).review_required
        assert tx.get(Action, source["action"]).status == "REJECTED"


@pytest.mark.ac11
@pytest.mark.ac18
def test_agent_failure_no_model_dependency_and_no_diagnostic_leak_or_agent_success(clients, session_factory, demo_ids):
    with session_factory.begin() as tx:
        source = seed_incident(tx)
        incident = tx.get(Incident, source["incident"])
        event = new_event(tx, incident, "synthetic_model_failure")
        job = Job(id=new_id(), incident_id=incident.id, trigger_event_id=event.id,
            dedupe_key=str(uuid4()), status="FAILED", attempt=1,
            last_error={"code": "MODEL_UNAVAILABLE", "retryable": True})
        tx.add(job)
        tx.flush()
        run = AgentRun(id=new_id(), job_id=job.id, attempt=1, trigger_event_id=event.id,
            input_version=4, status="FAILED", steps_json=[{"private": "PRIVATE-F3-RUN"}],
            metadata_json={"private": "PRIVATE-F3-RUN"}, error_json={"code": "MODEL_UNAVAILABLE"})
        tx.add(run)
        job_id, run_id = job.id, run.id
    handover = created(clients())
    encoded = json.dumps(handover)
    assert all(secret not in encoded for secret in ("PRIVATE-F3-PROMPT", "PRIVATE-F3-ENV", "PRIVATE-F3-RUN"))
    assert ack(clients("incoming_supervisor"), handover, handover["items"][0]).status_code == 200
    old_owner = clients().get(f'/api/v1/jobs/{job_id}')
    assert old_owner.status_code == 200 and "run_summary" not in old_owner.json()["data"]
    error(clients().post(f'/api/v1/jobs/{job_id}/retry', json={}, headers=headers()), 403)
    with session_factory() as tx:
        assert tx.get(AgentRun, run_id).status == "FAILED"
        assert tx.get(Job, job_id).status == "FAILED"
        assert count(tx, Action, Action.incident_id == source["incident"]) == 1
        assert tx.get(Incident, source["incident"]).version == 5


@pytest.mark.ac17
def test_query_failure_is_503_not_successful_empty_list_and_server_returns_latest_conflict(clients, session_factory, monkeypatch):
    from app.features.handovers import service
    with session_factory.begin() as tx:
        source = seed_incident(tx)
    handover = created(clients())
    saved = deepcopy(handover["items"][0])
    original = service.read_handover
    def unavailable(*args, **kwargs):
        raise OperationalError("SELECT", {}, RuntimeError("synthetic database outage"))
    monkeypatch.setattr(service, "read_handover", unavailable)
    response = clients().get(f'/api/v1/handovers/{handover["id"]}')
    error(response, 503, "SERVICE_UNAVAILABLE")
    assert "data" not in response.json()
    monkeypatch.setattr(service, "read_handover", original)
    assert add_note(clients("reporter"), source["incident"], 4).status_code == 202
    error(ack(clients("incoming_supervisor"), handover, saved), 409, "HANDOVER_STALE")
    assert saved == handover["items"][0]
    assert item_for(read(clients(), handover["id"]), source["incident"])["revision"] == 2
