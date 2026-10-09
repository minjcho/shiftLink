from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import hmac
import json

from fastapi.encoders import jsonable_encoder
from sqlalchemy import or_, select, text

from app.core.errors import DomainError, not_found
from app.core.models import (Action, Approval, Equipment, Evidence, Handover, HandoverAck,
    HandoverItem, HandoverRevision, Incident, Message, Request, Shift, ShiftAssignment,
    User, new_id, utcnow)
from app.core.transactions import new_event


def as_dict(row):
    return jsonable_encoder({column.name: getattr(row, column.name) for column in row.__table__.columns})


def user_data(tx, user_id):
    user = tx.get(User, user_id) if user_id else None
    return {"id": user.id, "display_name": user.display_name} if user else None


def _assignment(tx, shift):
    user = tx.get(User, shift.supervisor_id)
    assignment = tx.get(ShiftAssignment, (shift.id, shift.supervisor_id))
    if (user is None or not user.enabled or user.site_id != shift.site_id
            or user.role != "supervisor" or assignment is None or assignment.duty != "SUPERVISOR"):
        raise DomainError(422, "SHIFT_ASSIGNMENT_MISSING", "교대 책임자 배정을 확인해 주세요.")
    return user


def _pair(tx, principal, body):
    shifts = list(tx.scalars(select(Shift).where(Shift.site_id == principal.site_id)
        .order_by(Shift.starts_at, Shift.id)))
    outgoing = next((x for x in shifts if x.id == str(body.from_shift_occurrence_id)), None)
    incoming = next((x for x in shifts if x.id == str(body.to_shift_occurrence_id)), None)
    if outgoing is None or incoming is None:
        raise not_found()
    if principal.role != "supervisor" or principal.user_id != outgoing.supervisor_id:
        raise DomainError(403, "FORBIDDEN", "출발 교대의 지정 책임자만 인계를 만들 수 있습니다.")
    index = shifts.index(outgoing)
    if (outgoing.id == incoming.id or index + 1 >= len(shifts) or shifts[index + 1].id != incoming.id
            or outgoing.ends_at != incoming.starts_at or outgoing.starts_at >= incoming.starts_at
            or incoming.ends_at <= incoming.starts_at):
        raise DomainError(422, "SHIFT_SCOPE_INVALID", "시간상 인접한 허용 교대 쌍을 선택해 주세요.")
    _assignment(tx, outgoing)
    receiver = _assignment(tx, incoming)
    return outgoing, incoming, receiver


def _read_handover(tx, principal, handover_id):
    row = tx.scalar(select(Handover).where(Handover.id == handover_id, Handover.site_id == principal.site_id))
    if row is None:
        raise not_found()
    if principal.role != "supervisor" or principal.user_id not in {row.created_by, row.receiver_id}:
        # The object identifier is not an authority to inspect a handover.
        raise not_found()
    return row


def _source_scope(handover):
    return (Incident.owner_shift_occurrence_id == handover.from_shift_occurrence_id) & (Incident.owner_id == handover.created_by)


def _lock_content(tx, incident_ids):
    """Call only after all relevant Incident rows have been locked in ID order."""
    if not incident_ids:
        return
    for model in (Action, Request):
        list(tx.scalars(select(model).where(model.incident_id.in_(incident_ids))
            .order_by(model.id).with_for_update().execution_options(populate_existing=True)))


def _safe_analysis(incident):
    source = incident.analysis
    if not isinstance(source, dict):
        return None
    # Never copy run diagnostics, metadata, tool arguments or arbitrary nested keys.
    result = {key: source[key] for key in ("run_id", "base_version", "decision", "reason")
              if key in source and isinstance(source[key], (str, int, type(None)))}
    for key in ("hypotheses", "missing_information", "source_refs"):
        result[key] = [x for x in source.get(key, []) if isinstance(x, str)] if isinstance(source.get(key), list) else []
    result["facts"] = []
    for fact in source.get("facts", []) if isinstance(source.get("facts"), list) else []:
        if (isinstance(fact, dict) and isinstance(fact.get("text"), str)
                and fact.get("kind") in {"HUMAN_STATEMENT", "RECORD", "SYSTEM_STATE"}):
            result["facts"].append({"text": fact["text"], "kind": fact["kind"],
                "source_refs": [x for x in fact.get("source_refs", []) if isinstance(x, str)]
                    if isinstance(fact.get("source_refs"), list) else []})
    result["is_stale"] = source.get("base_version") != incident.version
    return result


