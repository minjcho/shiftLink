"""Lease primitives. F1 supplies the investigation handler and business finalizer."""
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, insert, update, and_, or_, func

from .database import transaction
from .errors import DomainError
from .schema import jobs, agent_runs, incidents


@dataclass(frozen=True)
class Claim:
    job_id: UUID
    run_id: UUID
    incident_id: UUID
    attempt: int
    token: UUID
    input_version: int


def claim_job(engine, settings):
    with engine.begin() as connection:
        job = connection.execute(select(jobs).where(jobs.c.attempt < settings.job_max_attempts,
            or_(and_(jobs.c.status == "QUEUED", jobs.c.available_at <= func.clock_timestamp()),
                and_(jobs.c.status == "RUNNING", jobs.c.lease_expires_at <= func.clock_timestamp())))
            .order_by(jobs.c.available_at, jobs.c.id).with_for_update(skip_locked=True).limit(1)).mappings().one_or_none()
        if job is None:
            return None
        if job["status"] == "RUNNING":
            connection.execute(update(agent_runs).where(agent_runs.c.job_id == job["id"], agent_runs.c.status == "RUNNING")
                .values(status="SUPERSEDED", finished_at=func.clock_timestamp(), error_json={"code": "LEASE_EXPIRED"}))
        version = connection.scalar(select(incidents.c.version).where(incidents.c.id == job["incident_id"]))
        token, run_id, attempt = uuid4(), uuid4(), job["attempt"] + 1
        connection.execute(update(jobs).where(jobs.c.id == job["id"]).values(status="RUNNING", attempt=attempt,
            lease_token=token, lease_expires_at=func.clock_timestamp() + timedelta(seconds=settings.job_lease_seconds),
            updated_at=func.clock_timestamp()))
        connection.execute(insert(agent_runs).values(id=run_id, job_id=job["id"], attempt=attempt,
            trigger_event_id=job["trigger_event_id"], input_version=version, status="RUNNING", mode=settings.agent_mode))
        return Claim(job["id"], run_id, job["incident_id"], attempt, token, version)


def finish_job(engine, claim, *, run_status, apply=None, error=None):
    """Stage business changes under Incident lock; validate Job lease LAST.

    apply(tx) must not commit or call external services. Any failure, including
    lease expiry during apply, rolls back all staged business rows.
    """
    if run_status not in ("SUCCEEDED", "WAITING_INPUT", "FAILED"):
        raise ValueError("Invalid final run status")
    with transaction(engine) as tx:
        incident = tx.lock_incident(claim.incident_id)
        # Fast preliminary read; the authoritative lease check follows all business locks.
        valid = tx.connection.scalar(select(jobs.c.id).where(jobs.c.id == claim.job_id,
            jobs.c.status == "RUNNING", jobs.c.attempt == claim.attempt, jobs.c.lease_token == claim.token,
            jobs.c.lease_expires_at > func.clock_timestamp()))
        if valid is None:
            raise DomainError(409, "LEASE_LOST", "실행 권한이 만료됐습니다.")
        stale = incident["version"] != claim.input_version
        final_status = "SUPERSEDED" if stale else run_status
        if not stale and apply is not None:
            apply(tx)
        tx.connection.execute(select(jobs.c.id).where(jobs.c.id == claim.job_id).with_for_update()).one()
        job_status = "SUCCEEDED" if final_status == "WAITING_INPUT" else final_status
        changed = tx.connection.execute(update(jobs).where(jobs.c.id == claim.job_id,
            jobs.c.status == "RUNNING", jobs.c.attempt == claim.attempt, jobs.c.lease_token == claim.token,
            jobs.c.lease_expires_at > func.clock_timestamp()).values(status=job_status,
                lease_token=None, lease_expires_at=None, last_error=error, updated_at=func.clock_timestamp()))
        if changed.rowcount != 1:
            raise DomainError(409, "LEASE_LOST", "실행 권한이 만료됐습니다.")
        applied_version = tx.connection.scalar(select(incidents.c.version).where(incidents.c.id == claim.incident_id))
        changed = tx.connection.execute(update(agent_runs).where(agent_runs.c.id == claim.run_id,
            agent_runs.c.job_id == claim.job_id, agent_runs.c.attempt == claim.attempt, agent_runs.c.status == "RUNNING")
            .values(status=final_status, applied_version=None if stale else applied_version,
                    error_json=error, finished_at=func.clock_timestamp()))
        if changed.rowcount != 1:
            raise RuntimeError("Claim and running AgentRun do not match")
        return final_status


def recover_exhausted(engine, max_attempts):
    """Narrow D03 recovery: no business writes or new model calls."""
    with engine.begin() as connection:
        ids = list(connection.scalars(select(jobs.c.id).where(jobs.c.status == "RUNNING",
            jobs.c.attempt >= max_attempts, jobs.c.lease_expires_at <= func.clock_timestamp())
            .order_by(jobs.c.id).with_for_update(skip_locked=True)))
        for job_id in ids:
            error = {"code": "ATTEMPTS_EXHAUSTED"}
            connection.execute(update(jobs).where(jobs.c.id == job_id).values(status="FAILED", last_error=error,
                lease_token=None, lease_expires_at=None, updated_at=func.clock_timestamp()))
            connection.execute(update(agent_runs).where(agent_runs.c.job_id == job_id, agent_runs.c.status == "RUNNING")
                .values(status="FAILED", error_json=error, finished_at=func.clock_timestamp()))
        return len(ids)
