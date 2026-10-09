from copy import deepcopy
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.features.actions.commands import ApprovalCommand, CompletionCommand, StartCommand
from app.features.actions.errors import ActionError
from app.features.actions.models import MessageView, RequestView
from app.features.actions.service import ActionApplication
from app.features.resolution.readiness import evaluate_resolution_readiness
from support import INCOMING, MAINTAINER, NOW, OWNER, REPORTER, uid


def execute(store, command_type, actor=OWNER, key=None, **extra):
    command = command_type(expected_version=store.context.actions[0].version,
                           expected_incident_version=store.context.incident.version, **extra)
    return ActionApplication(store.transaction, lambda: NOW).execute(
        actor, uid(501), key or str(uuid4()), command, {"request_id": "test-request"})


def approve(store):
    return execute(store, ApprovalCommand, decision="APPROVE", reason="내용 확인")


def start(store):
    approve(store)
    return execute(store, StartCommand, MAINTAINER)


def complete(store):
    start(store)
    return execute(store, CompletionCommand, MAINTAINER, result="  수행 결과 원문\n그대로 보존  ")


def test_approve_start_complete_preserves_result_and_bumps_once(store):
    response = complete(store)
    c = store.context
    assert response.status == 200
    assert (c.actions[0].status, c.actions[0].version) == ("COMPLETED", 4)
    assert (c.incident.status, c.incident.version) == ("PENDING_VERIFICATION", 8)
    assert len(c.approvals) == len(c.messages) == 1
    assert c.messages[0].text == "  수행 결과 원문\n그대로 보존  "
    assert c.messages[0].author_id == MAINTAINER.user_id
    assert c.evidence[-1].source_type == "completion_report"
    assert len(store.events) == len(store.receipts) == 3
    assert evaluate_resolution_readiness(c).verification_ready


@pytest.mark.parametrize("command_type,actor,extra,expected", [
    (StartCommand, MAINTAINER, {}, 409),
    (ApprovalCommand, REPORTER, {"decision": "APPROVE", "reason": "확인"}, 403),
    (ApprovalCommand, INCOMING, {"decision": "APPROVE", "reason": "확인"}, 403),
    (CompletionCommand, MAINTAINER, {"result": "승인 전 완료"}, 409),
    (StartCommand, OWNER, {}, 403),
])
def test_invalid_actor_or_order_has_no_business_effect(store, command_type, actor, extra, expected):
    before = store.context
    response = execute(store, command_type, actor, **extra)
    assert response.status == expected
    assert store.context == before and not store.events


@pytest.mark.parametrize("target", ["action", "incident"])
def test_both_versions_checked(store, target):
    command = ApprovalCommand(expected_version=9 if target == "action" else 1,
                              expected_incident_version=9 if target == "incident" else 5,
                              decision="APPROVE", reason="확인")
    response = ActionApplication(store.transaction).execute(OWNER, uid(501), "v", command, {})
    assert response.status == 409
    assert response.body["error"]["details"]["target"] == target
    assert not store.context.approvals


def test_replay_precedes_new_owner_version_and_resolved_state(store):
    command = ApprovalCommand(expected_version=1, expected_incident_version=5, decision="APPROVE", reason="확인")
    app = ActionApplication(store.transaction)
    first = app.execute(OWNER, uid(501), "stable", command, {"request_id": "first"})
    store.context = store.context.model_copy(update={"incident": store.context.incident.model_copy(
        update={"owner_id": INCOMING.user_id, "version": 20, "status": "RESOLVED"})})
    second = app.execute(OWNER, uid(501), "stable", command, {"request_id": "second"})
    assert second.replayed and second.body == first.body
    assert store.context.incident.version == 20 and len(store.context.approvals) == 1


def test_same_key_different_body_and_route_conflict(store):
    execute(store, ApprovalCommand, key="same", decision="APPROVE", reason="확인")
    with pytest.raises(ActionError, match="다른 입력"):
        execute(store, ApprovalCommand, key="same", decision="REJECT", reason="다른 입력")
    with pytest.raises(ActionError):
        execute(store, StartCommand, OWNER, key="same")


def test_receipts_scoped_by_actor_and_site(store):
    approve(store)
    response = execute(store, StartCommand, OWNER, key="same")
    assert response.status == 403
    assert execute(store, StartCommand, MAINTAINER, key="same").status == 200
    other_site = MAINTAINER.model_copy(update={"site_id": uid(2)})
    with pytest.raises(ActionError) as error:
        execute(store, CompletionCommand, other_site, key="same", result="결과")
    assert error.value.status == 404 and not store.context.messages


def test_reject_blocks_progress_and_readiness(store):
    execute(store, ApprovalCommand, decision="REJECT", reason="범위 불명확")
    assert store.context.actions[0].status == "REJECTED"
    assert store.context.incident.status == "INVESTIGATING"
    assert store.context.incident.review_reason == "범위 불명확"
    response = execute(store, StartCommand, MAINTAINER)
    assert response.body["error"]["code"] == "REVIEW_REQUIRED"
    assert not evaluate_resolution_readiness(store.context).verification_ready


