from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.models import (Action, AgentRun, CommandReceipt, Equipment, Event, Evidence, Handover,
    HandoverItem, HandoverRevision, Incident, Job, Message, Request, ResolutionCase, Shift, ShiftAssignment, User, utcnow)


def post_report(client, ids, headers, *, text="  CV-03 소음과 진동 제보 원문  ", key=None):
    response = client.post("/api/v1/incidents", json={"equipment_id": ids["equipment"], "text": text},
                           headers={**headers, "Idempotency-Key": key or str(uuid4())})
    assert response.status_code == 202, response.text
    return response


def add_question(factory, incident_id, target):
    question_id = str(uuid4())
    with factory.begin() as tx:
        tx.add(Request(id=question_id, incident_id=incident_id, target_user_id=target,
            purpose_code="VERIFY_SCOPE", question="어디까지 확인했나요?", is_required=True,
            status="OPEN", version=1, evidence_refs=[]))
    return question_id


def counts(factory, incident_id):
    with factory() as tx:
        return {model.__tablename__: tx.scalar(select(func.count()).select_from(model).where(model.incident_id == incident_id))
                for model in (Message, Event, Job)}


@pytest.mark.ac1
@pytest.mark.ac2
def test_report_is_persisted_without_worker_and_reconnects(client, login, demo_ids, auth_headers, session_factory):
    login()
    response = post_report(client, demo_ids, auth_headers)
    data = response.json()["data"]
    assert data["version"] == 1 and data["status"] == "OPEN"
    session_factory.kw["bind"].dispose()
    detail = client.get(f"/api/v1/incidents/{data['incident_id']}").json()["data"]
    assert detail["messages"][0]["text"] == "  CV-03 소음과 진동 제보 원문  "
    assert detail["messages"][0]["id"] == data["message_id"]
    assert detail["owner_id"] == demo_ids["outgoing_supervisor"]
    assert detail["latest_job"]["id"] == data["job_id"]
    assert detail["latest_job"]["status"] == "QUEUED"
    assert counts(session_factory, data["incident_id"]) == {"messages": 1, "events": 1, "jobs": 1}


@pytest.mark.ac2
def test_session_origin_spoofing_scope_and_missing_assignment(client, login, demo_ids, auth_headers, session_factory):
    payload = {"equipment_id": demo_ids["equipment"], "text": "원문"}
    assert client.post("/api/v1/incidents", json=payload, headers={**auth_headers,"Idempotency-Key":"auth"}).status_code == 401
    assert client.post("/api/v1/demo/session", json={"account_key":"reporter"}).status_code == 403
    login()
    for field in ("actor_id", "site_id", "role", "owner_id", "assignee_id"):
        r = client.post("/api/v1/incidents", json={**payload,field:"forged"}, headers={**auth_headers,"Idempotency-Key":field})
        assert r.status_code == 422
    assert client.post("/api/v1/incidents", json=payload, headers={"Origin":"https://evil.example","Idempotency-Key":"evil"}).status_code == 403
    with session_factory.begin() as tx:
        tx.get(Shift, demo_ids["outgoing_shift"]).active = False
    missing = client.post("/api/v1/incidents", json=payload, headers={**auth_headers,"Idempotency-Key":"missing"})
    assert missing.status_code == 422 and missing.json()["error"]["code"] == "SHIFT_ASSIGNMENT_MISSING"
    with session_factory() as tx:
        assert tx.scalar(select(func.count()).select_from(Incident)) == 0


@pytest.mark.ac2
@pytest.mark.ac9
def test_other_site_cannot_read_or_write_existing_resources(client,login,demo_ids,auth_headers,session_factory):
    login()
    data = post_report(client,demo_ids,auth_headers).json()["data"]
    with session_factory.begin() as tx:
        foreign_site, foreign_shift = str(uuid4()), str(uuid4())
        tx.get(User,demo_ids["maintainer"]).site_id = foreign_site
        tx.add(Shift(id=foreign_shift, site_id=foreign_site, label="foreign",
                     starts_at=utcnow(), ends_at=utcnow()+timedelta(hours=4),
                     supervisor_id=demo_ids["maintainer"], active=True))
        tx.flush()
        tx.add(ShiftAssignment(shift_occurrence_id=foreign_shift, user_id=demo_ids["maintainer"], duty="MAINTENANCE"))
    login("maintainer")
    for path in (f"/api/v1/incidents/{data['incident_id']}",f"/api/v1/jobs/{data['job_id']}"):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json()["error"]["current_version"] is None
        assert data["incident_id"] not in response.text
    assert client.get("/api/v1/incidents").json()["data"]["items"] == []
    response = client.post(f"/api/v1/incidents/{data['incident_id']}/messages",json={"text":"foreign","expected_version":1},
        headers={**auth_headers,"Idempotency-Key":"foreign"})
    assert response.status_code == 404 and counts(session_factory,data["incident_id"])["messages"] == 1