def snapshot(tx, incident):
    """Build a JSON value, with no live ORM references or owner-only run details."""
    equipment = tx.get(Equipment, incident.equipment_id)
    actions = list(tx.scalars(select(Action).where(Action.incident_id == incident.id).order_by(Action.id)))
    requests = [as_dict(x) for x in tx.scalars(select(Request).where(Request.incident_id == incident.id).order_by(Request.id))]
    evidence = [as_dict(x) for x in tx.scalars(select(Evidence).where(Evidence.incident_id == incident.id,
        Evidence.site_id == incident.site_id).order_by(Evidence.id))]
    analysis = _safe_analysis(incident)
    assignee_id = actions[0].assignee_id if actions else None
    value = {"incident_id": incident.id, "display_id": incident.display_id, "title": incident.title,
        "site_id": incident.site_id, "equipment_id": incident.equipment_id,
        "equipment": {"id": equipment.id, "code": equipment.code, "label": equipment.label} if equipment else None,
        "status": incident.status, "version": incident.version, "owner_id": incident.owner_id,
        "owner": user_data(tx, incident.owner_id), "owner_shift_occurrence_id": incident.owner_shift_occurrence_id,
        "assignee_id": assignee_id, "assignee": user_data(tx, assignee_id),
        "review_required": incident.review_required, "review_reason": incident.review_reason,
        "created_at": incident.created_at, "resolved_at": incident.resolved_at,
        "messages": [as_dict(x) for x in tx.scalars(select(Message).where(Message.incident_id == incident.id,
            Message.site_id == incident.site_id).order_by(Message.received_at, Message.id))],
        "requests": requests, "open_requests": [x for x in requests if x["status"] == "OPEN"],
        "actions": [as_dict(x) for x in actions],
        "unfinished_actions": [as_dict(x) for x in actions if x.status in {"PROPOSED", "APPROVED", "IN_PROGRESS"}],
        "approvals": [as_dict(x) for x in tx.scalars(select(Approval).where(Approval.action_id.in_([x.id for x in actions]))
            .order_by(Approval.id))], "evidence": evidence, "analysis": analysis,
        "facts": analysis["facts"] if analysis and not analysis["is_stale"] else [],
        "waiting_for_input": any(x["is_required"] for x in requests if x["status"] == "OPEN")}
    return jsonable_encoder(value)


def _latest_ack(tx, item):
    return tx.scalar(select(HandoverAck).where(HandoverAck.item_id == item.id,
        HandoverAck.revision == item.latest_revision))


def _business_content(value):
    result = deepcopy(value)
    # Analysis-only updates do not constitute new business information or new ACK duties.
    for key in ("analysis", "facts", "version"):
        result.pop(key, None)
    return result


