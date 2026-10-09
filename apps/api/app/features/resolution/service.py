"""Human verification on the shared F1 transaction and F2 readiness policy."""
import base64
import binascii
from datetime import datetime
import json
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy import or_, select

from app.core.auth import require_owner
from app.core.errors import DomainError
from app.core.models import (Action, Approval, Evidence, Incident, Message, Request,
    ResolutionCase, User, Verification, new_id, utcnow)
from app.core.transactions import bump_incident, lock_incident, new_event, require_version
from app.features.intake.service import as_dict, read_incident


def readiness(tx, incident, ports):
    result = ports.evaluate_resolution_readiness(tx, incident=incident)
    if (not isinstance(result, dict) or type(result.get("ready")) is not bool
            or not isinstance(result.get("unmet_requirements"), list)
            or any(not isinstance(x, str) for x in result["unmet_requirements"])
            or (result["ready"] and result["unmet_requirements"])):
        raise DomainError(503, "SERVICE_UNAVAILABLE", "검증 준비 조건을 확인하지 못했습니다.")
    return result


def person_data(tx, user_id):
    user = tx.get(User, user_id)
    return {"id": user_id, "display_name": user.display_name if user else None}


def verification_data(tx, row):
    return {**as_dict(row), "reviewer": person_data(tx, row.actor_id)}


def case_data(row):
    # Only stored data: a case never follows changing Incident/User records.
    return {**as_dict(row), "source_type": "case",
            "reviewer": row.snapshot_json.get("reviewer"),
            "resolved_at": row.snapshot_json.get("incident", {}).get("resolved_at")}


def detail(tx, principal, incident, ports):
    latest = tx.scalar(select(Verification).where(Verification.incident_id == incident.id)
        .order_by(Verification.applied_version.desc(), Verification.id.desc()).limit(1))
    case = tx.scalar(select(ResolutionCase).where(ResolutionCase.incident_id == incident.id,
        ResolutionCase.site_id == principal.site_id).order_by(ResolutionCase.resolved_version.desc()).limit(1))
    if incident.status == "RESOLVED":
        prepared = {"ready": False, "unmet_requirements": ["INCIDENT_RESOLVED"]}
    elif ports.readiness_evaluator is None:
        prepared = {"ready": False, "unmet_requirements": ["READINESS_UNAVAILABLE"]}
    else:
        prepared = readiness(tx, incident, ports)
    owner = principal.role == "supervisor" and incident.owner_id == principal.user_id
    pending = incident.status == "PENDING_VERIFICATION"
    return {**prepared, "checked_version": incident.version,
            "can_resolve": owner and pending and prepared["ready"] and not incident.review_required,
            "can_return": owner and pending,
            "latest_verification": verification_data(tx, latest) if latest else None,
            "case": case_data(case) if case else None}


