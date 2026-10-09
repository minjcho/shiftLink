"""Real F1 proposal, F2 commands and F3 ACKs share the production adapters."""
import pytest
from sqlalchemy import select, func
from app.core import models as db
from app.core.ports import production_ports
from app.features.handovers.service import refresh_handover_items
from test_actions_integration import proposed, post

@pytest.fixture
def ports():
    return production_ports()


def make_handover(client, login, ids):
    login('outgoing_supervisor')
    response = post(client, '/handovers', {
        'from_shift_occurrence_id': ids['outgoing_shift'],
        'to_shift_occurrence_id': ids['incoming_shift'],
    })
    assert response.status_code == 201, response.text
    return response.json()['data']


def get_handover(client, handover):
    response = client.get('/api/v1/handovers/' + handover['id'])
    assert response.status_code == 200, response.text
    return response.json()['data']


def ack(client, handover):
    item = handover['items'][0]
    response = post(client, f'/handovers/{handover["id"]}/items/{item["id"]}/ack', {
        'revision': item['revision'], 'snapshot_token': item['snapshot_token'],
        'expected_version': item['snapshot_version'],
    })
    assert response.status_code == 200, response.text
    return response.json()['data']


def test_production_f2_f3_workflow_preserves_authority_and_revisions(client, login, session_factory, demo_ids, ports):
    assert ports.handover_refresher is refresh_handover_items
    incident_id, action_id = proposed(client, login, session_factory, demo_ids, ports)
    handover = make_handover(client, login, demo_ids)
    login('incoming_supervisor')
    first_ack = ack(client, handover)
    assert first_ack['incident_version'] == 4
    current = get_handover(client, handover)
    assert current['items'][0]['revision'] == 1 and not current['items'][0]['is_stale']
    approval_body = {'decision':'APPROVE','reason':'인수 후 검토','expected_version':1,'expected_incident_version':4}
    login('outgoing_supervisor')
    assert post(client, f'/actions/{action_id}/approval-decisions', approval_body).status_code == 403
    login('incoming_supervisor')
    approval = post(client, f'/actions/{action_id}/approval-decisions', approval_body)
    assert approval.status_code == 200, approval.text
    current = get_handover(client, handover)
    assert current['items'][0]['revision'] == 2
    assert current['items'][0]['snapshot']['actions'][0]['status'] == 'APPROVED'
    login('maintainer')
    started = post(client, f'/actions/{action_id}/start', {'expected_version':2,'expected_incident_version':5})
    assert started.status_code == 200, started.text
    login('incoming_supervisor')
    current = get_handover(client, handover)
    assert current['items'][0]['revision'] == 3
    assert current['items'][0]['snapshot']['actions'][0]['status'] == 'IN_PROGRESS'
    assert ack(client, current)['incident_version'] == 7
    login('maintainer')
    result = post(client, f'/actions/{action_id}/completion', {
        'result':'실제 F2 결과 저장 경로 검증', 'evidence_refs':[],
        'expected_version':3, 'expected_incident_version':7,
    })
    assert result.status_code == 200, result.text
    assert result.json()['data']['verification_ready'] is True
    assert result.json()['data']['incident_status'] == 'PENDING_VERIFICATION'
    login('incoming_supervisor')
    current = get_handover(client, handover)
    item = current['items'][0]
    assert item['revision'] == 4 and item['requires_ack']
    assert item['snapshot']['actions'][0]['status'] == 'COMPLETED'
    assert any(e['source_type'] == 'completion_report' for e in item['snapshot']['evidence'])
    assert ack(client, current)['incident_version'] == 9
    with session_factory() as tx:
        incident = tx.get(db.Incident, incident_id)
        action = tx.get(db.Action, action_id)
        assert incident.owner_id == demo_ids['incoming_supervisor']
        assert action.assignee_id == demo_ids['maintainer']
        assert incident.status == 'PENDING_VERIFICATION'
        assert tx.scalar(select(func.count()).select_from(db.ResolutionCase).where(db.ResolutionCase.incident_id == incident_id)) == 0


def test_default_api_uses_same_feature_composition(session_factory, settings):
    from app.features.actions.orm import finalize_proposal, readiness
    from app.main import create_app
    app = create_app(settings=settings, session_factory=session_factory)
    assert app.state.ports.action_finalizer is finalize_proposal
    assert app.state.ports.readiness_evaluator is readiness
    assert app.state.ports.handover_refresher is refresh_handover_items