def _ensure_revision(tx, item, incident):
    current = snapshot(tx, incident)
    previous = tx.get(HandoverRevision, (item.id, item.latest_revision))
    if previous is not None:
        ack = _latest_ack(tx, item)
        expected = ack.ack_applied_version if ack else previous.snapshot_version
        comparable = _business_content(current)
        if (ack is not None and incident.version == ack.ack_applied_version
                and incident.owner_id == ack.new_owner_id):
            # Keep the actual immutable snapshot owner; ACK has its own current-owner projection.
            for key in ("owner_id", "owner", "owner_shift_occurrence_id"):
                comparable[key] = previous.snapshot_json.get(key)
        if incident.version == expected and comparable == _business_content(previous.snapshot_json):
            return previous
        item.latest_revision += 1
    content_hash = sha256(json.dumps(current, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    token = sha256(f"{item.id}:{item.latest_revision}:{incident.version}:{content_hash}".encode()).hexdigest()
    revision = HandoverRevision(item_id=item.id, revision=item.latest_revision,
        snapshot_version=incident.version, snapshot_json=current, snapshot_token=token)
    tx.add(revision)
    tx.flush()
    return revision


def refresh_handover_items(tx, *, incident, event):
    """Participates in F1/F2/F4's locked transaction; never commits or bumps version."""
    _lock_content(tx, [incident.id])
    rows = list(tx.scalars(select(HandoverItem).join(Handover, Handover.id == HandoverItem.handover_id)
        .where(HandoverItem.incident_id == incident.id, Handover.site_id == incident.site_id)
        .order_by(HandoverItem.id).with_for_update(of=HandoverItem).execution_options(populate_existing=True)))
    for item in rows:
        _ensure_revision(tx, item, incident)


def create_or_refresh(tx, principal, body):
    outgoing, incoming, receiver = _pair(tx, principal, body)
    # Only creation takes this pair mutex. A business change never takes it while
    # holding Incident, so it cannot invert the shared row-lock order.
    key = int.from_bytes(sha256(f"handover:{principal.site_id}:{outgoing.id}:{incoming.id}".encode()).digest()[:8], "big", signed=True)
    tx.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
    handover = tx.scalar(select(Handover).where(Handover.site_id == principal.site_id,
        Handover.from_shift_occurrence_id == outgoing.id, Handover.to_shift_occurrence_id == incoming.id))
    created = handover is None
    if created:
        handover = Handover(id=new_id(), site_id=principal.site_id, from_shift_occurrence_id=outgoing.id,
            to_shift_occurrence_id=incoming.id, receiver_id=receiver.id, created_by=principal.user_id, cutoff_at=utcnow())
        tx.add(handover)
        tx.flush()
    elif handover.receiver_id != receiver.id or handover.created_by != principal.user_id:
        raise DomainError(409, "INVALID_STATE", "기존 인계의 책임자 배정이 변경되었습니다.")
    existing_ids = select(HandoverItem.incident_id).where(HandoverItem.handover_id == handover.id)
    incidents = list(tx.scalars(select(Incident).where(Incident.site_id == principal.site_id,
        or_((Incident.status != "RESOLVED") & _source_scope(handover), Incident.id.in_(existing_ids)))
        .order_by(Incident.id).with_for_update().execution_options(populate_existing=True)))
    _lock_content(tx, [x.id for x in incidents])
    items = list(tx.scalars(select(HandoverItem).where(HandoverItem.handover_id == handover.id)
        .order_by(HandoverItem.id).with_for_update().execution_options(populate_existing=True)))
    by_incident = {x.incident_id: x for x in items}
    for incident in incidents:
        item = by_incident.get(incident.id)
        if incident.status == "RESOLVED":
            # Resolution should already have refreshed via the common business hook.
            # The historical row remains available even for an imported resolved fixture.
            continue
        if item is None:
            # Recheck scope after waiting on a concurrently transferred Incident row.
            if incident.owner_shift_occurrence_id != outgoing.id or incident.owner_id != outgoing.supervisor_id:
                continue
            item = HandoverItem(id=new_id(), handover_id=handover.id, incident_id=incident.id, latest_revision=1)
            tx.add(item)
            tx.flush()
        _ensure_revision(tx, item, incident)
    return (201 if created else 200), {"data": read_handover(tx, principal, handover.id)}


def _item_data(tx, principal, handover, item, revision, incident):
    ack = tx.scalar(select(HandoverAck).where(HandoverAck.item_id == item.id, HandoverAck.revision == revision.revision))
    previous_ack = tx.scalar(select(HandoverAck.id).where(HandoverAck.item_id == item.id).limit(1)) is not None
    expected = ack.ack_applied_version if ack else revision.snapshot_version
    stale = revision.revision != item.latest_revision or incident.version != expected
    resolved = incident.status == "RESOLVED"
    action = tx.scalar(select(Action).where(Action.incident_id == incident.id).order_by(Action.id).limit(1))
    owner_allowed = ((incident.owner_id == handover.created_by and incident.owner_shift_occurrence_id == handover.from_shift_occurrence_id)
        or (incident.owner_id == handover.receiver_id and incident.owner_shift_occurrence_id == handover.to_shift_occurrence_id))
    return jsonable_encoder({"id": item.id, "incident_id": incident.id, "revision": revision.revision,
        "latest_revision": item.latest_revision, "snapshot_version": revision.snapshot_version,
        "snapshot_token": revision.snapshot_token, "snapshot": revision.snapshot_json,
        "ack_status": "ACKNOWLEDGED" if ack else "PENDING", "ack_applied_version": ack.ack_applied_version if ack else None,
        "acknowledged_by": ack.actor_id if ack else None, "acknowledged_at": ack.acknowledged_at if ack else None,
        "is_stale": stale, "is_resolved": resolved, "requires_ack": not resolved and not ack,
        "previously_acknowledged": previous_ack, "added_since_cutoff": incident.created_at > handover.cutoff_at,
        "current_owner_id": incident.owner_id, "current_owner": user_data(tx, incident.owner_id),
        "current_owner_shift_occurrence_id": incident.owner_shift_occurrence_id,
        "current_incident_version": incident.version, "current_incident_status": incident.status,
        "current_analysis_base_version": incident.analysis.get("base_version") if isinstance(incident.analysis, dict) else None,
        "current_analysis_is_stale": bool(isinstance(incident.analysis, dict)
            and incident.analysis.get("base_version") != incident.version),
        "current_assignee_id": action.assignee_id if action else None,
        "current_assignee": user_data(tx, action.assignee_id) if action else None,
        "can_ack": principal.user_id == handover.receiver_id and principal.role == "supervisor"
            and not stale and not resolved and not ack and owner_allowed})


def read_handover(tx, principal, handover_id, *, item_id=None, revision=None):
    handover = _read_handover(tx, principal, handover_id)
    if (item_id is None) != (revision is None):
        raise DomainError(422, "VALIDATION_ERROR", "과거 조회에는 item_id와 revision이 함께 필요합니다.")
    stmt = select(HandoverItem).where(HandoverItem.handover_id == handover.id).order_by(HandoverItem.id)
    if item_id is not None:
        stmt = stmt.where(HandoverItem.id == item_id)
    items = list(tx.scalars(stmt))
    if item_id is not None and not items:
        raise not_found()
    result = []
    for item in items:
        incident = tx.scalar(select(Incident).where(Incident.id == item.incident_id, Incident.site_id == principal.site_id))
        if incident is None:
            raise not_found()
        selected = tx.get(HandoverRevision, (item.id, revision if revision is not None else item.latest_revision))
        if selected is None:
            raise not_found()
        result.append(_item_data(tx, principal, handover, item, selected, incident))
    included = select(HandoverItem.incident_id).where(HandoverItem.handover_id == handover.id)
    additions = []
    if item_id is None:
        for incident in tx.scalars(select(Incident).where(Incident.site_id == principal.site_id,
                Incident.status != "RESOLVED", _source_scope(handover), Incident.id.not_in(included)).order_by(Incident.id)):
            additions.append({"incident_id": incident.id, "display_id": incident.display_id,
                "title": incident.title, "status": incident.status, "created_at": incident.created_at,
                "added_since_cutoff": incident.created_at > handover.cutoff_at, "can_ack": False})
    return jsonable_encoder({"handover_id": handover.id, "id": handover.id, "site_id": handover.site_id,
        "from_shift_occurrence_id": handover.from_shift_occurrence_id, "to_shift_occurrence_id": handover.to_shift_occurrence_id,
        "from_shift": as_dict(tx.get(Shift, handover.from_shift_occurrence_id)),
        "to_shift": as_dict(tx.get(Shift, handover.to_shift_occurrence_id)),
        "receiver_id": handover.receiver_id, "receiver": user_data(tx, handover.receiver_id),
        "created_by": handover.created_by, "cutoff_at": handover.cutoff_at, "created_at": handover.created_at,
        "refreshed_at": utcnow(), "items": result, "pending_additions": additions,
        "can_refresh": principal.role == "supervisor" and principal.user_id == handover.created_by})


def _stale(tx, principal, handover, item, incident):
    latest = tx.get(HandoverRevision, (item.id, item.latest_revision))
    raise DomainError(409, "HANDOVER_STALE", "새 인계 내용을 다시 확인한 뒤 인수해 주세요.",
        current_version=incident.version, details={"latest_revision": item.latest_revision,
            "latest_item": _item_data(tx, principal, handover, item, latest, incident)})


def _ack_response(tx, incident, item, revision, ack):
    action = tx.scalar(select(Action).where(Action.incident_id == incident.id).order_by(Action.id).limit(1))
    return 200, {"data": jsonable_encoder({"item_id": item.id, "revision": revision.revision,
        "ack_status": "ACKNOWLEDGED", "snapshot_version": revision.snapshot_version,
        "ack_applied_version": ack.ack_applied_version, "incident_version": incident.version,
        "owner_id": incident.owner_id, "owner_shift_occurrence_id": incident.owner_shift_occurrence_id,
        "assignee_id": action.assignee_id if action else None, "acknowledged_by": ack.actor_id,
        "acknowledged_at": ack.acknowledged_at})}


def acknowledge(tx, principal, handover_id, item_id, body):
    handover = _read_handover(tx, principal, handover_id)
    if principal.role != "supervisor" or principal.user_id != handover.receiver_id:
        raise DomainError(403, "FORBIDDEN", "지정 수신 책임자만 항목을 인수할 수 있습니다.")
    reference = tx.scalar(select(HandoverItem).where(HandoverItem.id == item_id, HandoverItem.handover_id == handover.id))
    if reference is None:
        raise not_found()
    incident = tx.scalar(select(Incident).where(Incident.id == reference.incident_id, Incident.site_id == principal.site_id)
        .with_for_update().execution_options(populate_existing=True))
    if incident is None:
        raise not_found()
    _lock_content(tx, [incident.id])
    item = tx.scalar(select(HandoverItem).where(HandoverItem.id == reference.id)
        .with_for_update().execution_options(populate_existing=True))
    if incident.status == "RESOLVED":
        # Return, rather than raise, so execute_command commits rejection + receipt atomically.
        new_event(tx, incident, "rejected_input", principal.user_id,
            related_ids={"handover_id": handover.id, "item_id": item.id},
            payload={"command": "ack_handover", "input": body.model_dump(mode="json")})
        return 409, DomainError(409, "INCIDENT_RESOLVED", "해결된 사건은 새로 인수할 수 없습니다.").body()
    revision = tx.get(HandoverRevision, (item.id, item.latest_revision))
    if (body.revision != item.latest_revision or body.expected_version != revision.snapshot_version
            or not hmac.compare_digest(body.snapshot_token.encode(), revision.snapshot_token.encode())):
        _stale(tx, principal, handover, item, incident)
    owner_allowed = ((incident.owner_id == handover.created_by and incident.owner_shift_occurrence_id == handover.from_shift_occurrence_id)
        or (incident.owner_id == handover.receiver_id and incident.owner_shift_occurrence_id == handover.to_shift_occurrence_id))
    ack = _latest_ack(tx, item)
    expected = ack.ack_applied_version if ack else revision.snapshot_version
    if incident.version != expected or not owner_allowed:
        _stale(tx, principal, handover, item, incident)
    if ack is not None:
        # A different key is a freshly validated command, with no duplicate business effect.
        return _ack_response(tx, incident, item, revision, ack)
    previous_owner_id = incident.owner_id
    incident.owner_id = handover.receiver_id
    incident.owner_shift_occurrence_id = handover.to_shift_occurrence_id
    incident.version += 1
    incident.updated_at = utcnow()
    ack = HandoverAck(id=new_id(), item_id=item.id, revision=revision.revision, actor_id=principal.user_id,
        previous_owner_id=previous_owner_id, new_owner_id=incident.owner_id, ack_applied_version=incident.version)
    tx.add(ack)
    tx.flush()
    new_event(tx, incident, "handover_acknowledged", principal.user_id,
        related_ids={"handover_id": handover.id, "item_id": item.id, "ack_id": ack.id},
        payload={"revision": revision.revision, "snapshot_version": revision.snapshot_version,
            "ack_applied_version": ack.ack_applied_version, "previous_owner_id": previous_owner_id,
            "new_owner_id": incident.owner_id})
    return _ack_response(tx, incident, item, revision, ack)
