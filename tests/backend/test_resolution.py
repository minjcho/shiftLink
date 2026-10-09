"""F4 on real F1/F2 HTTP + PostgreSQL. No model calls or substitute readiness."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core import models as db
from app.core.auth import Principal
from app.core.errors import DomainError
from app.core.ports import production_ports
from app.features.intake.schemas import MessageBody
from app.features.intake.service import add_message
from app.features.resolution.schemas import VerificationBody
from app.features.resolution.service import verify
from app.main import create_app
from test_actions_integration import proposed, approve_start, complete, post


@pytest.fixture
def ports():
    return production_ports()


@pytest.fixture
def pending(client, login, session_factory, demo_ids, ports):
    incident_id, action_id = proposed(client, login, session_factory, demo_ids, ports)
    approve_start(client, login, action_id)
    response = complete(client, action_id)
    assert response.status_code == 200, response.text
    login('outgoing_supervisor')
    return incident_id, action_id


def body(decision='RESOLVE', version=6, **kwargs):
    return {'decision': decision, 'expected_version': version, 'notes': '  승인 내용과 완료 결과를 확인했습니다.\n',
            'evidence_refs': [], **kwargs}


def verification(client, incident_id, payload=None, key=None):
    return post(client, f'/incidents/{incident_id}/verification', payload or body(), key)


def assert_no_resolution(factory, incident_id):
    with factory() as tx:
        assert tx.get(db.Incident, incident_id).status != 'RESOLVED'
        assert tx.scalar(select(func.count()).select_from(db.Verification)) == 0
        assert tx.scalar(select(func.count()).select_from(db.ResolutionCase)
            .where(db.ResolutionCase.incident_id == incident_id)) == 0


def test_resolve_snapshot_receipt_restart(client, login, session_factory, pending, settings, ports):
    incident_id, action_id = pending
    before = client.get(f'/api/v1/incidents/{incident_id}').json()['data']['resolution']
    assert before['ready'] and before['can_resolve'] and before['checked_version'] == 6
    key = str(uuid4())
    first = verification(client, incident_id, key=key)
    assert first.status_code == 200, first.text
    result = first.json()['data']
    assert result['incident_status'] == 'RESOLVED' and result['incident_version'] == 7
    replay = verification(client, incident_id, key=key)
    assert replay.json() == first.json() and replay.headers['Idempotent-Replayed'] == 'true'
    conflict = verification(client, incident_id, body(notes='다른 내용'), key)
    assert conflict.status_code == 409 and conflict.json()['error']['code'] == 'IDEMPOTENCY_CONFLICT'
    cases = client.get('/api/v1/cases', params={'incident_id': incident_id}).json()['data']['items']
    assert len(cases) == 1 and cases[0]['id'] == result['case_id']
    snapshot = cases[0]['snapshot_json']
    assert snapshot['verification']['notes'] == body()['notes']
    assert snapshot['verification']['checked_version'] == 6
    assert snapshot['incident']['version'] == 7 and snapshot['incident']['status'] == 'RESOLVED'
    assert snapshot['actions'][0]['status'] == 'COMPLETED' and len(snapshot['approvals']) == 1
    assert snapshot['actions'][0]['completion_evidence_id'] in cases[0]['evidence_refs']
    assert 'analysis' not in snapshot['incident']
    late = post(client, f'/incidents/{incident_id}/messages', {'text': '늦은 원문', 'expected_version': 6})
    assert late.status_code == 409
    late_key = str(uuid4())
    late_verify = verification(client, incident_id, key=late_key)
    assert late_verify.status_code == 409
    assert verification(client, incident_id, key=late_key).json() == late_verify.json()
    with TestClient(create_app(settings=settings, ports=ports, session_factory=session_factory)) as restarted:
        restarted.cookies.update(client.cookies)
        assert restarted.get('/api/v1/cases', params={'incident_id': incident_id}).json()['data']['items'] == cases
        assert verification(restarted, incident_id, key=key).json() == first.json()
    with session_factory() as tx:
        assert tx.get(db.Incident, incident_id).version == 7
        assert tx.scalar(select(func.count()).select_from(db.Verification)) == 1
        assert tx.scalar(select(func.count()).select_from(db.Event).where(db.Event.type == 'rejected_input')) == 2


@pytest.mark.parametrize('defect,status', [
    ('no_action', 409), ('unfinished', 409), ('approval', 409), ('question', 409),
    ('result', 409), ('completion_evidence', 409), ('review', 409), ('bad_hash', 409),
    ('notes', 422), ('extra_evidence', 422), ('wrong_site_evidence', 422),
    ('stale', 409), ('state', 409), ('actor', 422), ('bool_version', 422),
    ('worker', 403), ('previous_owner', 403), ('site', 404), ('unknown', 404)])
def test_final_gates(client, login, session_factory, demo_ids, pending, defect, status):
    incident_id, action_id = pending
    payload = body()
    with session_factory.begin() as tx:
        incident = tx.get(db.Incident, incident_id)
        action = tx.get(db.Action, action_id)
        if defect == 'no_action': action.is_required = False
        if defect == 'unfinished': action.status = 'IN_PROGRESS'
        if defect == 'approval': tx.scalar(select(db.Approval)).payload_hash = '0' * 64
        if defect == 'question': tx.add(db.Request(incident_id=incident_id, target_user_id=demo_ids['maintainer'], purpose_code='VERIFY_RESULT', question='남은 사항?'))
        if defect == 'result': action.result_message_id = None
        if defect == 'completion_evidence': action.completion_evidence_id = None
        if defect == 'review': incident.review_required = True
        if defect == 'bad_hash': tx.get(db.Evidence, action.completion_evidence_id).content_hash = '0' * 64
        if defect == 'state': incident.status = 'INVESTIGATING'
        if defect == 'previous_owner': incident.owner_id = demo_ids['incoming_supervisor']
        if defect == 'site': incident.site_id = str(uuid4())
        if defect == 'wrong_site_evidence':
            extra = db.Evidence(incident_id=incident_id, site_id=str(uuid4()), source_type='message', source_id=action.result_message_id,
                excerpt='foreign', content_hash='0'*64, equipment_id=incident.equipment_id)
            tx.add(extra); tx.flush(); payload['evidence_refs'] = [extra.id]
    if defect == 'notes': payload['notes'] = ' \n '
    if defect == 'extra_evidence': payload['evidence_refs'] = [str(uuid4())]
    if defect == 'stale': payload['expected_version'] = 5
    if defect == 'bool_version': payload['expected_version'] = True
    if defect == 'actor': payload['actor_id'] = demo_ids['incoming_supervisor']
    if defect == 'worker': login('maintainer')
    target = str(uuid4()) if defect == 'unknown' else incident_id
    response = verification(client, target, payload)
    assert response.status_code == status, response.text
    assert_no_resolution(session_factory, incident_id)


def test_return_preserves_completed_results_and_blocks_agent(client, session_factory, pending, ports):
    from app.agent.finalizer import DecisionRejected, finalize
    from app.core.transactions import enqueue_job, new_event
    from test_boundary_integration import prepare, execution, decision
    incident_id, action_id = pending
    # A reviewer must be able to RETURN even if a prerequisite is now invalid.
    with session_factory.begin() as tx:
        tx.scalar(select(db.Approval)).payload_hash = '0'*64
    key = str(uuid4())
    response = verification(client, incident_id, body('RETURN'), key)
    assert response.status_code == 200, response.text
    assert response.json()['data']['case_id'] is None and response.json()['data']['resolved_at'] is None
    assert verification(client, incident_id, body('RETURN'), key).json() == response.json()
    with session_factory.begin() as tx:
        incident = tx.get(db.Incident, incident_id)
        action = tx.get(db.Action, action_id)
        assert incident.review_required and incident.status == 'INVESTIGATING' and incident.version == 7
        assert incident.review_reason == body()['notes']
        assert action.status == 'COMPLETED' and tx.get(db.Message, action.result_message_id)
        assert tx.get(db.Evidence, action.completion_evidence_id)
        assert tx.scalar(select(func.count()).select_from(db.ResolutionCase).where(db.ResolutionCase.incident_id == incident_id)) == 0
        enqueue_job(tx, incident, new_event(tx, incident, 'test_investigation'))
    context = prepare(session_factory, ports)
    with pytest.raises(DecisionRejected):
        finalize(session_factory, context.identity, execution(decision('REQUEST_VERIFICATION')), ports)
    assert verification(client, incident_id, body(version=7)).status_code == 409


def test_atomic_hook_failure(client, session_factory, pending, ports):
    incident_id, _ = pending
    def fail(tx, **kwargs):
        assert tx.scalar(select(func.count()).select_from(db.Verification)) == 1
        raise DomainError(503, 'SERVICE_UNAVAILABLE', 'Injected F3 storage failure')
    ports.handover_refresher = fail
    key = str(uuid4())
    assert verification(client, incident_id, key=key).status_code == 503
    assert_no_resolution(session_factory, incident_id)
    with session_factory() as tx:
        assert tx.get(db.Incident, incident_id).version == 6
        assert tx.scalar(select(func.count()).select_from(db.CommandReceipt).where(db.CommandReceipt.idempotency_key == key)) == 0
    ports.handover_refresher = None
    assert verification(client, incident_id, key=key).status_code == 200


def test_two_resolvers_one_case(client, settings, session_factory, pending, ports):
    incident_id, _ = pending
    def send():
        with TestClient(create_app(settings=settings, ports=ports, session_factory=session_factory)) as other:
            other.cookies.update(client.cookies)
            return verification(other, incident_id).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(send) for _ in range(2)]
        assert sorted(f.result(timeout=10) for f in futures) == [200, 409]
    with session_factory() as tx:
        assert tx.scalar(select(func.count()).select_from(db.Verification)) == 1
        assert tx.scalar(select(func.count()).select_from(db.ResolutionCase).where(db.ResolutionCase.incident_id == incident_id)) == 1


@pytest.mark.parametrize('first', ['message', 'resolve'])
def test_message_resolve_lock_race(session_factory, demo_ids, pending, ports, first):
    incident_id, _ = pending
    actor = Principal(demo_ids['outgoing_supervisor'], demo_ids['site'], 'supervisor', '검토자')
    entered, release, second_entered = Event(), Event(), Event()
    def operation(name, primary):
        with session_factory.begin() as tx:
            if primary:
                tx.scalar(select(db.Incident).where(db.Incident.id == incident_id).with_for_update())
                entered.set(); assert release.wait(5)
            else: second_entered.set()
            try:
                if name == 'resolve': return verify(tx, actor, incident_id, VerificationBody(**body()), ports)[0]
                return add_message(tx, actor, incident_id, MessageBody(text='경합 원문', expected_version=6), ports)[0]
            except DomainError as error: return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(operation, first, True)
        assert entered.wait(5)
        b = pool.submit(operation, 'resolve' if first == 'message' else 'message', False)
        assert second_entered.wait(5)
        try:
            with pytest.raises(TimeoutError): b.result(timeout=.1)
        finally: release.set()
        assert a.result(timeout=5) == (202 if first == 'message' else 200)
        assert b.result(timeout=5) == 409
    with session_factory() as tx:
        incident = tx.get(db.Incident, incident_id)
        assert incident.version == 7
        assert incident.status == ('INVESTIGATING' if first == 'message' else 'RESOLVED')
        assert tx.scalar(select(func.count()).select_from(db.ResolutionCase).where(db.ResolutionCase.incident_id == incident_id)) == (first == 'resolve')


def test_case_scope_paging_and_invalid_cursors(client, login, session_factory, pending, demo_ids):
    incident_id, _ = pending
    assert verification(client, incident_id).status_code == 200
    with session_factory.begin() as tx:
        tx.add(db.ResolutionCase(site_id=str(uuid4()), equipment_id=demo_ids['equipment'], title='foreign-secret'))
        for i in range(2):
            tx.add(db.ResolutionCase(site_id=demo_ids['site'], equipment_id=demo_ids['equipment'], title=f'past-{i}'))
    seen = []
    cursor = None
    while True:
        params = {'limit': 1, **({'cursor': cursor} if cursor else {})}
        response = client.get('/api/v1/cases', params=params)
        assert response.status_code == 200, response.text
        page = response.json()['data']
        seen += [x['id'] for x in page['items']]
        assert 'foreign-secret' not in response.text
        cursor = page['next_cursor']
        if not cursor: break
    assert len(seen) == len(set(seen)) and len(seen) >= 3
    for bad in ('?', 'bnVsbA==', 'W10=', 'eyJpZCI6ImJhZCJ9'):
        assert client.get('/api/v1/cases', params={'cursor': bad}).status_code == 422
    assert client.get('/api/v1/cases', params={'incident_id': str(uuid4())}).status_code == 404
    with session_factory.begin() as tx: tx.get(db.Incident, incident_id).site_id = str(uuid4())
    assert client.get('/api/v1/cases', params={'incident_id': incident_id}).status_code == 404


def test_missing_port_and_security(client, login, pending, ports):
    incident_id, _ = pending
    ports.readiness_evaluator = None
    assert not client.get(f'/api/v1/incidents/{incident_id}').json()['data']['resolution']['can_resolve']
    assert verification(client, incident_id).status_code == 503
    assert client.post(f'/api/v1/incidents/{incident_id}/verification', json=body()).status_code == 403
    assert client.post(f'/api/v1/incidents/{incident_id}/verification', json=body(), headers={'Origin':'http://testserver'}).status_code == 422
    client.cookies.clear()
    assert post(client, f'/incidents/{incident_id}/verification', body()).status_code == 401
    assert client.get('/api/v1/cases').status_code == 401


def test_resolved_case_is_searchable_as_case(client, login, session_factory, demo_ids, pending, ports):
    import json
    from app.agent.tools import ToolExecutor
    from test_boundary_integration import prepare
    incident_id, _ = pending
    case_id = verification(client, incident_id).json()['data']['case_id']
    login('reporter')
    report = post(client, '/incidents', {'equipment_id': demo_ids['equipment'], 'text': '비슷한 확인 범위 사건'})
    assert report.status_code == 202
    context = prepare(session_factory, ports)
    result = ToolExecutor(session_factory, context)('search_similar_incidents', json.dumps({
        'equipment_id': demo_ids['equipment'], 'query': '확인 범위'}))
    assert result['outcome'] == 'OK', result
    hit = next(x for x in result['data']['items'] if x['case_id'] == case_id)
    assert hit['source_type'] == 'case' and hit['source_id'] == case_id


def test_snapshot_insert_failure_rolls_back_every_write(client, session_factory, pending):
    from sqlalchemy import event
    incident_id, _ = pending
    def fail(*args):
        raise DomainError(503, 'SERVICE_UNAVAILABLE', 'Injected case insert failure')
    key = str(uuid4())
    event.listen(db.ResolutionCase, 'before_insert', fail)
    try:
        assert verification(client, incident_id, key=key).status_code == 503
    finally:
        event.remove(db.ResolutionCase, 'before_insert', fail)
    assert_no_resolution(session_factory, incident_id)
    with session_factory() as tx:
        assert tx.get(db.Incident, incident_id).version == 6
        assert tx.scalar(select(func.count()).select_from(db.Event).where(db.Event.type == 'incident_resolved')) == 0
        assert tx.scalar(select(func.count()).select_from(db.CommandReceipt).where(db.CommandReceipt.idempotency_key == key)) == 0
    assert verification(client, incident_id, key=key).status_code == 200


def test_scope_before_replay_but_owner_after_replay(client, session_factory, pending, demo_ids):
    incident_id, _ = pending
    key = str(uuid4())
    first = verification(client, incident_id, key=key)
    with session_factory.begin() as tx:
        tx.get(db.Incident, incident_id).owner_id = demo_ids['incoming_supervisor']
    assert verification(client, incident_id, key=key).json() == first.json()
    assert verification(client, incident_id).status_code == 403
    with session_factory.begin() as tx:
        tx.get(db.Incident, incident_id).site_id = str(uuid4())
    assert verification(client, incident_id, key=key).status_code == 404