@pytest.mark.ac4
@pytest.mark.ac21
def test_cross_incident_links_and_stale_input_have_no_side_effect(client,login,demo_ids,auth_headers,session_factory):
    login()
    first = post_report(client,demo_ids,auth_headers).json()["data"]
    other = post_report(client,demo_ids,auth_headers).json()["data"]
    qid = add_question(session_factory,other["incident_id"],demo_ids["reporter"])
    path = f"/api/v1/incidents/{first['incident_id']}/messages"
    for number,body in enumerate([
        {"text":"외부 정정","expected_version":1,"correction_of":other["message_id"]},
        {"text":"외부 답변","expected_version":1,"reply_to_request_id":qid},
        {"text":"오래된 화면","expected_version":20},
    ]):
        response = client.post(path,json=body,headers={**auth_headers,"Idempotency-Key":f"invalid-{number}"})
        assert response.status_code == (409 if number == 2 else 404)
    assert counts(session_factory,first["incident_id"]) == {"messages":1,"events":1,"jobs":1}


@pytest.mark.ac3
@pytest.mark.ac5
def test_receipt_replays_exact_body_after_state_change_and_rejects_key_reuse(client, login, demo_ids, auth_headers, session_factory):
    login()
    first = post_report(client, demo_ids, auth_headers, key="stable")
    ident = first.json()["data"]["incident_id"]
    with session_factory.begin() as tx:
        tx.get(Incident, ident).status = "IN_PROGRESS"
        tx.get(Incident, ident).version = 5
    again = post_report(client, demo_ids, auth_headers, key="stable")
    assert again.json() == first.json()
    assert again.headers["Idempotent-Replayed"] == "true"
    changed = client.post("/api/v1/incidents", json={"equipment_id":demo_ids["equipment"],"text":"다른 원문"},
                          headers={**auth_headers,"Idempotency-Key":"stable"})
    assert changed.status_code == 409 and changed.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert counts(session_factory, ident) == {"messages":1,"events":1,"jobs":1}
    with session_factory() as tx:
        assert tx.get(Incident, ident).version == 5


@pytest.mark.ac4
@pytest.mark.ac5
def test_note_correction_preserves_original_and_increments_once(client, login, demo_ids, auth_headers, session_factory):
    login()
    first = post_report(client, demo_ids, auth_headers).json()["data"]
    ident = first["incident_id"]
    body = {"text":"정정한 새 원문", "expected_version":1, "correction_of":first["message_id"]}
    response = client.post(f"/api/v1/incidents/{ident}/messages", json=body, headers={**auth_headers,"Idempotency-Key":"correction"})
    assert response.status_code == 202 and response.json()["data"]["incident_version"] == 2
    replay = client.post(f"/api/v1/incidents/{ident}/messages", json=body, headers={**auth_headers,"Idempotency-Key":"correction"})
    assert replay.json() == response.json()
    detail = client.get(f"/api/v1/incidents/{ident}").json()["data"]
    assert detail["status"] == "OPEN" and detail["version"] == 2
    assert [m["text"] for m in detail["messages"]] == ["  CV-03 소음과 진동 제보 원문  ","정정한 새 원문"]
    assert detail["messages"][1]["kind"] == "CORRECTION"
    assert detail["messages"][1]["correction_of"] == first["message_id"]
    assert counts(session_factory, ident) == {"messages":2,"events":2,"jobs":2}


@pytest.mark.ac6
@pytest.mark.ac7
def test_verification_reopens_for_new_information_and_resolved_late_input_is_retained(client, login, demo_ids, auth_headers, session_factory):
    login()
    ident = post_report(client, demo_ids, auth_headers).json()["data"]["incident_id"]
    with session_factory.begin() as tx:
        tx.get(Incident, ident).status = "PENDING_VERIFICATION"
    response = client.post(f"/api/v1/incidents/{ident}/messages", json={"text":"추가 정보","expected_version":1},
                          headers={**auth_headers,"Idempotency-Key":"new-information"})
    assert response.status_code == 202 and response.json()["data"]["incident_status"] == "INVESTIGATING"
    with session_factory.begin() as tx:
        incident = tx.get(Incident, ident)
        assert not incident.review_required
        incident.status = "RESOLVED"
        incident.version = 3
        tx.add(ResolutionCase(incident_id=ident, site_id=demo_ids["site"], equipment_id=demo_ids["equipment"],
            title="이미 해결됨", resolved_version=3, snapshot_json={"preserved":"immutable"}))
    before = counts(session_factory, ident)
    late = {"text":"해결 후 늦은 기록", "expected_version":2}
    first = client.post(f"/api/v1/incidents/{ident}/messages", json=late, headers={**auth_headers,"Idempotency-Key":"late"})
    second = client.post(f"/api/v1/incidents/{ident}/messages", json=late, headers={**auth_headers,"Idempotency-Key":"late"})
    assert first.status_code == 409 and first.json()["error"]["code"] == "INCIDENT_RESOLVED"
    assert second.json() == first.json() and second.headers["Idempotent-Replayed"] == "true"
    after = counts(session_factory, ident)
    assert after == {**before,"events":before["events"]+1}
    with session_factory() as tx:
        assert tx.get(Incident, ident).version == 3
        event = tx.scalar(select(Event).where(Event.incident_id == ident, Event.type == "rejected_input"))
        assert event.payload["input"]["text"] == late["text"]
        assert tx.scalar(select(ResolutionCase).where(ResolutionCase.incident_id == ident)).snapshot_json == {"preserved":"immutable"}


