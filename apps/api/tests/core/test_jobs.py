from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import uuid4
import pytest
from sqlalchemy import insert,select,update,func,event,text
from app.core import schema as s
from app.core.database import transaction
from app.core.errors import DomainError
from app.core.jobs import claim_job,finish_job,recover_exhausted
from app.core import jobs as job_service
from app.core.seed import uid
from test_transactions import incident


def queued(database, status="INVESTIGATING"):
    id=incident(database)
    event_id,job_id=uuid4(),uuid4()
    with database.begin() as c:
        c.execute(update(s.incidents).where(s.incidents.c.id == id).values(status=status))
        c.execute(insert(s.events).values(id=event_id,site_id=uid(1),incident_id=id,type="TEST",related_ids={},payload={}))
        c.execute(insert(s.jobs).values(id=job_id,incident_id=id,trigger_event_id=event_id,job_kind="INVESTIGATE",dedupe_key=str(job_id)))
    return id,job_id


def test_first_open_investigation_can_persist_a_question(database, settings):
    id, job = queued(database, status="OPEN")
    claim = claim_job(database, settings)
    with database.connect() as c:
        row = c.execute(select(s.incidents).where(s.incidents.c.id == id)).mappings().one()
        assert row["status"] == "INVESTIGATING"
        assert row["version"] == claim.input_version == 2
        assert c.scalar(select(s.agent_runs.c.input_version).where(s.agent_runs.c.id == claim.run_id)) == 2

    question_id = uuid4()
    def apply(tx):
        tx.connection.execute(insert(s.requests).values(id=question_id, incident_id=id,
            target_user_id=uid(202), purpose_code="VERIFY_SCOPE", question="어떤 범위를 확인했나요?",
            is_required=True, status="OPEN", evidence_refs=[]))
        tx.bump_incident(id, claim.input_version)
    assert finish_job(database, claim, run_status="WAITING_INPUT", apply=apply) == "WAITING_INPUT"
    with database.connect() as c:
        assert c.scalar(select(s.requests.c.id).where(s.requests.c.id == question_id)) == question_id
        assert c.scalar(select(s.jobs.c.status).where(s.jobs.c.id == job)) == "SUCCEEDED"
        assert c.scalar(select(s.incidents.c.version).where(s.incidents.c.id == id)) == 3


def expire(database,job_id):
    with database.begin() as c:
        c.execute(update(s.jobs).where(s.jobs.c.id==job_id).values(lease_expires_at=func.now()-timedelta(seconds=1)))


def test_two_claimers_only_one_wins(database,settings):
    queued(database)
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims=list(pool.map(lambda _:claim_job(database,settings),range(2)))
    assert sum(c is not None for c in claims) == 1


@pytest.mark.parametrize("status",["SUCCEEDED","FAILED"])
def test_old_worker_cannot_finish_or_apply_after_reclaim(database,settings,status):
    id,job=queued(database)
    first=claim_job(database,settings)
    expire(database,job)
    second=claim_job(database,settings)
    assert second.attempt == 2 and first.token != second.token
    with pytest.raises(DomainError):
        finish_job(database,first,run_status=status,apply=lambda tx:tx.bump_incident(id,1))
    assert finish_job(database,second,run_status="WAITING_INPUT") == "WAITING_INPUT"
    with database.connect() as c:
        assert c.scalar(select(s.incidents.c.version).where(s.incidents.c.id==id)) == 1
        assert c.scalar(select(s.jobs.c.status).where(s.jobs.c.id==job)) == "SUCCEEDED"


def test_stale_input_skips_business_and_supersedes(database,settings):
    id,job=queued(database)
    claim=claim_job(database,settings)
    with transaction(database) as tx:
        tx.lock_incident(id)
        tx.bump_incident(id,1)
    def forbidden(tx): raise AssertionError("stale apply called")
    assert finish_job(database,claim,run_status="SUCCEEDED",apply=forbidden) == "SUPERSEDED"


