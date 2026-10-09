from __future__ import annotations

import base64
from datetime import datetime
import json

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, or_, select

from app.core.auth import current_shift, require_owner
from app.core.errors import DomainError, not_found
from app.core.models import (Action, AgentRun, Approval, Equipment, Evidence, Event, Handover,
    HandoverAck, HandoverItem, HandoverRevision, Incident, Job, Message, Request, ShiftAssignment,
    User, new_id, utcnow)
from app.core.transactions import bump_incident, enqueue_job, lock_incident, new_event, require_version


def as_dict(row):
    return jsonable_encoder({column.name: getattr(row, column.name) for column in row.__table__.columns})


def event_data(row):
    # Cross-feature event payloads are not an alternate full handover/read-diagnostic API.
    result = as_dict(row)
    allowed_ids = {"message_id", "request_id", "action_id", "job_id", "run_id", "verification_id", "case_id"}
    result["related_ids"] = {key: value for key, value in row.related_ids.items() if key in allowed_ids}
    if row.type not in {"incident_reported", "message_added", "request_answered", "rejected_input"}:
        result["payload"] = {}
    return result


def create_report(tx, principal, body, ports):
    equipment = tx.scalar(select(Equipment).where(Equipment.id == str(body.equipment_id), Equipment.site_id == principal.site_id))
    if equipment is None:
        raise not_found()
    shift = current_shift(tx, principal)
    supervisor = tx.get(User, shift.supervisor_id) if shift else None
    if (shift is None or supervisor is None or not supervisor.enabled or supervisor.role != "supervisor"
            or supervisor.site_id != principal.site_id):
        raise DomainError(422, "SHIFT_ASSIGNMENT_MISSING", "현재 교대 책임자 배정이 필요합니다.")
    mapped = tx.get(ShiftAssignment, (shift.id, supervisor.id))
    if mapped is None or mapped.duty != "SUPERVISOR":
        raise DomainError(422, "SHIFT_ASSIGNMENT_MISSING", "현재 교대 책임자 배정이 필요합니다.")
    incident_id = new_id()
    incident = Incident(id=incident_id, display_id=f"INC-{incident_id[:12].upper()}", title=body.text[:100],
        site_id=principal.site_id, equipment_id=equipment.id, reporter_id=principal.user_id,
        origin_shift_occurrence_id=shift.id, owner_shift_occurrence_id=shift.id, owner_id=supervisor.id,
        status="OPEN", version=1, action_generation=1, review_required=False)
    tx.add(incident)
    tx.flush()
    message = Message(id=new_id(), site_id=principal.site_id, incident_id=incident.id,
        author_id=principal.user_id, kind="REPORT", text=body.text, observed_at=body.observed_at)
    tx.add(message)
    tx.flush()
    event = new_event(tx, incident, "incident_reported", principal.user_id, related_ids={"message_id": message.id})
    job = enqueue_job(tx, incident, event)
    return 202, {"data": {"incident_id": incident.id, "display_id": incident.display_id, "status": incident.status,
        "version": incident.version, "message_id": message.id, "job_id": job.id, "received_at": message.received_at.isoformat()}}


def add_message(tx, principal, incident_id, body, ports):
    incident = lock_incident(tx, incident_id, principal)
    request = None
    if body.reply_to_request_id:
        request = tx.scalar(select(Request).where(Request.id == str(body.reply_to_request_id),
            Request.incident_id == incident.id).with_for_update())
        if request is None:
            raise not_found()
        if request.target_user_id != principal.user_id:
            raise DomainError(403, "FORBIDDEN", "지정된 대상자만 질문에 답변할 수 있습니다.")
    if body.correction_of:
        original = tx.scalar(select(Message).where(Message.id == str(body.correction_of), Message.incident_id == incident.id))
        if original is None:
            raise not_found()
    # Authorized late input is retained even though the prior UI version is now stale.
    if incident.status == "RESOLVED":
        new_event(tx, incident, "rejected_input", principal.user_id,
                  payload={"command": "add_message", "input": body.model_dump(mode="json")})
        error = DomainError(409, "INCIDENT_RESOLVED", "해결된 사건입니다. 새로운 제보를 등록해 주세요.")
        return 409, error.body()
    require_version(incident, body.expected_version)
    if request and request.status != "OPEN":
        raise DomainError(409, "REQUEST_CLOSED", "이미 답변된 질문입니다.")
    message = Message(id=new_id(), site_id=principal.site_id, incident_id=incident.id,
        author_id=principal.user_id, kind="REPLY" if request else ("CORRECTION" if body.correction_of else "NOTE"),
        text=body.text, observed_at=body.observed_at, reply_to_request_id=request.id if request else None,
        correction_of=str(body.correction_of) if body.correction_of else None)
    tx.add(message)
    tx.flush()
    if request:
        request.status = "ANSWERED"
        request.response_message_id = message.id
        request.version += 1
        request.answered_at = utcnow()
    if incident.status == "PENDING_VERIFICATION":
        incident.status = "INVESTIGATING"
    event = new_event(tx, incident, "request_answered" if request else "message_added", principal.user_id,
        related_ids={"message_id": message.id, "request_id": request.id if request else None})
    bump_incident(tx, incident, event, ports)
    job = enqueue_job(tx, incident, event)
    return 202, {"data": {"message_id": message.id, "request_id": request.id if request else None,
        "request_version": request.version if request else None, "incident_id": incident.id,
        "incident_status": incident.status, "incident_version": incident.version, "job_id": job.id}}


