"""F3/F2/F4 integration through the merged production routes and feature ports."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.features.handovers import service as handovers
from app.features.handovers.schemas import AcknowledgeBody
from app.core import models as db
from app.core.auth import Principal
from app.core.errors import DomainError
from app.core.ports import production_ports
from app.main import create_app
from app.features.resolution.service import verify
from app.features.resolution.schemas import VerificationBody
from test_actions_integration import proposed, approve_start, complete, post
from test_resolution import body, verification


@pytest.fixture
def ports():
    return production_ports()


@pytest.fixture
def client(session_factory, settings, ports):
    app = create_app(session_factory=session_factory, settings=settings, ports=ports)
    with TestClient(app) as client:
        yield client


def handover(client, ids):
    response = post(client, '/handovers', {'from_shift_occurrence_id': ids['outgoing_shift'],
        'to_shift_occurrence_id': ids['incoming_shift']})
    assert response.status_code == 201, response.text
    data = response.json()['data']
    item = data['items'][0]
    return data['id'], item, {'revision': item['revision'], 'snapshot_token': item['snapshot_token'],
        'expected_version': item['snapshot_version']}


def test_actual_f3_ack_before_completion_then_new_owner_verifies(client, login, session_factory, demo_ids, ports):
    incident_id, action_id = proposed(client, login, session_factory, demo_ids, ports)
    approve_start(client, login, action_id)
    login('outgoing_supervisor')
    handover_id, item, ack_body = handover(client, demo_ids)
    login('incoming_supervisor')
    ack_path = f'/handovers/{handover_id}/items/{item["id"]}/ack'
    ack = post(client, ack_path, ack_body, 'f4-integration-ack')
    assert ack.status_code == 200, ack.text
    assert ack.json()['data']['owner_id'] == demo_ids['incoming_supervisor']
    login('maintainer')
    completion = post(client, f'/actions/{action_id}/completion', {
        'result': '인수 후 동일 담당자의 완료 결과', 'expected_version': 3, 'expected_incident_version': 6})
    assert completion.status_code == 200, completion.text
    assert completion.json()['data']['incident_status'] == 'PENDING_VERIFICATION'
    login('outgoing_supervisor')
    assert verification(client, incident_id, body(version=7)).status_code == 403
    login('incoming_supervisor')
    assert verification(client, incident_id, body(version=6)).status_code == 409
    resolved = verification(client, incident_id, body(version=7))
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()['data']['incident_version'] == 8
    latest = client.get(f'/api/v1/handovers/{handover_id}').json()['data']['items'][0]
    assert latest['is_resolved'] and not latest['can_ack']
    assert latest['snapshot']['status'] == 'RESOLVED'
    assert latest['current_assignee_id'] == demo_ids['maintainer']
    past = client.get(f'/api/v1/handovers/{handover_id}', params={'item_id': item['id'], 'revision': item['revision']}).json()['data']['items'][0]
    assert past['snapshot'] == item['snapshot']
    assert post(client, ack_path, ack_body, 'f4-integration-ack').json() == ack.json()
    assert post(client, ack_path, ack_body).status_code == 409
    case = client.get('/api/v1/cases', params={'incident_id': incident_id}).json()['data']['items'][0]
    assert case['reviewer']['id'] == demo_ids['incoming_supervisor']
    assert case['snapshot_json']['actions'][0]['status'] == 'COMPLETED'


@pytest.mark.parametrize('first', ['ack', 'resolve'])
def test_actual_ack_resolve_lock_race(client, login, session_factory, demo_ids, ports, first):
    incident_id, action_id = proposed(client, login, session_factory, demo_ids, ports)
    approve_start(client, login, action_id)
    assert complete(client, action_id).status_code == 200
    login('outgoing_supervisor')
    handover_id, item, ack_body = handover(client, demo_ids)
    outgoing = Principal(demo_ids['outgoing_supervisor'], demo_ids['site'], 'supervisor', '출발')
    incoming = Principal(demo_ids['incoming_supervisor'], demo_ids['site'], 'supervisor', '수신')
    entered, release, second_entered = Event(), Event(), Event()
    def operation(name, primary):
        with session_factory.begin() as tx:
            if primary:
                tx.scalar(select(db.Incident).where(db.Incident.id == incident_id).with_for_update())
                entered.set(); assert release.wait(5)
            else: second_entered.set()
            try:
                if name == 'resolve': return verify(tx, outgoing, incident_id, VerificationBody(**body()), ports)[0]
                return handovers.acknowledge(tx, incoming, handover_id, item['id'], AcknowledgeBody(**ack_body))[0]
            except DomainError as error: return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(operation, first, True)
        assert entered.wait(5)
        b = pool.submit(operation, 'resolve' if first == 'ack' else 'ack', False)
        assert second_entered.wait(5)
        try:
            with pytest.raises(TimeoutError): b.result(timeout=.1)
        finally: release.set()
        assert a.result(timeout=5) == 200
        assert b.result(timeout=5) == (403 if first == 'ack' else 409)
    with session_factory() as tx:
        incident = tx.get(db.Incident, incident_id)
        assert incident.version == 7
        assert incident.owner_id == (incoming.user_id if first == 'ack' else outgoing.user_id)
        assert incident.status == ('PENDING_VERIFICATION' if first == 'ack' else 'RESOLVED')
