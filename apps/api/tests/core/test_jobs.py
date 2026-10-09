from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import insert,select,update,func
from app.core import schema as s
from app.core.database import transaction
from app.core.errors import DomainError
from app.core.jobs import claim_job,finish_job,recover_exhausted
from app.core.seed import uid
from test_transactions import incident


def queued(database):
    id=incident(database)
    event_id,job_id=uuid4(),uuid4()
    with database.begin() as c:
        c.execute(insert(s.events).values(id=event_id,site_id=uid(1),incident_id=id,type="TEST",related_ids={},payload={}))
        c.execute(insert(s.jobs).values(id=job_id,incident_id=id,trigger_event_id=event_id,job_kind="INVESTIGATE",dedupe_key=str(job_id)))
    return id,job_id


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