def test_owner_can_reject_a_proposal_even_if_its_evidence_is_no_longer_usable(store):
    store.context = store.context.model_copy(update={"evidence": ()})
    response = execute(store, ApprovalCommand, decision="REJECT", reason="근거 재검토 필요")
    assert response.status == 200 and store.context.actions[0].status == "REJECTED"


@pytest.mark.parametrize("changed", ["scope", "assignee_id", "due_at", "completion_criteria", "evidence_refs", "title"])
def test_approval_hash_detects_content_changes(store, changed):
    from datetime import timedelta
    approve(store)
    replacements = {"scope": "변조", "assignee_id": OWNER.user_id, "due_at": NOW + timedelta(days=1),
                    "completion_criteria": ("변조",), "evidence_refs": (uid(999),), "title": "변조"}
    action = store.context.actions[0].model_copy(update={changed: replacements[changed]})
    store.context = store.context.model_copy(update={"actions": (action,)})
    actor = OWNER if changed == "assignee_id" else MAINTAINER
    response = execute(store, StartCommand, actor)
    assert response.status == 409 and store.context.actions[0].status == "APPROVED"


def test_completion_checks_hash_again(store):
    start(store)
    action = store.context.actions[0].model_copy(update={"scope": "변조"})
    store.context = store.context.model_copy(update={"actions": (action,)})
    assert execute(store, CompletionCommand, MAINTAINER, result="결과").status == 409
    assert not store.context.messages


def test_handover_changes_owner_but_not_assignee(store):
    store.context = store.context.model_copy(update={"incident": store.context.incident.model_copy(
        update={"owner_id": INCOMING.user_id, "version": 6})})
    assert approve(store).status == 403
    assert execute(store, ApprovalCommand, INCOMING, decision="APPROVE", reason="인수 후 확인").status == 200
    assert execute(store, StartCommand, MAINTAINER).status == 200
    assert execute(store, CompletionCommand, MAINTAINER, result="결과").status == 200
    assert store.context.actions[0].assignee_id == MAINTAINER.user_id


@pytest.mark.parametrize("failure", ["after_write", "receipt"])
def test_uow_rolls_back_result_and_receipt_on_failure(store, failure):
    start(store)
    before = deepcopy((store.context, store.events, store.receipts))
    store.failure = failure
    with pytest.raises(RuntimeError):
        execute(store, CompletionCommand, MAINTAINER, key="retry", result="보존할 결과")
    assert (store.context, store.events, store.receipts) == before
    store.failure = None
    assert execute(store, CompletionCommand, MAINTAINER, key="retry", result="보존할 결과").status == 200


def test_readiness_exception_rolls_back_and_does_not_mask_failure(store, monkeypatch):
    start(store)
    before = deepcopy(store.context)
    def fail(_):
        raise RuntimeError("readiness failure")
    monkeypatch.setattr("app.features.actions.domain.evaluate_resolution_readiness", fail)
    with pytest.raises(RuntimeError):
        execute(store, CompletionCommand, MAINTAINER, result="결과")
    assert store.context == before


def test_completion_with_question_pending_saves_result_without_status_transition(store):
    start(store)
    question = RequestView(id=uid(901), incident_id=uid(401), target_user_id=MAINTAINER.user_id,
                           is_required=True, status="OPEN")
    store.context = store.context.model_copy(update={"requests": (question,)})
    result = execute(store, CompletionCommand, MAINTAINER, result="수행 결과")
    assert result.status == 200 and not result.body["data"]["verification_ready"]
    assert result.body["data"]["unmet_requirements"] == ["REQUIRED_QUESTION_UNANSWERED"]
    assert store.context.incident.status == "IN_PROGRESS"
    assert store.context.actions[0].status == "COMPLETED"


def test_late_authorized_result_is_preserved_once_without_changing_incident(store):
    start(store)
    store.context = store.context.model_copy(update={"incident": store.context.incident.model_copy(
        update={"status": "RESOLVED", "version": 10})})
    before = store.context
    command = CompletionCommand(expected_version=3, expected_incident_version=7, result="늦은 결과")
    app = ActionApplication(store.transaction)
    first = app.execute(MAINTAINER, uid(501), "late", command, {})
    second = app.execute(MAINTAINER, uid(501), "late", command, {})
    assert first.status == second.status == 409 and second.replayed
    assert store.context == before
    assert [e.type for e in store.events].count("rejected_input") == 1
    assert store.events[-1].payload["input"]["result"] == "늦은 결과"


@pytest.mark.parametrize("extra", [{"result": " "}, {"result": "\n"},
                                  {"result": "정상", "actor_id": str(uid(203))}])
def test_invalid_client_input(extra):
    with pytest.raises(ValidationError):
        CompletionCommand(expected_version=1, expected_incident_version=1, **extra)


@pytest.mark.parametrize("refs", [(uid(999),), (uid(801), uid(999))])
def test_invalid_additional_evidence_aborts_completion(store, refs):
    start(store)
    before = store.context
    response = execute(store, CompletionCommand, MAINTAINER, result="결과", evidence_refs=refs)
    assert response.status == 422 and store.context == before
