from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from app.core.models import (Action, Approval, Equipment, Evidence, Incident, Message,
                             Request, ShiftAssignment, User)


@dataclass(frozen=True)
class RunIdentity:
    job_id: str
    run_id: str
    incident_id: str
    site_id: str
    attempt: int
    lease_token: str
    input_version: int | None = None


@dataclass
class RunContext:
    identity: RunIdentity
    payload: dict
    source_ids: set[str]
    target_user_ids: set[str]


def iso(value: datetime | None):
    return value.isoformat() if value is not None else None


def allowed_targets(tx, incident: Incident) -> set[str]:
    equipment = tx.get(Equipment, incident.equipment_id)
    return set(tx.scalars(select(User.id).join(ShiftAssignment, ShiftAssignment.user_id == User.id).where(
        User.id == equipment.default_maintainer_id, User.site_id == incident.site_id, User.enabled.is_(True),
        ShiftAssignment.shift_occurrence_id == incident.owner_shift_occurrence_id,
        ShiftAssignment.duty == "MAINTENANCE",
    )))


def issue_evidence(tx, incident: Incident, *, source_type: str, source_id: str,
                   excerpt: str, equipment_id: str | None, source_version: str = "1",
                   source_location: str = "", observed_at=None,
                   applicability: dict | None = None, document_approval=None) -> Evidence:
    digest = hashlib.sha256(excerpt.encode()).hexdigest()
    evidence = tx.scalar(select(Evidence).where(
        Evidence.incident_id == incident.id, Evidence.site_id == incident.site_id,
        Evidence.source_type == source_type, Evidence.source_id == source_id,
        Evidence.source_version == source_version, Evidence.content_hash == digest,
        Evidence.source_location == source_location,
    ))
    if evidence is None:
        evidence = Evidence(site_id=incident.site_id, incident_id=incident.id, source_type=source_type,
                            source_id=source_id, source_version=source_version, excerpt=excerpt,
                            equipment_id=equipment_id, source_location=source_location,
                            observed_at=observed_at, content_hash=digest,
                            applicability=applicability or {}, document_approval=document_approval)
        tx.add(evidence)
        tx.flush()
    return evidence


def evidence_data(evidence: Evidence) -> dict:
    return {"id": evidence.id, "source_type": evidence.source_type, "source_id": evidence.source_id,
            "source_version": evidence.source_version, "equipment_id": evidence.equipment_id,
            "applicability": evidence.applicability, "document_approval": evidence.document_approval,
            "excerpt": evidence.excerpt, "content_hash": evidence.content_hash,
            "source_location": evidence.source_location, "observed_at": iso(evidence.observed_at),
            "captured_at": iso(evidence.captured_at)}


def build_context(tx, identity: RunIdentity, incident: Incident) -> RunContext:
    messages = list(tx.scalars(select(Message).where(Message.incident_id == incident.id)
                              .order_by(Message.received_at, Message.id)))
    message_rows = []
    for message in messages:
        ev = issue_evidence(tx, incident, source_type="message", source_id=message.id,
                            excerpt=message.text, equipment_id=incident.equipment_id,
                            source_location=f"messages/{message.id}", observed_at=message.observed_at,
                            applicability={"author_id": message.author_id, "received_at": iso(message.received_at)})
        message_rows.append({"id": message.id, "kind": message.kind, "text": message.text,
                             "author_id": message.author_id, "observed_at": iso(message.observed_at),
                             "received_at": iso(message.received_at), "source_ref": ev.id,
                             "reply_to_request_id": message.reply_to_request_id,
                             "correction_of": message.correction_of})
    requests = list(tx.scalars(select(Request).where(Request.incident_id == incident.id).order_by(Request.id)))
    actions = list(tx.scalars(select(Action).where(Action.incident_id == incident.id).order_by(Action.id)))
    approvals = list(tx.scalars(select(Approval).where(Approval.action_id.in_([a.id for a in actions])))) if actions else []
    evidence = list(tx.scalars(select(Evidence).where(Evidence.incident_id == incident.id,
                                                       Evidence.site_id == incident.site_id).order_by(Evidence.id)))
    targets = allowed_targets(tx, incident)
    payload = {
        "incident": {"id": incident.id, "equipment_id": incident.equipment_id,
                     "version": incident.version, "status": incident.status,
                     "owner_id": incident.owner_id, "review_required": incident.review_required,
                     "review_reason": incident.review_reason},
        "trigger_event_id": None, "input_version": identity.input_version,
        "messages": message_rows,
        "requests": [{"id": r.id, "target_user_id": r.target_user_id, "purpose_code": r.purpose_code,
                      "question": r.question, "is_required": r.is_required, "status": r.status,
                      "response_message_id": r.response_message_id, "evidence_refs": r.evidence_refs} for r in requests],
        "actions": [{"id": a.id, "scope": a.scope, "completion_criteria": a.completion_criteria,
                     "status": a.status, "assignee_id": a.assignee_id, "action_generation": a.action_generation,
                     "evidence_refs": a.evidence_refs, "result_message_id": a.result_message_id} for a in actions],
        "approvals": [{"action_id": a.action_id, "decision": a.decision,
                       "action_revision": a.action_revision, "payload_hash": a.payload_hash} for a in approvals],
        "allowed_question_target_ids": sorted(targets),
        "evidence": [evidence_data(e) for e in evidence],
    }
    return RunContext(identity, payload, {e.id for e in evidence}, targets)
