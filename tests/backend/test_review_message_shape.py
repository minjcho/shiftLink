"""Reject ambiguous message intent before recording any domain command."""

import pytest
from sqlalchemy import select

from app.core.models import CommandReceipt, Event, Incident, Job, Message, Request
from test_intake import add_question, post_report


def command_state(factory):
    with factory() as tx:
        return {
            model.__tablename__: {
                row.id: {column.name: getattr(row, column.name) for column in model.__table__.columns}
                for row in tx.scalars(select(model))
            }
            for model in (Incident, Message, Request, Event, Job, CommandReceipt)
        }


@pytest.mark.parametrize("kind", ["REPLY", "CORRECTION", "NOTE"])
def test_dual_message_links_reject_without_writes_and_allow_valid_retry(
    client, login, demo_ids, auth_headers, session_factory, kind
):
    login()
    report = post_report(client, demo_ids, auth_headers).json()["data"]
    incident_id = report["incident_id"]
    question_id = add_question(session_factory, incident_id, demo_ids["reporter"])
    path = f"/api/v1/incidents/{incident_id}/messages"
    headers = {**auth_headers, "Idempotency-Key": "message-shape"}
    body = {
        "text": "  확인한 원문  ",
        "expected_version": 1,
        "reply_to_request_id": question_id,
        "correction_of": report["message_id"],
    }
    before = command_state(session_factory)

    rejected = client.post(path, json=body, headers=headers)

    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["error"]["code"] == "VALIDATION_ERROR"
    # Include full rows so status/version/timestamps and existing Job changes
    # cannot hide behind unchanged row counts.
    assert command_state(session_factory) == before

    # Validation must not consume the idempotency key. Each supported message
    # kind still works with the same key after fixing the ambiguous body.
    body["reply_to_request_id"] = question_id if kind == "REPLY" else None
    body["correction_of"] = report["message_id"] if kind == "CORRECTION" else None
    accepted = client.post(path, json=body, headers=headers)

    assert accepted.status_code == 202, accepted.text
    data = accepted.json()["data"]
    assert data["incident_version"] == 2
    assert data["request_id"] == (question_id if kind == "REPLY" else None)
    assert data["request_version"] == (2 if kind == "REPLY" else None)
    with session_factory() as tx:
        message = tx.get(Message, data["message_id"])
        assert message.kind == kind
        assert message.text == body["text"]
        assert message.reply_to_request_id == body["reply_to_request_id"]
        assert message.correction_of == body["correction_of"]
        question = tx.get(Request, question_id)
        assert question.status == ("ANSWERED" if kind == "REPLY" else "OPEN")
        assert question.version == (2 if kind == "REPLY" else 1)
        assert question.response_message_id == (message.id if kind == "REPLY" else None)
        assert (question.answered_at is not None) == (kind == "REPLY")
        original = tx.get(Message, report["message_id"])
        assert original.text == before["messages"][original.id]["text"]
    after = command_state(session_factory)
    for table in ("messages", "events", "jobs", "command_receipts"):
        assert len(after[table]) == len(before[table]) + 1
