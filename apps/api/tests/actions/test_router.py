import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.features.actions.router import create_actions_router
from app.features.actions.responses import CompletionResult, SuccessEnvelope
from app.features.actions.service import ActionApplication
from support import MAINTAINER, NOW, OWNER, uid


@pytest.fixture
def client(store):
    app = FastAPI()
    # Only the test harness supplies a principal; production must use F0 auth + Origin.
    def principal(): return OWNER
    app.include_router(create_actions_router(ActionApplication(store.transaction, lambda: NOW),
                                             principal, lambda: {"request_id": "http-test"}), prefix="/api/v1")
    app.state.principal_dependency = principal
    return TestClient(app)


def test_three_routes_only_and_no_public_create_edit_delete(client):
    assert set(client.app.openapi()["paths"]) == {
        "/api/v1/actions/{action_id}/approval-decisions", "/api/v1/actions/{action_id}/start",
        "/api/v1/actions/{action_id}/completion"}
    assert client.post("/api/v1/actions", json={}).status_code == 404
    assert client.patch(f"/api/v1/actions/{uid(501)}/start", json={}).status_code == 405


def test_http_approval_replay_is_exact(client):
    url = f"/api/v1/actions/{uid(501)}/approval-decisions"
    body = {"decision": "APPROVE", "reason": "확인", "expected_version": 1, "expected_incident_version": 5}
    first = client.post(url, json=body, headers={"Idempotency-Key": "same"})
    second = client.post(url, json=body, headers={"Idempotency-Key": "same"})
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json() and second.headers["Idempotent-Replayed"] == "true"


@pytest.mark.parametrize("body", [
    {"expected_version": 1},
    {"expected_version": 1, "expected_incident_version": 5, "role": "supervisor"},
    {"expected_version": True, "expected_incident_version": 5},
    {"expected_version": "1", "expected_incident_version": 5},
])
def test_http_rejects_missing_fields_and_actor_injection(client, body):
    response = client.post(f"/api/v1/actions/{uid(501)}/start", json=body, headers={"Idempotency-Key": "a"})
    assert response.status_code == 422


def test_no_missing_auth_fallback(client):
    def reject(): raise HTTPException(401)
    client.app.dependency_overrides[client.app.state.principal_dependency] = reject
    assert client.post(f"/api/v1/actions/{uid(501)}/start", json={"expected_version": 1,
        "expected_incident_version": 5}, headers={"Idempotency-Key": "a"}).status_code == 401


def test_missing_key_is_validation_error(client):
    assert client.post(f"/api/v1/actions/{uid(501)}/start", json={
        "expected_version": 1, "expected_incident_version": 5}).status_code == 422


def test_http_complete_flow(client, store):
    base = f"/api/v1/actions/{uid(501)}"
    assert client.post(base + "/approval-decisions", json={"decision": "APPROVE", "reason": "확인",
        "expected_version": 1, "expected_incident_version": 5}, headers={"Idempotency-Key": "a"}).status_code == 200
    client.app.dependency_overrides[client.app.state.principal_dependency] = lambda: MAINTAINER
    assert client.post(base + "/start", json={"expected_version": 2, "expected_incident_version": 6},
                       headers={"Idempotency-Key": "b"}).status_code == 200
    result = client.post(base + "/completion", json={"result": "완료 기록", "evidence_refs": [],
        "expected_version": 3, "expected_incident_version": 7}, headers={"Idempotency-Key": "c"})
    assert result.status_code == 200 and result.json()["data"]["verification_ready"]
    SuccessEnvelope[CompletionResult].model_validate(result.json())
