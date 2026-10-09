"""Independent DB-connection races and F3 port rollback for F1.

F3 fixtures/adapters here are contract doubles, not the F3 product implementation.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event as ThreadEvent
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.auth import Principal
from app.core.errors import DomainError
from app.core.models import (CommandReceipt, Event, Handover, HandoverItem,
                             HandoverRevision, Incident, Job, Message, Request)
from app.core.transactions import execute_command
from app.main import create_app


def report(client, headers, equipment_id):
    response = client.post('/api/v1/incidents', json={'equipment_id': equipment_id,
        'text': '동시 명령 시험 원문', 'observed_at': None},
        headers={**headers, 'Idempotency-Key': str(uuid4())})
    assert response.status_code == 202, response.text
    return response.json()['data']


def counts(tx, incident_id):
    return tuple(tx.scalar(select(func.count()).select_from(model).where(model.incident_id == incident_id))
                 for model in (Message, Event, Job))


@pytest.mark.ac3
@pytest.mark.ac34
def test_same_receipt_two_http_connections_one_report(session_factory, settings, ports, demo_ids, auth_headers):
    app = create_app(settings=settings, ports=ports, session_factory=session_factory)
    body = {'equipment_id': demo_ids['equipment'], 'text': '실제 동시 제보', 'observed_at': None}
    key = str(uuid4())
    barrier = Barrier(2)
    def send():
        with TestClient(app) as client:
            assert client.post('/api/v1/demo/session', json={'account_key':'reporter'}, headers=auth_headers).status_code == 200
            barrier.wait(timeout=5)
            return client.post('/api/v1/incidents', json=body, headers={**auth_headers,'Idempotency-Key':key})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: send(), range(2)))
    assert any(response.status_code == 202 for response in results)
    for response in results:
        assert response.status_code in (202, 409)
        if response.status_code == 409:
            assert response.json()['error']['code'] == 'COMMAND_IN_PROGRESS'
    with TestClient(app) as client:
        client.post('/api/v1/demo/session', json={'account_key':'reporter'}, headers=auth_headers)
        replay = client.post('/api/v1/incidents', json=body, headers={**auth_headers,'Idempotency-Key':key})
    first = next(response for response in results if response.status_code == 202)
    assert replay.json() == first.json()
    assert replay.headers['Idempotent-Replayed'] == 'true'
    with session_factory() as tx:
        assert tx.scalar(select(func.count()).select_from(Incident)) == 1
        assert counts(tx, first.json()['data']['incident_id']) == (1, 1, 1)
        assert tx.scalar(select(func.count()).select_from(CommandReceipt)) == 1


@pytest.mark.ac3
def test_in_progress_receipt_never_runs_second_handler(session_factory, demo_ids):
    principal = Principal(demo_ids['reporter'], demo_ids['site'], 'worker', '시험 작업자')
    entered, finish = ThreadEvent(), ThreadEvent()
    key = str(uuid4())
    def slow(tx):
        entered.set()
        assert finish.wait(5)
        return 202, {'data': {'value': 'original'}}
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(execute_command, session_factory, principal, key, 'POST', '/receipttest', {}, slow)
        assert entered.wait(5)
        try:
            with pytest.raises(DomainError) as captured:
                execute_command(session_factory, principal, key, 'POST', '/receipttest', {},
                                lambda tx: pytest.fail('duplicate handler must not execute'))
            assert captured.value.code == 'COMMAND_IN_PROGRESS'
        finally:
            finish.set()
        assert future.result(timeout=5)[0] == 202
    assert execute_command(session_factory, principal, key, 'POST', '/receipttest', {},
                           lambda tx: pytest.fail('replay must bypass the handler'))[2] is True


@pytest.mark.ac3
@pytest.mark.ac21
@pytest.mark.ac22
@pytest.mark.ac34
def test_two_answer_commands_one_reply_and_job(session_factory, settings, ports, demo_ids, auth_headers, login, client):
    login('reporter')
    created = report(client, auth_headers, demo_ids['equipment'])
    with session_factory.begin() as tx:
        question = Request(incident_id=created['incident_id'], target_user_id=demo_ids['maintainer'],
                           purpose_code='VERIFY_SCOPE', question='확인한 범위는?', is_required=True)
        tx.add(question)
        tx.flush()
        question_id = question.id
    body = {'text':'외관을 확인했습니다.', 'expected_version':1, 'reply_to_request_id':question_id,
            'observed_at':None, 'correction_of':None}
    app = create_app(settings=settings, ports=ports, session_factory=session_factory)
    barrier = Barrier(2)
    keys = [str(uuid4()), str(uuid4())]
    def send(key):
        with TestClient(app) as actor:
            actor.post('/api/v1/demo/session', json={'account_key':'maintainer'}, headers=auth_headers)
            barrier.wait(timeout=5)
            return key, actor.post(f"/api/v1/incidents/{created['incident_id']}/messages", json=body,
                                  headers={**auth_headers,'Idempotency-Key':key})
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(send, keys))
    assert sorted(response.status_code for _, response in results) == [202,409]
    failure = next(response for _,response in results if response.status_code == 409)
    assert failure.json()['error']['code'] in {'VERSION_CONFLICT','REQUEST_CLOSED'}
    good_key, good_response = next(pair for pair in results if pair[1].status_code == 202)
    login('maintainer')
    replay = client.post(f"/api/v1/incidents/{created['incident_id']}/messages", json=body,
                         headers={**auth_headers,'Idempotency-Key':good_key})
    assert replay.json() == good_response.json()
    assert replay.headers['Idempotent-Replayed'] == 'true'
    with session_factory() as tx:
        assert counts(tx, created['incident_id']) == (2,2,2)
        assert tx.get(Incident, created['incident_id']).version == 2
        q = tx.get(Request, question_id)
        assert (q.status,q.version,q.is_required,q.target_user_id) == ('ANSWERED',2,True,demo_ids['maintainer'])
        assert tx.get(Message, q.response_message_id).reply_to_request_id == question_id


@pytest.mark.ac5
@pytest.mark.ac34
def test_missing_or_failing_handover_adapter_rolls_back_new_input(session_factory, ports, demo_ids, auth_headers, login, client):
    login('reporter')
    created = report(client, auth_headers, demo_ids['equipment'])
    with session_factory.begin() as tx:
        handover = Handover(site_id=demo_ids['site'], from_shift_occurrence_id=demo_ids['outgoing_shift'],
            to_shift_occurrence_id=demo_ids['incoming_shift'], receiver_id=demo_ids['incoming_supervisor'],
            created_by=demo_ids['outgoing_supervisor'])
        tx.add(handover)
        tx.flush()
        item = HandoverItem(handover_id=handover.id,incident_id=created['incident_id'])
        tx.add(item)
        tx.flush()
        item_id = item.id
        tx.add(HandoverRevision(item_id=item.id, revision=1, snapshot_version=1,
                               snapshot_json={'immutable':'original'}, snapshot_token='original-token'))
    body = {'text':'새 정보', 'expected_version':1, 'reply_to_request_id':None, 'observed_at':None,'correction_of':None}
    key = str(uuid4())
    uri = f"/api/v1/incidents/{created['incident_id']}/messages"
    def check_unchanged():
        with session_factory() as tx:
            assert counts(tx,created['incident_id']) == (1,1,1)
            assert tx.get(Incident,created['incident_id']).version == 1
            assert tx.get(HandoverItem,item_id).latest_revision == 1
            assert tx.get(HandoverRevision,(item_id,1)).snapshot_json == {'immutable':'original'}
            assert tx.get(HandoverRevision,(item_id,2)) is None
            assert tx.scalar(select(CommandReceipt.id).where(CommandReceipt.idempotency_key == key)) is None
    missing = client.post(uri,json=body,headers={**auth_headers,'Idempotency-Key':key})
    assert missing.status_code == 503
    check_unchanged()
    def fail_after_write(tx, *, incident, event):
        item = tx.get(HandoverItem,item_id)
        item.latest_revision = 2
        tx.add(HandoverRevision(item_id=item_id,revision=2,snapshot_version=incident.version,
                               snapshot_json={'test_contract':'pending new snapshot'},snapshot_token='new-token'))
        tx.flush()
        raise DomainError(503,'SERVICE_UNAVAILABLE','계약 대체의 실패',retryable=False)
    ports.handover_refresher = fail_after_write
    failed = client.post(uri,json=body,headers={**auth_headers,'Idempotency-Key':key})
    assert failed.status_code == 503
    check_unchanged()
