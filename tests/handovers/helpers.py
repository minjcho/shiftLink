"""Independent synthetic input builders and HTTP assertions for F3 contracts."""
from datetime import timedelta
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import func, select

from app.core.models import (Action, Approval, Event, Evidence, Incident, Message,
                            Request, new_id, utcnow)
from app.core.seed import SEED_IDS


def headers(key=None):
    return {"Origin": "http://testserver", "Idempotency-Key": key or str(uuid4())}


def pair(ids=SEED_IDS):
    return {"from_shift_occurrence_id": ids["outgoing_shift"],
            "to_shift_occurrence_id": ids["incoming_shift"]}


def create(client, body=None, key=None):
    return client.post("/api/v1/handovers", json=body or pair(), headers=headers(key))


def created(client, body=None, key=None):
    response = create(client, body=body, key=key)
    assert response.status_code in (200, 201), response.text
    return response.json()["data"]


def read(client, handover_id, **query):
    response = client.get(f"/api/v1/handovers/{handover_id}", params=query)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def ack_body(item):
    return {"revision": item["revision"], "snapshot_token": item["snapshot_token"],
            "expected_version": item["snapshot_version"]}


def ack(client, handover, item, *, key=None, body=None):
    return client.post(f'/api/v1/handovers/{handover["id"]}/items/{item["id"]}/ack',
                       json=body or ack_body(item), headers=headers(key))


def item_for(handover, incident_id):
    return next(item for item in handover["items"] if item["incident_id"] == incident_id)


def error(response, status, code=None):
    assert response.status_code == status, response.text
    if code:
        assert response.json()["error"]["code"] == code, response.text
    return response.json()["error"]


def count(tx, model, *where):
    return tx.scalar(select(func.count()).select_from(model).where(*where))


def seed_incident(tx, *, status="IN_PROGRESS", action_status="IN_PROGRESS", review=False,
                  owner=None, shift=None, site=None, equipment=None, rich=True, created_at=None):
    ids = SEED_IDS
    incident_id = new_id()
    incident = Incident(id=incident_id, display_id=f"SYNTH-F3-{incident_id[:12]}",
        title="합성 F3 기록 확인", site_id=site or ids["site"],
        equipment_id=equipment or ids["equipment"], reporter_id=ids["reporter"],
        origin_shift_occurrence_id=shift or ids["outgoing_shift"],
        owner_shift_occurrence_id=shift or ids["outgoing_shift"],
        owner_id=owner or ids["outgoing_supervisor"], status=status, version=4,
        review_required=review, review_reason="추가 범위를 책임자가 재검토" if review else None,
        created_at=created_at or utcnow() - timedelta(minutes=20))
    tx.add(incident)
    tx.flush()
    report = Message(id=new_id(), site_id=incident.site_id, incident_id=incident.id,
        author_id=ids["reporter"], kind="REPORT", text="작업자가 흔들림을 관찰했다고 보고함")
    tx.add(report)
    tx.flush()
    evidence = Evidence(id=new_id(), site_id=incident.site_id, incident_id=incident.id,
        source_type="MESSAGE", source_id=report.id, excerpt=report.text,
        content_hash=sha256(report.text.encode()).hexdigest(), source_location="합성 원문")
    tx.add(evidence)
    tx.flush()
    result = {"incident": incident.id, "report": report.id, "evidence": evidence.id,
              "action": None, "open_request": None, "answered_request": None,
              "approval": None, "result": None, "reply": None}
    if rich:
        opened = Request(id=new_id(), incident_id=incident.id, target_user_id=ids["maintainer"],
            purpose_code="VERIFY_SCOPE", question="확인한 범위는?", is_required=True,
            status="OPEN", evidence_refs=[evidence.id])
        answered = Request(id=new_id(), incident_id=incident.id, target_user_id=ids["reporter"],
            purpose_code="VERIFY_RESULT", question="관찰 시각은?", is_required=True,
            status="ANSWERED", evidence_refs=[evidence.id])
        tx.add_all([opened, answered])
        tx.flush()
        reply = Message(id=new_id(), site_id=incident.site_id, incident_id=incident.id,
            author_id=ids["reporter"], kind="REPLY", text="직전 교대에 관찰했습니다.",
            reply_to_request_id=answered.id)
        tx.add(reply)
        tx.flush()
        answered.response_message_id = reply.id
        answered.answered_at = utcnow()
        result.update(open_request=opened.id, answered_request=answered.id, reply=reply.id)
    if action_status:
        action = Action(id=new_id(), incident_id=incident.id, assignee_id=ids["maintainer"],
            title="기록 범위 확인", scope="기록과 보고의 차이 확인", completion_criteria=["차이를 기록"],
            evidence_refs=[evidence.id], status=action_status, version=2)
        tx.add(action)
        tx.flush()
        approval = Approval(id=new_id(), action_id=action.id, action_revision=1,
            decision="REJECT" if review else "APPROVE", reason="대상 기록 범위 재검토" if review else "합성 기록 확인 승인",
            payload_hash="fixture-approved-payload", approved_payload_snapshot={"scope": action.scope,
                "assignee_id": action.assignee_id}, actor_id=ids["outgoing_supervisor"])
        tx.add(approval)
        result.update(action=action.id, approval=approval.id)
        if action_status == "COMPLETED":
            message = Message(id=new_id(), site_id=incident.site_id, incident_id=incident.id,
                author_id=ids["maintainer"], kind="ACTION_RESULT", action_id=action.id,
                text="합성 기록 범위와 차이 확인 결과")
            tx.add(message)
            tx.flush()
            action.result_message_id = message.id
            action.completion_evidence_id = evidence.id
            action.completed_at = utcnow()
            result["result"] = message.id
    incident.analysis = {"base_version": 4, "applied_version": 4, "run_id": str(uuid4()),
        "facts": [{"text": report.text, "kind": "HUMAN_STATEMENT", "source_refs": [evidence.id]}],
        "hypotheses": ["추가 확인이 필요한 가설"],
        "missing_information": ["정확한 관찰 범위"], "reason": "추가 확인 필요",
        "internal_prompt": "PRIVATE-F3-PROMPT", "environment": {"token": "PRIVATE-F3-ENV"}}
    tx.flush()
    return result