def read_incident(tx, principal, incident_id):
    incident = tx.scalar(select(Incident).where(Incident.id == incident_id, Incident.site_id == principal.site_id))
    if incident is None:
        raise not_found()
    return incident


def retryable_job(job, incident, settings):
    return bool(job.status == "FAILED" and job.attempt < settings.job_max_attempts
        and incident.status != "RESOLVED" and not incident.review_required
        and (job.last_error or {}).get("retryable", False))


def job_data(tx, principal, job, incident, settings):
    run = tx.scalar(select(AgentRun).where(AgentRun.job_id == job.id).order_by(AgentRun.attempt.desc()).limit(1))
    result = {"id": job.id, "incident_id": job.incident_id, "status": job.status, "attempt": job.attempt,
        "latest_run_id": run.id if run else None, "latest_run_status": run.status if run else None,
        "mode": run.mode if run else settings.agent_mode, "started_at": run.started_at if run else None,
        "finished_at": run.finished_at if run else None, "error_code": (job.last_error or {}).get("code"),
        "retryable": retryable_job(job, incident, settings)}
    if run and principal.role == "supervisor" and principal.user_id == incident.owner_id:
        result["run_summary"] = {"run_id": run.id, "input_version": run.input_version, "applied_version": run.applied_version,
            "model_id": run.model_id, "prompt_version": run.prompt_version, "tool_schema_version": run.tool_schema_version,
            "steps": run.steps_json, "usage": run.usage_json, "metadata": run.metadata_json,
            "decision": run.decision_json, "error": run.error_json}
    return jsonable_encoder(result)


def retry_job(tx, principal, job_id, settings):
    reference = tx.get(Job, job_id)
    if reference is None:
        raise not_found()
    incident = lock_incident(tx, reference.incident_id, principal)
    require_owner(principal, incident)
    job = tx.scalar(select(Job).where(Job.id == job_id).with_for_update())
    if job.status == "SUCCEEDED":
        return 200, {"data": job_data(tx, principal, job, incident, settings)}
    if job.status in {"RUNNING", "QUEUED"}:
        raise DomainError(409, "INVALID_STATE", "이미 조사가 대기 또는 실행 중입니다.")
    if job.status == "SUPERSEDED":
        raise DomainError(409, "INVALID_STATE", "최신 조사 Job을 확인해 주세요.")
    if not retryable_job(job, incident, settings):
        raise DomainError(409, "REVIEW_REQUIRED" if incident.review_required else "INVALID_STATE", "현재 조사는 재시도할 수 없습니다.")
    job.status = "QUEUED"
    job.available_at = tx.scalar(select(func.clock_timestamp()))
    job.updated_at = utcnow()
    job.lease_token = None
    job.lease_expires_at = None
    tx.flush()
    return 202, {"data": job_data(tx, principal, job, incident, settings)}


def incident_summary(tx, incident):
    equipment = tx.get(Equipment, incident.equipment_id)
    owner = tx.get(User, incident.owner_id)
    open_questions = list(tx.scalars(select(Request).where(Request.incident_id == incident.id, Request.status == "OPEN")))
    actions = list(tx.scalars(select(Action).where(Action.incident_id == incident.id)))
    return {"id": incident.id, "display_id": incident.display_id, "title": incident.title,
        "site_id": incident.site_id, "equipment_id": incident.equipment_id,
        "equipment": {"id": equipment.id, "code": equipment.code, "label": equipment.label},
        "status": incident.status, "version": incident.version, "owner_id": incident.owner_id,
        "owner": {"id": owner.id, "display_name": owner.display_name}, "owner_shift_occurrence_id": incident.owner_shift_occurrence_id,
        "review_required": incident.review_required, "review_reason": incident.review_reason,
        "waiting_for_input": any(q.is_required for q in open_questions), "open_request_count": len(open_questions),
        "unfinished_action_count": sum(a.status in {"PROPOSED", "APPROVED", "IN_PROGRESS"} for a in actions),
        "updated_at": incident.updated_at, "created_at": incident.created_at, "resolved_at": incident.resolved_at}