def test_final_lease_check_rolls_back_staged_business(database,settings):
    id,job=queued(database)
    claim=claim_job(database,settings)
    def apply(tx):
        tx.bump_incident(id,1)
        tx.connection.execute(update(s.jobs).where(s.jobs.c.id==job).values(lease_expires_at=func.now()-timedelta(seconds=1)))
    with pytest.raises(DomainError):finish_job(database,claim,run_status="SUCCEEDED",apply=apply)
    with database.connect() as c:
        assert c.scalar(select(s.incidents.c.version).where(s.incidents.c.id==id)) == 1
        assert c.scalar(select(s.agent_runs.c.status).where(s.agent_runs.c.id==claim.run_id)) == "RUNNING"


def test_final_attempt_recovery_is_once_and_terminal(database,settings):
    id,job=queued(database)
    settings=settings.model_copy(update={"job_max_attempts":1})
    claim=claim_job(database,settings)
    expire(database,job)
    assert claim_job(database,settings) is None
    assert recover_exhausted(database,1) == 1
    assert recover_exhausted(database,1) == 0
    with pytest.raises(DomainError):finish_job(database,claim,run_status="FAILED")
    with database.connect() as c:
        assert c.scalar(select(s.jobs.c.last_error).where(s.jobs.c.id==job))["code"] == "ATTEMPTS_EXHAUSTED"
        assert c.scalar(select(s.agent_runs.c.status).where(s.agent_runs.c.id==claim.run_id)) == "FAILED"


def test_successful_finalizer_commits_business_with_run(database,settings):
    id,job=queued(database)
    claim=claim_job(database,settings)
    assert finish_job(database,claim,run_status="SUCCEEDED",apply=lambda tx:tx.bump_incident(id,1)) == "SUCCEEDED"
    with database.connect() as c:
        assert c.scalar(select(s.incidents.c.version).where(s.incidents.c.id==id)) == 2
        assert c.scalar(select(s.agent_runs.c.applied_version).where(s.agent_runs.c.id==claim.run_id)) == 2
        assert c.scalar(select(s.jobs.c.lease_token).where(s.jobs.c.id==job)) is None


@pytest.mark.parametrize("status", ["INVESTIGATING", "ACTION_REQUIRED", "IN_PROGRESS", "PENDING_VERIFICATION", "RESOLVED"])
def test_claim_preserves_existing_business_state(database, settings, status):
    id, _ = queued(database, status=status)
    claim = claim_job(database, settings)
    with database.connect() as c:
        row = c.execute(select(s.incidents).where(s.incidents.c.id == id)).mappings().one()
        assert row["status"] == status and row["version"] == claim.input_version == 1
        assert c.scalar(select(func.count()).select_from(s.events).where(s.events.c.type == "INVESTIGATION_STARTED")) == 0


def test_open_retry_does_not_repeat_initial_transition(database, settings):
    id, job = queued(database, status="OPEN")
    first = claim_job(database, settings)
    expire(database, job)
    second = claim_job(database, settings)
    assert first.input_version == second.input_version == 2
    assert second.attempt == 2
    with database.connect() as c:
        assert c.scalar(select(func.count()).select_from(s.events).where(s.events.c.type == "INVESTIGATION_STARTED")) == 1
        assert c.scalar(select(s.agent_runs.c.status).where(s.agent_runs.c.id == first.run_id)) == "SUPERSEDED"