def verify(tx, principal, incident_id, body, ports):
    incident = lock_incident(tx, incident_id, principal)
    require_owner(principal, incident)
    # Receipt replay is handled before this function, including after owner changes.
    if incident.status == "RESOLVED":
        new_event(tx, incident, "rejected_input", principal.user_id,
                  payload={"command": "verification", "input": body.model_dump(mode="json")})
        return 409, DomainError(409, "INCIDENT_RESOLVED", "이미 해결된 사건입니다.").body()
    require_version(incident, body.expected_version)
    if incident.status != "PENDING_VERIFICATION":
        raise DomainError(409, "INVALID_STATE", "검증 대기 상태에서만 최종 검토할 수 있습니다.")
    # All writers serialize on Incident first, then mutable business children.
    for model in (Action, Request):
        list(tx.scalars(select(model).where(model.incident_id == incident.id)
                        .order_by(model.id).with_for_update()))
    if body.decision == "RESOLVE":
        prepared = readiness(tx, incident, ports)
        if incident.review_required or not prepared["ready"]:
            missing = list(dict.fromkeys(prepared["unmet_requirements"] +
                          (["REVIEW_REQUIRED"] if incident.review_required else [])))
            raise DomainError(409, "READINESS_NOT_MET", "해결에 필요한 조건을 확인해 주세요.",
                              details={"unmet_requirements": missing})
    # Share F2's persisted-evidence policy; don't trust browser-provided source data.
    if body.evidence_refs:
        from app.features.actions.orm import load_context
        from app.features.actions.integrity import valid_evidence
        from pydantic import ValidationError
        try:
            context = load_context(tx, incident)
            valid = all(valid_evidence(context, ref) is not None for ref in body.evidence_refs)
        except (ValidationError, ValueError):
            valid = False
        if not valid:
            raise DomainError(422, "VALIDATION_ERROR", "같은 사건의 유효한 근거를 선택해 주세요.")
    now = utcnow()
    checked = incident.version
    verification = Verification(id=new_id(), incident_id=incident.id, decision=body.decision,
        notes=body.notes, evidence_refs=list(dict.fromkeys(str(x) for x in body.evidence_refs)),
        checked_version=checked, applied_version=checked + 1, actor_id=principal.user_id, created_at=now)
    tx.add(verification)
    case_id = new_id() if body.decision == "RESOLVE" else None
    if case_id:
        incident.status = "RESOLVED"
        incident.resolved_at = now
    else:
        incident.status = "INVESTIGATING"
        incident.review_required = True
        incident.review_reason = body.notes
    event = new_event(tx, incident, "incident_resolved" if case_id else "verification_returned",
        principal.user_id, payload={"decision": body.decision, "notes": body.notes},
        related_ids={"verification_id": verification.id, **({"case_id": case_id} if case_id else {})})
    # Also refresh F3 in this transaction; hook failure rolls back every F4 write.
    bump_incident(tx, incident, event, ports)
    if case_id:
        actions = list(tx.scalars(select(Action).where(Action.incident_id == incident.id).order_by(Action.id)))
        refs = list(dict.fromkeys([a.completion_evidence_id for a in actions if a.completion_evidence_id]
                                 + verification.evidence_refs))
        snapshot = {"schema_version": 1, "incident": as_dict(incident),
            "reviewer": person_data(tx, principal.user_id), "verification": as_dict(verification),
            "actions": [as_dict(x) for x in actions],
            "approvals": [as_dict(x) for x in tx.scalars(select(Approval)
                .where(Approval.action_id.in_([a.id for a in actions])).order_by(Approval.id))],
            "messages": [as_dict(x) for x in tx.scalars(select(Message)
                .where(Message.incident_id == incident.id).order_by(Message.received_at, Message.id))],
            "requests": [as_dict(x) for x in tx.scalars(select(Request)
                .where(Request.incident_id == incident.id).order_by(Request.id))],
            "evidence": [as_dict(x) for x in tx.scalars(select(Evidence)
                .where(Evidence.incident_id == incident.id, Evidence.site_id == principal.site_id).order_by(Evidence.id))]}
        # AI analysis is mutable advisory/diagnostic material, not the human's decision.
        snapshot["incident"].pop("analysis", None)
        tx.add(ResolutionCase(id=case_id, incident_id=incident.id, site_id=incident.site_id,
            equipment_id=incident.equipment_id, title=incident.title, resolved_version=incident.version,
            verification_id=verification.id, snapshot_json=snapshot, evidence_refs=refs, created_at=now))
        tx.flush()
    return 200, {"data": {"incident_id": incident.id, "incident_status": incident.status,
        "incident_version": incident.version, "verification_id": verification.id,
        "case_id": case_id, "resolved_at": incident.resolved_at.isoformat() if case_id else None}}


def list_cases(tx, principal, *, incident_id=None, cursor=None, limit=20):
    if incident_id:
        read_incident(tx, principal, incident_id)
    stmt = select(ResolutionCase).where(ResolutionCase.site_id == principal.site_id)
    if incident_id:
        stmt = stmt.where(ResolutionCase.incident_id == incident_id)
    if cursor:
        try:
            value = json.loads(base64.urlsafe_b64decode(cursor.encode()))
            if value["site_id"] != principal.site_id or value["incident_id"] != incident_id:
                raise ValueError("cursor scope changed")
            created_at = datetime.fromisoformat(value["created_at"])
            row_id = str(UUID(value["id"]))
            if created_at.tzinfo is None:
                raise ValueError("timezone required")
        except (ValueError, TypeError, KeyError, binascii.Error, UnicodeError, AttributeError):
            raise DomainError(422, "VALIDATION_ERROR", "유효하지 않은 목록 위치입니다.")
        stmt = stmt.where(or_(ResolutionCase.created_at < created_at,
            (ResolutionCase.created_at == created_at) & (ResolutionCase.id < row_id)))
    rows = list(tx.scalars(stmt.order_by(ResolutionCase.created_at.desc(), ResolutionCase.id.desc()).limit(limit + 1)))
    next_cursor = None
    if len(rows) > limit:
        row = rows[limit - 1]
        next_cursor = base64.urlsafe_b64encode(json.dumps({"site_id": principal.site_id,
            "incident_id": incident_id, "created_at": row.created_at.isoformat(), "id": row.id}).encode()).decode()
    return jsonable_encoder({"items": [case_data(row) for row in rows[:limit]], "next_cursor": next_cursor})