def list_incidents(tx, principal, *, status=None, equipment_id=None, scope="all", cursor=None, limit=20):
    stmt = select(Incident).where(Incident.site_id == principal.site_id)
    stmt = stmt.where(Incident.status == status) if status else stmt.where(Incident.status != "RESOLVED")
    if equipment_id:
        stmt = stmt.where(Incident.equipment_id == equipment_id)
    if scope == "mine":
        stmt = stmt.where(or_(Incident.owner_id == principal.user_id,
            Incident.id.in_(select(Action.incident_id).where(Action.assignee_id == principal.user_id)),
            Incident.id.in_(select(Request.incident_id).where(Request.target_user_id == principal.user_id, Request.status == "OPEN"))))
    if cursor:
        try:
            value = json.loads(base64.urlsafe_b64decode(cursor.encode()))
            last_time = datetime.fromisoformat(value["updated_at"])
            last_id = str(value["id"])
        except (ValueError, TypeError, KeyError):
            raise DomainError(422, "VALIDATION_ERROR", "유효하지 않은 목록 위치입니다.")
        stmt = stmt.where(or_(Incident.updated_at < last_time,
                            (Incident.updated_at == last_time) & (Incident.id < last_id)))
    rows = list(tx.scalars(stmt.order_by(Incident.updated_at.desc(), Incident.id.desc()).limit(limit + 1)))
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = base64.urlsafe_b64encode(json.dumps({"updated_at": last.updated_at.isoformat(), "id": last.id}).encode()).decode()
    return jsonable_encoder({"items": [incident_summary(tx, row) for row in rows[:limit]], "next_cursor": next_cursor})


def detail(tx, principal, incident_id, settings):
    incident = read_incident(tx, principal, incident_id)
    result = incident_summary(tx, incident)
    result["messages"] = [as_dict(x) for x in tx.scalars(select(Message).where(Message.incident_id == incident.id).order_by(Message.received_at, Message.id))]
    requests = list(tx.scalars(select(Request).where(Request.incident_id == incident.id).order_by(Request.created_at, Request.id)))
    result["requests"] = [as_dict(x) for x in requests]
    actions = list(tx.scalars(select(Action).where(Action.incident_id == incident.id).order_by(Action.created_at)))
    result["actions"] = [as_dict(x) for x in actions]
    result["approvals"] = [as_dict(x) for x in tx.scalars(select(Approval).where(Approval.action_id.in_([a.id for a in actions])))]
    result["evidence"] = [as_dict(x) for x in tx.scalars(select(Evidence).where(Evidence.incident_id == incident.id, Evidence.site_id == principal.site_id))]
    result["recent_events"] = [event_data(x) for x in tx.scalars(select(Event).where(Event.incident_id == incident.id).order_by(Event.occurred_at.desc(), Event.id.desc()).limit(50))]
    result["analysis"] = dict(incident.analysis, is_stale=incident.analysis.get("base_version") != incident.version) if incident.analysis else None
    job = tx.scalar(select(Job).where(Job.incident_id == incident.id).order_by(Job.created_at.desc(), Job.id.desc()).limit(1))
    result["latest_job"] = job_data(tx, principal, job, incident, settings) if job else None
    result["handover"] = None
    # No snapshot/token is embedded in public Incident read. Participants get a link and freshness summary.
    latest_readable = tx.execute(select(HandoverItem, Handover).join(Handover, Handover.id == HandoverItem.handover_id)
        .where(HandoverItem.incident_id == incident.id, Handover.site_id == principal.site_id,
               or_(Handover.created_by == principal.user_id, Handover.receiver_id == principal.user_id))
        .order_by(Handover.created_at.desc(), Handover.id.desc()).limit(1)).first()
    if latest_readable:
        item, handover = latest_readable
        revision = tx.get(HandoverRevision, (item.id, item.latest_revision))
        ack = tx.scalar(select(HandoverAck).where(HandoverAck.item_id == item.id, HandoverAck.revision == item.latest_revision))
        result["handover"] = {"id": handover.id, "item_id": item.id, "revision": item.latest_revision,
            "ack_status": "ACKNOWLEDGED" if ack else "PENDING", "snapshot_version": revision.snapshot_version if revision else None,
            "ack_applied_version": ack.ack_applied_version if ack else None,
            "is_stale": bool(revision and incident.version != (ack.ack_applied_version if ack else revision.snapshot_version)),
            "cutoff_at": handover.cutoff_at, "added_since_cutoff": incident.created_at > handover.cutoff_at}
    commands = []
    if incident.status != "RESOLVED":
        commands.append("add_message")
        if any(q.status == "OPEN" and q.target_user_id == principal.user_id for q in requests):
            commands.append("reply_request")
    if job and principal.role == "supervisor" and incident.owner_id == principal.user_id and retryable_job(job, incident, settings):
        commands.append("retry_job")
    result["allowed_commands"] = commands
    return jsonable_encoder(result)