@pytest.mark.parametrize("reclaim", [False, True])
def test_preparation_rejects_lost_lease_and_rolls_back_state(database, settings, monkeypatch, reclaim):
    id, job = queued(database, status="OPEN")
    prepare = job_service._prepare_investigation
    def lose_lease(engine, lease, hook):
        expire(engine, job)
        if reclaim:
            assert job_service._reserve_job(engine, settings).attempt == 2
        prepare(engine, lease, hook)
    monkeypatch.setattr(job_service, "_prepare_investigation", lose_lease)
    with pytest.raises(DomainError) as error:
        claim_job(database, settings)
    assert error.value.code == "LEASE_LOST"
    with database.connect() as c:
        row = c.execute(select(s.incidents).where(s.incidents.c.id == id)).mappings().one()
        assert row["status"] == "OPEN" and row["version"] == 1
        assert c.scalar(select(func.count()).select_from(s.events)) == 1  # Only the original trigger.
        assert c.scalar(select(func.count()).select_from(s.agent_runs)) == 0


def test_expiry_after_preparation_creates_no_run_and_is_recoverable(database, settings, monkeypatch):
    id, job = queued(database, status="OPEN")
    prepare = job_service._prepare_investigation
    def expire_after_commit(engine, lease, hook):
        prepare(engine, lease, hook)
        # Separate connection proves that preparation has committed before capture.
        with engine.connect() as c:
            assert c.scalar(select(s.incidents.c.status).where(s.incidents.c.id == id)) == "INVESTIGATING"
        expire(engine, job)
    monkeypatch.setattr(job_service, "_prepare_investigation", expire_after_commit)
    with pytest.raises(DomainError):
        claim_job(database, settings)
    with database.connect() as c:
        assert c.scalar(select(func.count()).select_from(s.agent_runs)) == 0
    monkeypatch.setattr(job_service, "_prepare_investigation", prepare)
    claim = claim_job(database, settings)
    assert claim.attempt == 2 and claim.input_version == 2
    assert finish_job(database, claim, run_status="SUCCEEDED") == "SUCCEEDED"


def test_run_captures_committed_version_after_preparation(database, settings, monkeypatch):
    id, _ = queued(database, status="OPEN")
    prepare = job_service._prepare_investigation
    def new_information(engine, lease, hook):
        prepare(engine, lease, hook)
        with transaction(engine) as tx:
            row = tx.lock_incident(id)
            assert row["version"] == 2
            tx.bump_incident(id, 2)  # A separate committed change before model input is acquired.
    monkeypatch.setattr(job_service, "_prepare_investigation", new_information)
    claim = claim_job(database, settings)
    assert claim.input_version == 3
    with database.connect() as c:
        assert c.scalar(select(s.agent_runs.c.input_version).where(s.agent_runs.c.id == claim.run_id)) == 3


def test_preparation_hook_failure_rolls_back_with_transition(database, settings):
    id, _ = queued(database, status="OPEN")
    def fail(tx, before, after):
        assert before["status"] == "OPEN" and after["status"] == "INVESTIGATING"
        raise RuntimeError("revision persistence failed")
    with pytest.raises(RuntimeError, match="revision persistence failed"):
        claim_job(database, settings, on_investigation_started=fail)
    with database.connect() as c:
        assert c.scalar(select(s.incidents.c.version).where(s.incidents.c.id == id)) == 1
        assert c.scalar(select(func.count()).select_from(s.events)) == 1


def test_preparation_does_not_hold_job_while_waiting_for_incident(database, settings):
    id, job = queued(database, status="OPEN")
    waiting = Event()
    def before_execute(connection, cursor, statement, parameters, context, many):
        if "FROM incidents" in statement and "FOR UPDATE" in statement:
            waiting.set()
    event.listen(database, "before_cursor_execute", before_execute)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with database.begin() as c:
                c.execute(select(s.incidents.c.id).where(s.incidents.c.id == id).with_for_update())
                waiting.clear()
                future = pool.submit(claim_job, database, settings)
                assert waiting.wait(5)
                c.execute(text("SET LOCAL lock_timeout = '500ms'"))
                # A normal Incident -> Job writer must still be able to acquire Job.
                c.execute(select(s.jobs.c.id).where(s.jobs.c.id == job).with_for_update()).one()
            assert future.result(timeout=5).input_version == 2
    finally:
        event.remove(database, "before_cursor_execute", before_execute)
