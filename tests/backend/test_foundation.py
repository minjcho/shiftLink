"""F0 guarantees exercised against the F1 database and HTTP implementation."""
from datetime import timedelta
import os
import subprocess
import sys
import time
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from app.core.models import Base, SessionToken, Shift, ShiftAssignment, User, Incident, Job, AgentRun, utcnow
from app.core.worker_lock import single_worker, WORKER_LOCK
from app.agent.jobs import claim_job, prepare_run, LostLease
from app.core.ports import FeaturePorts
from test_agent import create_job, decision, execution
from app.agent.finalizer import finalize


def test_session_rotation_revocation_and_restart(client, login, auth_headers, session_factory, settings):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.core.contracts import SessionView
    login()
    old = client.cookies.get('shiftlink_session')
    before = SessionView.model_validate(client.get('/api/v1/me').json()['data'])
    session_factory.kw['bind'].dispose()
    with TestClient(create_app(settings=settings, session_factory=session_factory)) as restarted:
        restarted.cookies.set('shiftlink_session', old)
        assert restarted.get('/api/v1/me').json()['data'] == before.model_dump(mode='json')
        login('incoming_supervisor')
        assert restarted.get('/api/v1/me').status_code == 401
    assert client.get('/api/v1/me').json()['data']['user_id'] != str(before.user_id)


@pytest.mark.parametrize('change', ['disabled', 'foreign_shift', 'removed_assignment'])
def test_current_session_rechecks_assignment_and_site(client, login, demo_ids, session_factory, change):
    login()
    with session_factory.begin() as tx:
        if change == 'disabled':
            tx.get(User, demo_ids['reporter']).enabled = False
        elif change == 'foreign_shift':
            tx.get(Shift, demo_ids['outgoing_shift']).site_id = str(uuid4())
        else:
            tx.execute(delete(ShiftAssignment).where(ShiftAssignment.user_id == demo_ids['reporter']))
    assert client.get('/api/v1/me').status_code in (401, 403)
    assert client.get('/api/v1/equipment').status_code in (401, 403)


def test_no_assignment_cannot_rotate_or_revoke_previous_session(client, login, auth_headers, demo_ids, session_factory):
    login()
    old = client.cookies.get('shiftlink_session')
    with session_factory.begin() as tx:
        tx.execute(delete(ShiftAssignment).where(ShiftAssignment.user_id == demo_ids['maintainer']))
    result = client.post('/api/v1/demo/session', json={'account_key':'maintainer'}, headers=auth_headers)
    assert result.status_code == 422
    assert result.json()['error']['code'] == 'SHIFT_ASSIGNMENT_MISSING'
    assert client.cookies.get('shiftlink_session') == old
    assert client.get('/api/v1/me').status_code == 200


def test_session_does_not_silently_move_when_active_shift_changes(client, login, demo_ids, session_factory):
    login('maintainer')
    before = client.get('/api/v1/me').json()['data']
    with session_factory.begin() as tx:
        tx.get(Shift, demo_ids['outgoing_shift']).active = False
        tx.flush()
        tx.get(Shift, demo_ids['incoming_shift']).active = True
    assert client.get('/api/v1/me').json()['data'] == before
    login('maintainer')
    assert client.get('/api/v1/me').json()['data']['shift_occurrence_id'] == demo_ids['incoming_shift']


def test_single_worker_exclusion_release_and_lost_connection(session_factory):
    engine = session_factory.kw['bind']
    with single_worker(engine) as check:
        check()
        with pytest.raises(RuntimeError, match='Another ShiftLink worker'):
            with single_worker(engine):
                pytest.fail('second worker acquired lock')
    with single_worker(engine) as check:
        check()
        with engine.connect() as tx:
            pid = tx.scalar(text('SELECT pid FROM pg_locks WHERE locktype=\'advisory\' AND objid=:key AND granted'), {'key': WORKER_LOCK})
            assert pid
            tx.execute(text('SELECT pg_terminate_backend(:pid)'), {'pid': pid})
        with pytest.raises(DBAPIError):
            check()
    with single_worker(engine) as check:
        check()


@pytest.mark.parametrize('status,blocked', [('OPEN',False),('OPEN',True),('IN_PROGRESS',False),('PENDING_VERIFICATION',False),('RESOLVED',False)])
def test_initial_transition_uses_committed_version_and_preserves_other_states(session_factory, demo_ids, status, blocked):
    incident_id, _ = create_job(session_factory, demo_ids, status=status, review_required=blocked)
    identity = claim_job(session_factory, mode='fake')
    context = prepare_run(session_factory, identity, FeaturePorts())
    expected = 2 if status == 'OPEN' and not blocked else 1
    with session_factory() as tx:
        assert tx.get(Incident, incident_id).version == expected
        assert tx.get(AgentRun, identity.run_id).input_version == expected == context.identity.input_version
        assert tx.get(Incident, incident_id).status == ('INVESTIGATING' if expected == 2 else status)
    if expected == 2:
        result = finalize(session_factory, context.identity, execution(decision(context,'ASK_USER')), FeaturePorts())
        assert result['status'] != 'SUPERSEDED'


def test_expired_preparation_cannot_commit_transition(session_factory, demo_ids):
    incident_id, job_id = create_job(session_factory, demo_ids)
    identity = claim_job(session_factory, mode='fake')
    with session_factory.begin() as tx:
        tx.get(Job,job_id).lease_expires_at = utcnow() - timedelta(seconds=1)
    with pytest.raises(LostLease):
        prepare_run(session_factory, identity, FeaturePorts())
    with session_factory() as tx:
        assert tx.get(Incident,incident_id).status == 'OPEN'
        assert tx.get(Incident,incident_id).version == 1