@pytest.mark.ac8
def test_list_filters_real_owner_target_assignee_and_cursor(client, login, demo_ids, auth_headers, session_factory):
    login()
    identifiers = [post_report(client,demo_ids,auth_headers,text=f"사건 {n}").json()["data"]["incident_id"] for n in range(3)]
    add_question(session_factory, identifiers[0], demo_ids["reporter"])
    with session_factory.begin() as tx:
        tx.add(Action(incident_id=identifiers[1], assignee_id=demo_ids["reporter"], scope="합성 계약 입력", status="PROPOSED"))
        tx.get(Incident, identifiers[2]).status = "RESOLVED"
    mine = client.get("/api/v1/incidents?scope=mine").json()["data"]["items"]
    assert {x["id"] for x in mine} == set(identifiers[:2])
    page = client.get("/api/v1/incidents?limit=1").json()["data"]
    assert len(page["items"]) == 1 and page["next_cursor"]
    next_page = client.get("/api/v1/incidents", params={"limit":1,"cursor":page["next_cursor"]}).json()["data"]
    assert next_page["items"][0]["id"] != page["items"][0]["id"]
    assert next_page["next_cursor"] is None
    assert client.get("/api/v1/incidents?status=RESOLVED").json()["data"]["items"][0]["id"] == identifiers[2]
    assert client.get("/api/v1/incidents?limit=101").status_code == 422


@pytest.mark.ac9
def test_evidence_scope_job_diagnostics_and_handover_projection(client, login, demo_ids, auth_headers, session_factory):
    login()
    data = post_report(client,demo_ids,auth_headers).json()["data"]
    with session_factory.begin() as tx:
        run = AgentRun(job_id=data["job_id"],attempt=1,trigger_event_id="fixture",status="FAILED",mode="fake",steps_json=[{"tool":"test_tool"}],metadata_json={"fixture":True})
        tx.add(run)
        evidence = Evidence(id=str(uuid4()),site_id=demo_ids["site"],incident_id=data["incident_id"],source_type="message",
            source_id=data["message_id"],excerpt="원문 발췌",content_hash="a"*64)
        tx.add(evidence)
        evidence_id = evidence.id
        handover = Handover(id=str(uuid4()),site_id=demo_ids["site"],from_shift_occurrence_id=demo_ids["outgoing_shift"],
            to_shift_occurrence_id=demo_ids["incoming_shift"],receiver_id=demo_ids["incoming_supervisor"],created_by=demo_ids["outgoing_supervisor"])
        tx.add(handover); tx.flush()
        item = HandoverItem(id=str(uuid4()),handover_id=handover.id,incident_id=data["incident_id"],latest_revision=1)
        tx.add(item); tx.flush()
        tx.add(HandoverRevision(item_id=item.id,revision=1,snapshot_version=1,snapshot_json={"private":"snapshot"},snapshot_token="token"))
        tx.add(Event(site_id=demo_ids["site"],incident_id=data["incident_id"],type="handover_acknowledged",
            payload={"snapshot_token":"private-event-token"},related_ids={"other_incident_id":"private-other-incident"}))
    public = client.get(f"/api/v1/incidents/{data['incident_id']}").json()["data"]
    assert public["handover"] is None and "run_summary" not in public["latest_job"]
    assert "private-event-token" not in str(public) and "private-other-incident" not in str(public)
    assert client.get(f"/api/v1/evidence/{evidence_id}").json()["data"]["excerpt"] == "원문 발췌"
    login("outgoing_supervisor")
    private = client.get(f"/api/v1/incidents/{data['incident_id']}").json()["data"]
    assert private["handover"]["revision"] == 1 and "snapshot_token" not in private["handover"]
    assert "run_summary" in private["latest_job"]
    with session_factory.begin() as tx:
        tx.get(Incident,data["incident_id"]).owner_id = demo_ids["incoming_supervisor"]
    former = client.get(f"/api/v1/jobs/{data['job_id']}").json()["data"]
    assert "run_summary" not in former
    with session_factory.begin() as tx:
        tx.get(Evidence,evidence_id).site_id = str(uuid4())
    assert client.get(f"/api/v1/evidence/{evidence_id}").status_code == 404


