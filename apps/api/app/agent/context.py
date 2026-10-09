from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from app.core.models import (Action, Approval, Equipment, Event, Evidence, Incident, Message,
                             Request, ShiftAssignment, User)
from .runner import ContextLimit, DEFAULT_MAX_INPUT_BYTES, initial_context_fits


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


def build_context(tx, identity: RunIdentity, incident: Incident, *, trigger_event_id=None,
                  max_input_bytes=DEFAULT_MAX_INPUT_BYTES, max_output_tokens=2000) -> RunContext:
    """Select complete records; authoritative messages/evidence are never shortened.

    Required current business state and its source closure take priority. Remaining
    messages, then non-message evidence, are considered newest first with ID ties.
    We do not reuse earlier model prose as a substitute for omitted originals.
    """
    messages = list(tx.scalars(select(Message).where(Message.incident_id == incident.id)
                              .order_by(Message.received_at, Message.id)))
    message_rows = {}
    for message in messages:
        ev = issue_evidence(tx, incident, source_type="message", source_id=message.id,
                            excerpt=message.text, equipment_id=incident.equipment_id,
                            source_location=f"messages/{message.id}", observed_at=message.observed_at,
                            applicability={"author_id": message.author_id, "received_at": iso(message.received_at)})
        message_rows[message.id] = {"id": message.id, "kind": message.kind, "text": message.text,
                             "author_id": message.author_id, "observed_at": iso(message.observed_at),
                             "received_at": iso(message.received_at), "source_ref": ev.id,
                             "reply_to_request_id": message.reply_to_request_id,
                             "correction_of": message.correction_of}
    requests = list(tx.scalars(select(Request).where(Request.incident_id == incident.id).order_by(Request.id)))
    actions = list(tx.scalars(select(Action).where(Action.incident_id == incident.id).order_by(Action.id)))
    approvals = list(tx.scalars(select(Approval).where(Approval.action_id.in_([a.id for a in actions]))
                               .order_by(Approval.created_at, Approval.id))) if actions else []
    evidence = list(tx.scalars(select(Evidence).where(Evidence.incident_id == incident.id,
                                                       Evidence.site_id == incident.site_id).order_by(Evidence.id)))
    targets = allowed_targets(tx, incident)
    evidence_by_id = {e.id: e for e in evidence}
    selected_messages = {messages[0].id, messages[-1].id} if messages else set()
    trigger = tx.get(Event, trigger_event_id) if trigger_event_id else None
    if trigger is not None and trigger.incident_id == incident.id and trigger.site_id == incident.site_id:
        trigger_message = trigger.related_ids.get("message_id")
        if trigger_message in message_rows:
            selected_messages.add(trigger_message)
    # Phase 1 requests are required and the generation-one Action remains relevant
    # even when completed/rejected. Keep the answers/results and approval details.
    required_requests = [r for r in requests if r.is_required or r.status == "OPEN"]
    required_request_ids = {r.id for r in required_requests}
    selected_messages.update(m.id for m in messages if m.reply_to_request_id in required_request_ids)
    selected_messages.update(r.response_message_id for r in required_requests if r.response_message_id in message_rows)
    selected_messages.update(a.result_message_id for a in actions if a.result_message_id in message_rows)
    selected_evidence = {ref for r in required_requests for ref in r.evidence_refs}
    selected_evidence.update(ref for a in actions for ref in a.evidence_refs)
    selected_evidence.update(a.completion_evidence_id for a in actions if a.completion_evidence_id)
    selected_evidence.intersection_update(evidence_by_id)
    selected_messages.update(evidence_by_id[ref].source_id for ref in selected_evidence
                             if evidence_by_id[ref].source_type in {"message", "completion_report"}
                             and evidence_by_id[ref].source_id in message_rows)
    def correction_closure(ids):
        # A correction cannot lose its original, or an included original its correction.
        ids = set(ids)
        while True:
            linked = {m.id for m in messages if m.correction_of in ids}
            linked.update(m.correction_of for m in messages if m.id in ids
                          and m.correction_of in message_rows)
            if linked.issubset(ids):
                return ids
            ids.update(linked)

    selected_messages = correction_closure(selected_messages)
    selected_evidence.update(message_rows[mid]["source_ref"] for mid in selected_messages)
    base = {
        "incident": {"id": incident.id, "equipment_id": incident.equipment_id,
                     "version": incident.version, "status": incident.status,
                     "owner_id": incident.owner_id, "owner_shift_occurrence_id": incident.owner_shift_occurrence_id,
                     "review_required": incident.review_required,
                     "review_reason": incident.review_reason},
        "trigger_event_id": trigger_event_id, "input_version": identity.input_version,
        "requests": [{"id": r.id, "target_user_id": r.target_user_id, "purpose_code": r.purpose_code,
                      "question": r.question, "is_required": r.is_required, "status": r.status,
                      "response_message_id": r.response_message_id, "evidence_refs": r.evidence_refs}
                     for r in required_requests],
        "actions": [{"id": a.id, "scope": a.scope, "completion_criteria": a.completion_criteria,
                     "status": a.status, "assignee_id": a.assignee_id, "action_generation": a.action_generation,
                     "revision": a.revision, "version": a.version,
                     "evidence_refs": a.evidence_refs, "result_message_id": a.result_message_id,
                     "completion_evidence_id": a.completion_evidence_id} for a in actions],
        "approvals": [{"action_id": a.action_id, "decision": a.decision,
                       "action_revision": a.action_revision, "payload_hash": a.payload_hash,
                       "reason": a.reason, "actor_id": a.actor_id, "created_at": iso(a.created_at),
                       "approved_payload_snapshot": a.approved_payload_snapshot} for a in approvals],
        "allowed_question_target_ids": sorted(targets),
    }

    def render():
        rows = []
        for ev in evidence:
            if ev.id not in selected_evidence:
                continue
            row = evidence_data(ev)
            original = message_rows.get(ev.source_id) if ev.source_type in {"message", "completion_report"} else None
            if original and original["id"] in selected_messages and ev.excerpt == original["text"]:
                del row["excerpt"]
                row["excerpt_from"] = f"messages/{original['id']}/text"
            rows.append(row)
        return {**base, "messages": [message_rows[m.id] for m in messages if m.id in selected_messages],
                "evidence": rows, "context_selection": {
                    "strategy": "required_then_recent_whole_records",
                    "omitted_messages": len(messages) - len(selected_messages),
                    "omitted_evidence": len(evidence) - len(selected_evidence),
                    "omitted_requests": len(requests) - len(required_requests),
                    "max_input_bytes": max_input_bytes}}

    def fits(payload, *, reserve_tools=False):
        return initial_context_fits(payload, max_input_bytes=max_input_bytes,
                                    max_output_tokens=max_output_tokens, reserve_tools=reserve_tools)

    payload = render()
    if not fits(payload):
        raise ContextLimit("Required incident records exceed the model input byte budget")
    for message in reversed(messages):
        if message.id in selected_messages:
            continue
        added_messages = correction_closure({message.id}) - selected_messages
        added_evidence = {message_rows[mid]["source_ref"] for mid in added_messages} - selected_evidence
        selected_messages.update(added_messages)
        selected_evidence.update(added_evidence)
        candidate = render()
        if fits(candidate, reserve_tools=True):
            payload = candidate
        else:
            selected_messages.difference_update(added_messages)
            selected_evidence.difference_update(added_evidence)
    for ev in sorted(evidence, key=lambda e: (e.captured_at, e.id), reverse=True):
        if ev.id in selected_evidence or ev.source_type == "message":
            continue
        selected_evidence.add(ev.id)
        candidate = render()
        if fits(candidate, reserve_tools=True):
            payload = candidate
        else:
            selected_evidence.remove(ev.id)
    return RunContext(identity, payload, selected_evidence, targets)
