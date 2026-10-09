"""Actual F1 finalizer -> F2 ORM -> HTTP commands -> readiness, no live model."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.agent.finalizer import DecisionRejected, finalize
from app.agent.jobs import LostLease
from app.core import models as db
from app.core.errors import DomainError
from app.core.ports import production_ports
from app.core.transactions import enqueue_job, new_event
from app.features.actions.orm import finalize_proposal, readiness
from app.main import create_app
from test_boundary_integration import decision, execution, prepare, proposal


@pytest.fixture
def ports():
    return production_ports()


def post(client, route, body, key=None):
    return client.post('/api/v1' + route, json=body,
        headers={'Origin': 'http://testserver', 'Idempotency-Key': key or str(uuid4())})


def proposed(client, login, session_factory, demo_ids, ports):
    login('reporter')
    response = post(client, '/incidents', {'equipment_id': demo_ids['equipment'], 'text': '확인 범위가 불명확합니다.'})
    assert response.status_code == 202, response.text
    incident_id = response.json()['data']['incident_id']
    context = prepare(session_factory, ports)
    dto = proposal(session_factory, context)
    result = finalize(session_factory, context.identity, execution(dto), ports)
    assert result['status'] == 'SUCCEEDED'
    with session_factory() as tx:
        incident = tx.get(db.Incident, incident_id)
        action = tx.scalar(select(db.Action).where(db.Action.incident_id == incident_id))
        assert incident.version == 3 and incident.status == 'ACTION_REQUIRED'
        assert action.version == 1 and action.assignee_id == demo_ids['maintainer']
        assert tx.scalar(select(func.count()).select_from(db.Event).where(
            db.Event.type.in_(['ACTION_PROPOSED', 'ACTION_PROPOSAL_FINALIZED']))) == 1
        return incident_id, action.id


def approve_start(client, login, action_id):
    login('outgoing_supervisor')
    approval = post(client, f'/actions/{action_id}/approval-decisions', {
        'decision': 'APPROVE', 'reason': '승인 범위 확인', 'expected_version': 1, 'expected_incident_version': 3})
    assert approval.status_code == 200, approval.text
    login('maintainer')
    start = post(client, f'/actions/{action_id}/start', {'expected_version': 2, 'expected_incident_version': 4})
    assert start.status_code == 200, start.text


def complete(client, action_id, key=None):
    return post(client, f'/actions/{action_id}/completion', {
        'result': '  지정 범위와 남은 사항을 확인했습니다.\n', 'evidence_refs': [],
        'expected_version': 3, 'expected_incident_version': 5}, key)


def test_real_http_path_receipt_and_restart(client, login, session_factory, demo_ids, ports, settings):
    incident_id, action_id = proposed(client, login, session_factory, demo_ids, ports)
    approve_start(client, login, action_id)
    key = str(uuid4())
    response = complete(client, action_id, key)
    assert response.status_code == 200, response.text
    result = response.json()['data']
    assert result['verification_ready'] is True and result['unmet_requirements'] == []
    assert result['incident_version'] == 6 and result['incident_status'] == 'PENDING_VERIFICATION'
    replay = complete(client, action_id, key)
    assert replay.json() == response.json() and replay.headers['Idempotent-Replayed'] == 'true'
    with session_factory() as tx:
        incident = tx.get(db.Incident, incident_id)
        assert readiness(tx, incident=incident) == {'ready': True, 'unmet_requirements': []}
        assert tx.scalar(select(func.count()).select_from(db.Approval)) == 1
        assert tx.scalar(select(func.count()).select_from(db.Message).where(db.Message.kind == 'ACTION_RESULT')) == 1
        assert tx.scalar(select(func.count()).select_from(db.Evidence).where(db.Evidence.source_type == 'completion_report')) == 1
        assert tx.get(db.Message, result['result_message_id']).text.startswith('  ')
        assert tx.scalar(select(func.count()).select_from(db.ResolutionCase).where(db.ResolutionCase.incident_id == incident_id)) == 0
    with TestClient(create_app(settings=settings, session_factory=session_factory)) as restarted:
        restarted.cookies.update(client.cookies)
        read = restarted.get(f'/api/v1/incidents/{incident_id}')
        assert read.status_code == 200
        assert read.json()['data']['actions'][0]['completion_evidence_id'] == result['completion_evidence_id']


@pytest.mark.parametrize('defect', ['worker_approval', 'previous_owner', 'action_version', 'incident_version', 'extra_actor', 'wrong_site'])
def test_authority_and_version_rejections(client, login, session_factory, demo_ids, ports, defect):
    incident_id, action_id = proposed(client, login, session_factory, demo_ids, ports)
    login('outgoing_supervisor' if defect != 'worker_approval' else 'maintainer')
    body = {'decision': 'APPROVE', 'reason': '검토', 'expected_version': 1, 'expected_incident_version': 3}
    if defect == 'previous_owner':
        with session_factory.begin() as tx:
            tx.get(db.Incident, incident_id).owner_id = demo_ids['incoming_supervisor']
    if defect == 'wrong_site':
        with session_factory.begin() as tx:
            tx.get(db.Incident, incident_id).site_id = str(uuid4())
    if defect == 'action_version': body['expected_version'] = 2
    if defect == 'incident_version': body['expected_incident_version'] = 2
    if defect == 'extra_actor': body['actor_id'] = demo_ids['incoming_supervisor']
    response = post(client, f'/actions/{action_id}/approval-decisions', body)
    assert response.status_code == {'worker_approval': 403, 'previous_owner': 403, 'action_version': 409,
        'incident_version': 409, 'extra_actor': 422, 'wrong_site': 404}[defect]
    with session_factory() as tx:
        assert tx.get(db.Incident, incident_id).version == 3
        assert tx.scalar(select(func.count()).select_from(db.Approval)) == 0


def test_hook_failure_rolls_back_all_effects_and_receipt(client, login, session_factory, demo_ids, ports):
    incident_id, action_id = proposed(client, login, session_factory, demo_ids, ports)
    approve_start(client, login, action_id)
    def failure(tx, **kwargs):
        assert tx.scalar(select(func.count()).select_from(db.Message).where(db.Message.kind == 'ACTION_RESULT')) == 1
        raise DomainError(503, 'SERVICE_UNAVAILABLE', 'Injected handover persistence failure')
    ports.handover_refresher = failure
    key = str(uuid4())
    assert complete(client, action_id, key).status_code == 503
    with session_factory() as tx:
        assert tx.get(db.Incident, incident_id).version == 5
        assert tx.get(db.Action, action_id).status == 'IN_PROGRESS'
        assert tx.scalar(select(func.count()).select_from(db.Message).where(db.Message.kind == 'ACTION_RESULT')) == 0
        assert tx.scalar(select(func.count()).select_from(db.CommandReceipt).where(db.CommandReceipt.idempotency_key == key)) == 0
    ports.handover_refresher = None
    assert complete(client, action_id, key).status_code == 200


def test_reject_blocks_start_and_readiness(client, login, session_factory, demo_ids, ports):
    incident_id, action_id = proposed(client, login, session_factory, demo_ids, ports)
    login('outgoing_supervisor')
    response = post(client, f'/actions/{action_id}/approval-decisions', {
        'decision': 'REJECT', 'reason': '후속 검토 필요', 'expected_version': 1, 'expected_incident_version': 3})
    assert response.status_code == 200
    login('maintainer')
    response = post(client, f'/actions/{action_id}/start', {'expected_version': 2, 'expected_incident_version': 4})
    assert response.status_code == 409 and response.json()['error']['code'] == 'REVIEW_REQUIRED'
    with session_factory() as tx:
        assert 'REVIEW_REQUIRED' in readiness(tx, incident=tx.get(db.Incident, incident_id))['unmet_requirements']


def test_readiness_port_used_by_real_finalizer(client, login, session_factory, demo_ids, ports):
    incident_id, action_id = proposed(client, login, session_factory, demo_ids, ports)
    approve_start(client, login, action_id)
    assert complete(client, action_id).status_code == 200
    # A new note invalidates verification waiting, then a new server-validated
    # investigation can request verification using the very same readiness code.
    note = post(client, f'/incidents/{incident_id}/messages', {'text': '추가 결과 확인', 'expected_version': 6})
    assert note.status_code == 202
    context = prepare(session_factory, ports)
    result = finalize(session_factory, context.identity, execution(decision('REQUEST_VERIFICATION')), ports)
    assert result['status'] == 'SUCCEEDED' and result['incident_version'] == 8
    with session_factory() as tx:
        assert tx.get(db.Incident, incident_id).status == 'PENDING_VERIFICATION'


@pytest.mark.parametrize('defect', ['empty', 'extra', 'expired'])
def test_finalizer_boundary_and_lease_rollback(client, login, session_factory, demo_ids, ports, defect):
    login('reporter')
    incident_id = post(client, '/incidents', {'equipment_id': demo_ids['equipment'], 'text': '원문'}).json()['data']['incident_id']
    context = prepare(session_factory, ports)
    if defect == 'empty':
        with pytest.raises(DecisionRejected, match='readiness'):
            finalize(session_factory, context.identity, execution(decision('REQUEST_VERIFICATION')), ports)
    else:
        dto = proposal(session_factory, context)
        def faulty(tx, **kwargs):
            result = finalize_proposal(tx, **kwargs)
            if defect == 'extra':
                tx.add(db.Action(incident_id=incident_id, action_slot='EXTRA', scope='extra',
                    assignee_id=demo_ids['maintainer']))
            else:
                tx.get(db.Job, context.identity.job_id).lease_expires_at = db.utcnow() - timedelta(seconds=1)
            tx.flush()
            return result
        ports.action_finalizer = faulty
        with pytest.raises(DecisionRejected if defect == 'extra' else LostLease):
            finalize(session_factory, context.identity, execution(dto), ports)
    with session_factory() as tx:
        assert tx.scalar(select(func.count()).select_from(db.Action)) == 0
        assert tx.get(db.Incident, incident_id).version == 2
        assert tx.get(db.Job, context.identity.job_id).status == 'RUNNING'


def test_two_completion_commands_create_one_result(client, login, session_factory, demo_ids, ports, settings):
    incident_id, action_id = proposed(client, login, session_factory, demo_ids, ports)
    approve_start(client, login, action_id)
    barrier = Barrier(2)
    def send():
        with TestClient(create_app(settings=settings, session_factory=session_factory)) as other:
            other.cookies.update(client.cookies)
            barrier.wait(timeout=5)
            return complete(other, action_id).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(send) for _ in range(2)]
        assert sorted(f.result(timeout=10) for f in futures) == [200, 409]
    with session_factory() as tx:
        assert tx.get(db.Incident, incident_id).version == 6
        assert tx.scalar(select(func.count()).select_from(db.Message).where(db.Message.kind == 'ACTION_RESULT')) == 1


@pytest.mark.parametrize('defect', ['open_question', 'bad_approval', 'wrong_evidence', 'bad_hash', 'blank_key', 'wrong_actor'])
def test_real_completion_gates(client, login, session_factory, demo_ids, ports, defect):
    incident_id, action_id = proposed(client, login, session_factory, demo_ids, ports)
    approve_start(client, login, action_id)
    with session_factory.begin() as tx:
        if defect == 'open_question':
            tx.add(db.Request(incident_id=incident_id, target_user_id=demo_ids['maintainer'],
                purpose_code='VERIFY_RESULT', question='남은 항목이 있습니까?'))
        if defect == 'bad_approval':
            tx.scalar(select(db.Approval)).payload_hash = '0' * 64
        if defect in ('wrong_evidence', 'bad_hash'):
            evidence = tx.get(db.Evidence, tx.get(db.Action, action_id).evidence_refs[0])
            if defect == 'bad_hash': evidence.content_hash = '0' * 64
        if defect == 'wrong_evidence':
            # Move to an existing different incident, never violate the FK just
            # to manufacture a precondition.
            other = db.Incident(display_id=f'OTHER-{uuid4()}', site_id=demo_ids['site'],
                equipment_id=demo_ids['equipment'], reporter_id=demo_ids['reporter'],
                origin_shift_occurrence_id=demo_ids['outgoing_shift'], owner_shift_occurrence_id=demo_ids['outgoing_shift'],
                owner_id=demo_ids['outgoing_supervisor'])
            tx.add(other)
            tx.flush()
            evidence.incident_id = other.id
            tx.flush()
    if defect == 'wrong_actor': login('reporter')
    response = complete(client, action_id, '   ' if defect == 'blank_key' else None)
    if defect == 'open_question':
        assert response.status_code == 200, response.text
        result = response.json()['data']
        assert not result['verification_ready'] and result['incident_status'] == 'IN_PROGRESS'
        assert 'REQUIRED_QUESTION_UNANSWERED' in result['unmet_requirements']
    else:
        assert response.status_code == {'bad_approval': 409, 'wrong_evidence': 422,
            'bad_hash': 422, 'blank_key': 422, 'wrong_actor': 403}[defect], response.text
        with session_factory() as tx:
            assert tx.get(db.Incident, incident_id).version == 5
            assert tx.scalar(select(func.count()).select_from(db.Message).where(db.Message.kind == 'ACTION_RESULT')) == 0


def test_late_completion_receipts_preserve_resolved_snapshot(client, login, session_factory, demo_ids, ports):
    incident_id, action_id = proposed(client, login, session_factory, demo_ids, ports)
    approve_start(client, login, action_id)
    key = str(uuid4())
    first = complete(client, action_id, key)
    assert first.status_code == 200
    with session_factory.begin() as tx:
        incident = tx.get(db.Incident, incident_id)
        incident.status, incident.version = 'RESOLVED', 7
        # Explicit fixture, not an implementation or claim of F4 verification.
        tx.add(db.ResolutionCase(incident_id=incident_id, resolved_version=7,
            site_id=incident.site_id, equipment_id=incident.equipment_id, title='fixture', snapshot_json={'version': 7}))
    assert complete(client, action_id, key).json() == first.json()
    late_key = str(uuid4())
    late = complete(client, action_id, late_key)
    assert late.status_code == 409 and late.json()['error']['code'] == 'INCIDENT_RESOLVED'
    assert complete(client, action_id, late_key).json() == late.json()
    with session_factory() as tx:
        assert tx.get(db.Incident, incident_id).version == 7
        case = tx.scalar(select(db.ResolutionCase).where(db.ResolutionCase.incident_id == incident_id))
        assert case.snapshot_json == {'version': 7}
        assert tx.scalar(select(func.count()).select_from(db.Event).where(db.Event.type == 'rejected_input')) == 1


def test_approval_unique_constraint_and_http_idempotency_conflict(client, login, session_factory, demo_ids, ports):
    incident_id, action_id = proposed(client, login, session_factory, demo_ids, ports)
    login('outgoing_supervisor')
    key = str(uuid4())
    body = {'decision': 'APPROVE', 'reason': '승인', 'expected_version': 1, 'expected_incident_version': 3}
    first = post(client, f'/actions/{action_id}/approval-decisions', body, key)
    assert first.status_code == 200
    assert post(client, f'/actions/{action_id}/approval-decisions', body, key).json() == first.json()
    conflict = post(client, f'/actions/{action_id}/approval-decisions', body | {'reason': '변경'}, key)
    assert conflict.status_code == 409 and conflict.json()['error']['code'] == 'IDEMPOTENCY_CONFLICT'
    with pytest.raises(IntegrityError):
        with session_factory.begin() as tx:
            row = tx.scalar(select(db.Approval))
            tx.add(db.Approval(**{c.name: getattr(row, c.name) for c in db.Approval.__table__.columns if c.name != 'id'}))
    with session_factory() as tx:
        assert tx.get(db.Incident, incident_id).version == 4
        assert tx.scalar(select(func.count()).select_from(db.Approval)) == 1


def test_production_ports_wired_without_test_injection(session_factory, settings):
    from app.features.actions.orm import finalize_proposal, readiness
    app = create_app(settings=settings, session_factory=session_factory)
    assert app.state.ports.action_finalizer is finalize_proposal
    assert app.state.ports.readiness_evaluator is readiness
    paths = app.openapi()['paths']
    assert paths['/api/v1/actions/{action_id}/completion']['post']['responses']['200']['content']['application/json']['schema']