@pytest.mark.ac21
@pytest.mark.ac22
def test_only_target_answers_once_and_replay_keeps_request_job(client, login, demo_ids, auth_headers, session_factory):
    login()
    ident = post_report(client,demo_ids,auth_headers).json()["data"]["incident_id"]
    qid = add_question(session_factory,ident,demo_ids["maintainer"])
    body = {"text":"외관만 확인했습니다.","expected_version":1,"reply_to_request_id":qid}
    path = f"/api/v1/incidents/{ident}/messages"
    for role in ("reporter","outgoing_supervisor","incoming_supervisor"):
        login(role)
        response = client.post(path,json=body,headers={**auth_headers,"Idempotency-Key":role})
        assert response.status_code == 403
    login("maintainer")
    first = client.post(path,json=body,headers={**auth_headers,"Idempotency-Key":"answer"})
    assert first.status_code == 202
    replay = client.post(path,json=body,headers={**auth_headers,"Idempotency-Key":"answer"})
    assert replay.json() == first.json()
    assert first.json()["data"]["request_id"] == qid and first.json()["data"]["request_version"] == 2
    with session_factory() as tx:
        question = tx.get(Request,qid)
        assert question.status == "ANSWERED" and question.target_user_id == demo_ids["maintainer"] and question.is_required
        assert question.response_message_id == first.json()["data"]["message_id"]
        assert tx.get(Incident,ident).version == 2
    assert counts(session_factory,ident) == {"messages":2,"events":2,"jobs":2}
    closed = client.post(path,json={**body,"expected_version":2},headers={**auth_headers,"Idempotency-Key":"new-answer"})
    assert closed.status_code == 409 and closed.json()["error"]["code"] == "REQUEST_CLOSED"


@pytest.mark.ac29
@pytest.mark.ac3
def test_retry_uses_current_owner_same_job_and_receipt(client, login, demo_ids, auth_headers, session_factory):
    login()
    data = post_report(client,demo_ids,auth_headers).json()["data"]
    with session_factory.begin() as tx:
        job = tx.get(Job,data["job_id"])
        job.status = "FAILED"; job.attempt = 1; job.last_error = {"code":"TIMEOUT","retryable":True}
    path = f"/api/v1/jobs/{data['job_id']}/retry"
    assert client.post(path,json={},headers={**auth_headers,"Idempotency-Key":"worker"}).status_code == 403
    login("outgoing_supervisor")
    response = client.post(path,json={},headers={**auth_headers,"Idempotency-Key":"retry"})
    assert response.status_code == 202 and response.json()["data"]["id"] == data["job_id"]
    assert response.json()["data"]["status"] == "QUEUED"
    with session_factory.begin() as tx:
        assert tx.get(Incident,data["incident_id"]).version == 1
        tx.get(Incident,data["incident_id"]).owner_id = demo_ids["incoming_supervisor"]
        tx.get(Job,data["job_id"]).status = "RUNNING"
    replay = client.post(path,json={},headers={**auth_headers,"Idempotency-Key":"retry"})
    assert replay.json() == response.json() and replay.headers["Idempotent-Replayed"] == "true"
    assert client.post(path,json={},headers={**auth_headers,"Idempotency-Key":"new-key"}).status_code == 403
    login("incoming_supervisor")
    assert client.post(path,json={},headers={**auth_headers,"Idempotency-Key":"running"}).status_code == 409
    with session_factory.begin() as tx:
        tx.get(Job,data["job_id"]).status = "SUCCEEDED"
    assert client.post(path,json={},headers={**auth_headers,"Idempotency-Key":"success"}).status_code == 200


@pytest.mark.ac29
def test_retry_refuses_exhausted_reviewed_resolved_or_nonretryable(client,login,demo_ids,auth_headers,session_factory):
    login()
    data = post_report(client,demo_ids,auth_headers).json()["data"]
    login("outgoing_supervisor")
    for number,(attempt,retryable,review,status) in enumerate([(3,True,False,"OPEN"),(1,False,False,"OPEN"),(1,True,True,"INVESTIGATING"),(1,True,False,"RESOLVED")]):
        with session_factory.begin() as tx:
            job = tx.get(Job,data["job_id"]); job.status = "FAILED"; job.attempt = attempt; job.last_error = {"retryable":retryable}
            incident = tx.get(Incident,data["incident_id"]); incident.review_required = review; incident.status = status
        response = client.post(f"/api/v1/jobs/{data['job_id']}/retry",json={},headers={**auth_headers,"Idempotency-Key":f"blocked-{number}"})
        assert response.status_code == 409
        with session_factory() as tx:
            assert tx.get(Job,data["job_id"]).status == "FAILED"