def test_maintenance_process_recovers_expiry_without_claiming(session_factory, settings, demo_ids):
    _, exhausted_id = create_job(session_factory,demo_ids)
    identity = claim_job(session_factory,mode='fake')
    with session_factory.begin() as tx:
        job = tx.get(Job, exhausted_id)
        job.attempt = settings.job_max_attempts
        job.lease_expires_at = utcnow() - timedelta(seconds=1)
        tx.get(AgentRun,identity.run_id).attempt = job.attempt
    _, queued_id = create_job(session_factory,demo_ids)
    engine = session_factory.kw['bind']
    with engine.connect() as tx:
        schema = tx.scalar(text('SELECT current_schema()'))
    url = engine.url.update_query_dict({'options':f'-csearch_path={schema}'}).render_as_string(hide_password=False)
    env = {**os.environ, 'PYTHONPATH':'apps/api','DATABASE_URL':url,'SESSION_SECRET':settings.session_secret,
           'WORKER_POLL_INTERVAL_SECONDS':'1','OPENAI_API_KEY':'','OPENAI_AGENT_MODEL':''}
    process = subprocess.Popen([sys.executable,'-m','app.agent.worker','--mode','maintenance'],
                               env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    try:
        deadline = time.monotonic()+10
        while time.monotonic()<deadline:
            assert process.poll() is None
            with session_factory() as tx:
                if tx.get(Job,exhausted_id).status == 'FAILED':
                    break
            time.sleep(.05)
        else:
            pytest.fail('maintenance did not recover exhausted job')
        with session_factory() as tx:
            assert tx.get(Job,queued_id).status == 'QUEUED'
            assert tx.get(Job,queued_id).attempt == 0
            assert tx.get(Job,exhausted_id).last_error['code'] == 'ATTEMPTS_EXHAUSTED'
    finally:
        process.terminate()
        process.communicate(timeout=10)
    assert process.returncode == 0


def test_f1_migration_upgrade_preserves_business_rows_and_legacy_tokens(monkeypatch, settings, demo_ids):
    from app.core.seed import seed_demo
    from app.core.db import create_session_factory
    schema = 'f0_migration_' + uuid4().hex
    admin = create_engine(settings.database_url)
    with admin.begin() as tx:
        tx.execute(text(f'CREATE SCHEMA "{schema}"'))
    url = make_url(settings.database_url).update_query_dict({'options': f'-csearch_path={schema}'}).render_as_string(hide_password=False)
    monkeypatch.setenv('DATABASE_URL',url)
    config = Config('apps/api/alembic.ini')
    factory = create_session_factory(url)
    try:
        command.upgrade(config,'0001_f1_foundation')
        with factory.begin() as tx:
            seed_demo(tx)
            tx.execute(text('INSERT INTO session_tokens (id,user_id,token_hash,expires_at) VALUES (:id,:user,\'legacy\',now()+interval \'1 hour\')'), {'id':str(uuid4()),'user':demo_ids['reporter']})
        incident_id, job_id = create_job(factory,demo_ids)
        for _ in range(2):
            command.upgrade(config,'head')
            with factory() as tx:
                assert tx.get(Incident,incident_id).version == 1
                assert tx.get(Job,job_id).status == 'QUEUED'
                assert tx.scalar(select(SessionToken)).shift_occurrence_id is None
            with factory.kw['bind'].connect() as tx:
                assert compare_metadata(MigrationContext.configure(tx),Base.metadata) == []
            command.downgrade(config,'0001_f1_foundation')
        command.upgrade(config,'head')
    finally:
        factory.kw['bind'].dispose()
        with admin.begin() as tx:
            tx.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_tool_waiting_for_incident_does_not_hold_job_lock(session_factory, demo_ids):
    """An owner holding Incident can still lock Job while a tool waits: no AB/BA cycle."""
    from concurrent.futures import ThreadPoolExecutor
    import json
    from app.core.db import create_session_factory
    from app.agent.tools import ToolExecutor
    from test_agent import prepared
    context = prepared(session_factory, demo_ids)
    engine = session_factory.kw['bind']
    with engine.connect() as tx:
        schema = tx.scalar(text('SELECT current_schema()'))
    name = 'f0-tool-' + uuid4().hex
    other = create_session_factory(engine.url.render_as_string(hide_password=False),
        connect_args={'options': f'-csearch_path={schema}', 'application_name': name})
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with session_factory.begin() as owner:
                owner.execute(select(Incident).where(Incident.id == context.identity.incident_id).with_for_update())
                future = pool.submit(ToolExecutor(other, context), 'search_documents',
                                     json.dumps({'equipment_id':demo_ids['equipment'],'query':'점검'}))
                deadline = time.monotonic()+5
                while time.monotonic()<deadline:
                    with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as monitor:
                        waiting = monitor.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE application_name=:name AND wait_event_type='Lock'"), {'name':name})
                    if waiting:
                        break
                    time.sleep(.02)
                else:
                    pytest.fail('tool did not reach the concurrent row lock')
                owner.execute(select(Job).where(Job.id == context.identity.job_id).with_for_update(nowait=True))
            assert future.result(timeout=5)['outcome'] == 'OK'
    finally:
        other.kw['bind'].dispose()