def seed_waits(session_factory):
    with session_factory.begin() as tx:
        return {
            "open": seed_incident(tx, status="OPEN", action_status=None),
            "question": seed_incident(tx, status="INVESTIGATING", action_status=None),
            "approval": seed_incident(tx, status="ACTION_REQUIRED", action_status="PROPOSED"),
            "work": seed_incident(tx),
            "verification": seed_incident(tx, status="PENDING_VERIFICATION", action_status="COMPLETED"),
            "review": seed_incident(tx, status="ACTION_REQUIRED", action_status="REJECTED", review=True),
        }


def add_note(client, incident_id, version, **extra):
    return client.post(f"/api/v1/incidents/{incident_id}/messages", headers=headers(),
        json={"text": "새 합성 원문", "expected_version": version, "observed_at": None,
              "reply_to_request_id": None, "correction_of": None, **extra})


def input_state(tx, incident_id):
    """Records that ACK must preserve, serialized without ORM identity coupling."""
    from app.features.intake.service import as_dict
    incident = tx.get(Incident, incident_id)
    actions = list(tx.scalars(select(Action).where(Action.incident_id == incident_id)))
    return {
        "incident_status": incident.status, "review_required": incident.review_required,
        "review_reason": incident.review_reason,
        "messages": sorted((as_dict(x) for x in tx.scalars(select(Message).where(Message.incident_id == incident_id))), key=lambda x: x["id"]),
        "requests": sorted((as_dict(x) for x in tx.scalars(select(Request).where(Request.incident_id == incident_id))), key=lambda x: x["id"]),
        "actions": sorted((as_dict(x) for x in actions), key=lambda x: x["id"]),
        "approvals": sorted((as_dict(x) for x in tx.scalars(select(Approval).where(Approval.action_id.in_([x.id for x in actions])))), key=lambda x: x["id"]),
        "evidence": sorted((as_dict(x) for x in tx.scalars(select(Evidence).where(Evidence.incident_id == incident_id))), key=lambda x: x["id"]),
    }
