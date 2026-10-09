from __future__ import annotations

from hashlib import sha256
import json

from sqlalchemy import func, select, text

from .errors import DomainError, not_found
from .models import CommandReceipt, Event, Incident, Job, new_id, utcnow


def new_event(tx, incident, type, actor_id=None, payload=None, related_ids=None):
    event = Event(id=new_id(), site_id=incident.site_id, incident_id=incident.id,
                  type=type, actor_id=actor_id, payload=payload or {}, related_ids=related_ids or {})
    tx.add(event)
    tx.flush()
    return event


def bump_incident(tx, incident, event, ports):
    incident.version += 1
    incident.updated_at = utcnow()
    tx.flush()
    ports.refresh_handover_items(tx, incident=incident, event=event)


def enqueue_job(tx, incident, event):
    job = Job(id=new_id(), incident_id=incident.id, trigger_event_id=event.id,
              dedupe_key=f"{incident.id}:{event.id}:INVESTIGATE", status="QUEUED", attempt=0,
              available_at=tx.scalar(select(func.clock_timestamp())))
    tx.add(job)
    tx.flush()
    return job


def lock_incident(tx, incident_id, principal):
    incident = tx.scalar(select(Incident).where(Incident.id == incident_id,
                           Incident.site_id == principal.site_id).with_for_update())
    if incident is None:
        raise not_found()
    return incident


def require_version(incident, expected_version):
    if incident.version != expected_version:
        raise DomainError(409, "VERSION_CONFLICT", "새 정보가 있습니다. 최신 내용을 다시 확인해 주세요.",
                          current_version=incident.version,
                          details={"target": "incident", "expected_version": expected_version})


def execute_command(session_factory, principal, key, method, route, body, handler):
    """Serialize receipt identity without leaving a reservation outside the business tx."""
    if not key or not key.strip() or len(key) > 200:
        raise DomainError(422, "VALIDATION_ERROR", "유효한 Idempotency-Key가 필요합니다.")
    canonical = json.dumps({"method": method.upper(), "route": route, "body": body},
                           sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = sha256(canonical.encode()).hexdigest()
    lock_key = int.from_bytes(sha256(f"{principal.site_id}:{principal.user_id}:{key}".encode()).digest()[:8], "big", signed=True)
    with session_factory.begin() as tx:
        locked = tx.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": lock_key})
        if not locked:
            raise DomainError(409, "COMMAND_IN_PROGRESS", "같은 요청이 처리 중입니다.", retryable=True)
        receipt = tx.scalar(select(CommandReceipt).where(CommandReceipt.site_id == principal.site_id,
            CommandReceipt.actor_id == principal.user_id, CommandReceipt.idempotency_key == key))
        if receipt:
            if receipt.payload_hash != digest:
                raise DomainError(409, "IDEMPOTENCY_CONFLICT", "같은 키로 다른 요청을 보낼 수 없습니다.")
            return receipt.http_status, receipt.response_json, True
        status, response = handler(tx)
        tx.add(CommandReceipt(site_id=principal.site_id, actor_id=principal.user_id,
            idempotency_key=key, payload_hash=digest, http_status=status, response_json=response, status="COMPLETED"))
        tx.flush()
        return status, response, False
