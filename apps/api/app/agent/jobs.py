from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import and_, func, or_, select

from app.core.models import AgentRun, Event, HandoverItem, Incident, Job, Request, Action
from .context import RunIdentity, build_context
from .runner import PROMPT_VERSION, TOOL_SCHEMA_VERSION


class LostLease(Exception):
    pass


def db_now(tx, now=None):
    return now if now is not None else tx.scalar(select(func.clock_timestamp()))


def fence(tx, identity: RunIdentity, *, now=None):
    job = tx.scalar(select(Job).where(Job.id == identity.job_id).with_for_update())
    instant = db_now(tx, now)
    if (job is None or job.status != "RUNNING" or job.attempt != identity.attempt
            or job.lease_token != identity.lease_token or job.lease_expires_at is None
            or job.lease_expires_at <= instant):
        raise LostLease("The execution no longer owns this job")
    run = tx.get(AgentRun, identity.run_id)
    if run is None or run.job_id != job.id or run.attempt != job.attempt or run.status != "RUNNING":
        raise LostLease("The run is no longer current")
    return job, run


def metadata_snapshot(metadata=None) -> dict:
    # An allowlist prevents accidentally persisting environment dictionaries or API credentials.
    supplied = metadata or {}
    return {key: supplied.get(key) for key in (
        "app_sha", "dirty", "dataset_version", "settings_id", "run_group_id", "sdk_version",
        "original_run_id", "original_commit", "recorded_at",
    )}


def claim_job(session_factory, *, mode="live", model_id=None, lease_seconds=90,
              max_attempts=3, metadata=None, now=None) -> RunIdentity | None:
    if mode not in {"live", "fake", "replay"}:
        raise ValueError("Unknown execution mode")
    with session_factory.begin() as tx:
        instant = db_now(tx, now)
        job = tx.scalar(select(Job).where(
            Job.attempt < max_attempts,
            or_(and_(Job.status == "QUEUED", Job.available_at <= instant),
                and_(Job.status == "RUNNING", Job.lease_expires_at <= instant)),
        ).order_by(Job.available_at, Job.id).with_for_update(skip_locked=True).limit(1))
        if job is None:
            return None
        if job.status == "RUNNING":
            prior = tx.scalar(select(AgentRun).where(AgentRun.job_id == job.id, AgentRun.attempt == job.attempt))
            if prior is not None and prior.status == "RUNNING":
                prior.status, prior.finished_at = "FAILED", instant
                prior.error_json = {"code": "LEASE_EXPIRED", "message": "A new worker recovered the expired attempt", "retryable": True}
        job.attempt += 1
        job.status, job.lease_token = "RUNNING", str(uuid4())
        job.lease_expires_at, job.updated_at = instant + timedelta(seconds=lease_seconds), instant
        run = AgentRun(job_id=job.id, attempt=job.attempt, trigger_event_id=job.trigger_event_id,
                       mode=mode, model_id=model_id, prompt_version=PROMPT_VERSION,
                       tool_schema_version=TOOL_SCHEMA_VERSION, started_at=instant,
                       metadata_json=metadata_snapshot(metadata))
        tx.add(run)
        tx.flush()
        incident = tx.get(Incident, job.incident_id)
        return RunIdentity(job.id, run.id, incident.id, incident.site_id, job.attempt, job.lease_token)


def lock_incident_graph(tx, identity: RunIdentity):
    incident = tx.scalar(select(Incident).where(Incident.id == identity.incident_id).with_for_update())
    # All writers for an incident serialize on its row; existing children retain the shared lock order.
    list(tx.scalars(select(Action).where(Action.incident_id == incident.id).order_by(Action.id).with_for_update()))
    list(tx.scalars(select(Request).where(Request.incident_id == incident.id).order_by(Request.id).with_for_update()))
    list(tx.scalars(select(HandoverItem).where(HandoverItem.incident_id == incident.id)
                    .order_by(HandoverItem.id).with_for_update()))
    return incident


def prepare_run(session_factory, identity: RunIdentity, ports, *, now=None):
    from app.core.transactions import bump_incident, new_event

    with session_factory.begin() as tx:
        incident = lock_incident_graph(tx, identity)
        fence(tx, identity, now=now)
        if incident.status == "OPEN":
            incident.status = "INVESTIGATING"
            event = new_event(tx, incident, "INVESTIGATION_STARTED", related_ids={"run_id": identity.run_id})
            bump_incident(tx, incident, event, ports)
        fence(tx, identity, now=now)
    # input_version is taken only after the initial OPEN transition commits.
    with session_factory.begin() as tx:
        incident = lock_incident_graph(tx, identity)
        job, run = fence(tx, identity, now=now)
        identity = replace(identity, input_version=incident.version)
        run.input_version = incident.version
        context = build_context(tx, identity, incident)
        context.payload["trigger_event_id"] = job.trigger_event_id
        run.metadata_json = {**run.metadata_json, "observed_source_ids": sorted(context.source_ids)}
        fence(tx, identity, now=now)
        return context


def persist_execution(run, execution):
    run.steps_json = execution.steps
    run.usage_json = {"calls": execution.usage} if any(u is not None for u in execution.usage) else None
    run.model_id = execution.model_id
    run.metadata_json = {**run.metadata_json, "model_calls": execution.model_calls,
                         "api_calls": execution.model_calls if execution.mode == "live" else 0,
                         "tool_calls": execution.tool_calls, "elapsed_seconds": execution.elapsed_seconds}
    run.decision_json = execution.final.model_dump(mode="json") if execution.final else None


def finish_failure(session_factory, identity: RunIdentity, error: dict, *, execution=None, now=None) -> bool:
    try:
        with session_factory.begin() as tx:
            job, run = fence(tx, identity, now=now)
            if execution is not None:
                persist_execution(run, execution)
            run.status, run.error_json, run.finished_at = "FAILED", error, db_now(tx, now)
            job.status, job.last_error, job.updated_at = "FAILED", error, run.finished_at
            job.lease_token = None
        return True
    except LostLease:
        return False


def recover_exhausted(session_factory, *, max_attempts=3, now=None) -> int:
    count = 0
    with session_factory.begin() as tx:
        instant = db_now(tx, now)
        jobs = list(tx.scalars(select(Job).where(Job.status == "RUNNING", Job.attempt >= max_attempts,
                                               Job.lease_expires_at <= instant)
                              .order_by(Job.id).with_for_update(skip_locked=True)))
        for job in jobs:
            error = {"code": "ATTEMPTS_EXHAUSTED", "message": "The last permitted attempt expired", "retryable": False}
            run = tx.scalar(select(AgentRun).where(AgentRun.job_id == job.id, AgentRun.attempt == job.attempt))
            if run is not None and run.status == "RUNNING":
                run.status, run.finished_at, run.error_json = "FAILED", instant, error
            job.status, job.last_error, job.lease_token, job.updated_at = "FAILED", error, None, instant
            count += 1
    return count
