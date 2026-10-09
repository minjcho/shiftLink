"""F1 contract tests: real PostgreSQL, explicit fake model/feature boundaries."""
from __future__ import annotations

import json
import time
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.agent.context import RunIdentity
from app.agent.finalizer import DecisionRejected, finalize
from app.agent.jobs import (LostLease, claim_job, finish_failure, prepare_run, recover_exhausted)
from app.agent.runner import (AgentExecution, ModelReply, OpenAIResponsesTransport, ReplayTransport,
                              RunLimits, ScriptedTransport, run_agent)
from app.agent.schemas import FinalDecision, final_format, tool_definitions
from app.agent.tools import ToolExecutor
from app.agent.worker import run_once, runtime_metadata
from app.core.models import (Action, ActionDraft, AgentRun, Document, DocumentChunk, EquipmentLog,
                             Event, Evidence, Incident, Job, Message, Request, ResolutionCase, utcnow)
from app.core.ports import FeaturePorts
from app.core.transactions import bump_incident, enqueue_job, new_event


def create_job(factory, ids, *, status="OPEN", review_required=False):
    with factory.begin() as tx:
        incident = Incident(id=str(uuid4()), display_id=f"TEST-{uuid4()}", site_id=ids["site"],
                            equipment_id=ids["equipment"], reporter_id=ids["reporter"],
                            origin_shift_occurrence_id=ids["outgoing_shift"],
                            owner_shift_occurrence_id=ids["outgoing_shift"],
                            owner_id=ids["outgoing_supervisor"], status=status, review_required=review_required)
        tx.add(incident)
        tx.flush()
        tx.add(Message(site_id=incident.site_id, incident_id=incident.id, author_id=ids["reporter"],
                       kind="REPORT", text="CV-03의 기록 범위를 확인해 주세요."))
        event = new_event(tx, incident, "REPORT_CREATED")
        job = enqueue_job(tx, incident, event)
        return incident.id, job.id


def prepared(factory, ids, *, status="OPEN", review_required=False):
    create_job(factory, ids, status=status, review_required=review_required)
    identity = claim_job(factory, mode="fake", model_id="scripted", metadata={
        "app_sha": "a" * 40, "dirty": True, "dataset_version": "0.3.0",
        "settings_id": "test-settings", "run_group_id": "test-group",
        "OPENAI_API_KEY": "must-never-be-persisted", "reasoning": "private-thought"})
    context = prepare_run(factory, identity, FeaturePorts())
    return context


def decision(context, kind="BLOCKED", **overrides):
    value = {"facts": [], "hypotheses": [], "missing_information": [], "decision": kind,
             "questions": [], "selected_draft_id": None, "existing_request_ids": [],
             "existing_action_ids": [], "source_refs": [], "reason": "Test-only deterministic decision."}
    if kind == "ASK_USER":
        value["questions"] = [{"question": "어떤 범위를 확인했습니까?", "purpose_code": "VERIFY_SCOPE",
                                "target_user_id": sorted(context.target_user_ids)[0] if context else str(uuid4()),
                                "source_refs": [context.payload["messages"][0]["source_ref"] if context else str(uuid4())]}]
    value.update(overrides)
    return value


def execution(dto):
    return AgentExecution(final=FinalDecision.model_validate(dto), mode="fake", model_id="scripted-test")


def call(name, arguments, call_id="tool-1"):
    return ModelReply(output=[{"type": "function_call", "name": name,
                               "arguments": json.dumps(arguments), "call_id": call_id}])


@pytest.mark.ac10
def test_prepare_commits_initial_transition_and_rebuilds_from_database(session_factory, demo_ids):
    context = prepared(session_factory, demo_ids)
    assert context.identity.input_version == 2
    assert context.payload["incident"]["status"] == "INVESTIGATING"
    assert context.payload["allowed_question_target_ids"] == [demo_ids["maintainer"]]
    with session_factory() as tx:
        run = tx.get(AgentRun, context.identity.run_id)
        assert run.input_version == tx.get(Incident, context.identity.incident_id).version
        assert tx.scalar(select(func.count(Event.id))) == 2
    # Existing business progress is not reset by a new investigation.
    other = prepared(session_factory, demo_ids, status="IN_PROGRESS")
    assert other.payload["incident"]["status"] == "IN_PROGRESS"
    assert other.identity.input_version == 1


@pytest.mark.ac11
@pytest.mark.ac12
@pytest.mark.ac13
@pytest.mark.ac14
def test_tools_real_search_scope_empty_error_and_immutable_sources(session_factory, demo_ids):
    context = prepared(session_factory, demo_ids)
    tools = ToolExecutor(session_factory, context)
    query = json.dumps({"equipment_id": demo_ids["equipment"], "query": "점검"})
    result = tools("search_documents", query)
    assert result["outcome"] == "OK"
    assert 0 < len(result["data"]["items"]) <= 5
    assert all(i["document_approval"] == "approved" and len(i["excerpt"]) <= 2000 for i in result["data"]["items"])
    source = result["data"]["items"][0]
    with session_factory.begin() as tx:
        document = tx.get(Document, source["document_id"])
        document.approval_status = "draft"
        chunk = tx.scalar(select(DocumentChunk).where(DocumentChunk.document_id == document.id).limit(1))
        chunk.text = "Changed source text"
    later = tools("search_documents", query)
    assert source["document_id"] not in [i["document_id"] for i in later["data"]["items"]]
    with session_factory() as tx:
        assert tx.get(Evidence, source["id"]).excerpt == source["excerpt"]
    empty = tools("search_documents", json.dumps({"equipment_id": demo_ids["equipment"], "query": "unfindable-xyz987"}))
    assert empty["outcome"] == "EMPTY" and empty["error"] is None
    wrong = tools("get_equipment_context", json.dumps({"equipment_id": demo_ids["comparison_equipment"]}))
    assert wrong["outcome"] == "ERROR" and wrong["data"] is None
    forbidden = tools("resolve_incident", "{}")
    assert forbidden["error"]["code"] == "TOOL_NOT_ALLOWED"
    failure = ToolExecutor(session_factory, context, injected_errors={"get_equipment_context": {
        "code": "SOURCE_UNAVAILABLE", "message": "Source unavailable", "retryable": True}})
    assert failure("get_equipment_context", json.dumps({"equipment_id": demo_ids["equipment"]}))["outcome"] == "ERROR"


@pytest.mark.ac11
@pytest.mark.ac14
def test_past_case_is_explicit_comparison_and_context_contains_no_oracle(session_factory, demo_ids):
    context = prepared(session_factory, demo_ids)
    tools = ToolExecutor(session_factory, context)
    result = tools("search_similar_incidents", json.dumps({"equipment_id": demo_ids["equipment"], "query": "기록"}))
    assert result["outcome"] == "OK"
    assert all(item["comparison_only"] for item in result["data"]["items"])
    assert all(item["equipment_id"] == demo_ids["comparison_equipment"] for item in result["data"]["items"])
    payload = json.dumps(context.payload, ensure_ascii=False)
    assert "L1a" not in payload and "expected_decision" not in payload and "oracle" not in payload


@pytest.mark.ac15
@pytest.mark.ac16
def test_candidate_only_does_not_create_action_and_rejects_unseen_sources(session_factory, demo_ids):
    context = prepared(session_factory, demo_ids)
    tools = ToolExecutor(session_factory, context)
    args = {"scope": "기록 확인", "completion_criteria": ["확인 범위 제출"], "source_refs": sorted(context.source_ids)}
    result = tools("propose_action", json.dumps(args))
    assert result["outcome"] == "OK"
    invalid = tools("propose_action", json.dumps({**args, "source_refs": [str(uuid4())]}))
    assert invalid["error"]["code"] == "EVIDENCE_INVALID"
    forbidden = tools("propose_action", json.dumps({**args, "assignee_id": demo_ids["reporter"]}))
    assert forbidden["error"]["code"] == "INVALID_TOOL_ARGUMENTS"
    with session_factory() as tx:
        assert tx.scalar(select(func.count(ActionDraft.id))) == 1
        assert tx.scalar(select(func.count(Action.id))) == 0
        assert tx.get(Incident, context.identity.incident_id).version == context.identity.input_version


@pytest.mark.ac16
@pytest.mark.ac19
@pytest.mark.parametrize("change", ["nested_fact", "nested_question", "bad_target", "other_draft", "unknown_action"])
def test_all_nested_ids_and_targets_validated_before_effects(session_factory, demo_ids, change):
    context = prepared(session_factory, demo_ids)
    dto = decision(context, "ASK_USER")
    if change == "nested_fact":
        dto["facts"] = [{"text": "Forged fact", "kind": "RECORD", "source_refs": [str(uuid4())]}]
    elif change == "nested_question":
        dto["questions"][0]["source_refs"] = [str(uuid4())]
    elif change == "bad_target":
        dto["questions"][0]["target_user_id"] = demo_ids["outgoing_supervisor"]
    elif change == "other_draft":
        dto = decision(context, "PROPOSE_ACTION", selected_draft_id=str(uuid4()))
    else:
        dto["existing_action_ids"] = [str(uuid4())]
    with pytest.raises(DecisionRejected):
        finalize(session_factory, context.identity, execution(dto), FeaturePorts())
    with session_factory() as tx:
        assert tx.scalar(select(func.count(Request.id))) == 0
        assert tx.scalar(select(func.count(Action.id))) == 0
        assert tx.get(Incident, context.identity.incident_id).analysis is None


@pytest.mark.ac16
@pytest.mark.ac17
@pytest.mark.parametrize("kind,overrides", [
    ("ASK_USER", {"questions": []}), ("PROPOSE_ACTION", {"selected_draft_id": None}),
    ("WAIT_EXISTING", {}), ("BLOCKED", {"selected_draft_id": str(uuid4())}),
    ("REQUEST_VERIFICATION", {"extra": True}),
])
def test_strict_final_branch_schema(kind, overrides):
    with pytest.raises(ValidationError):
        FinalDecision.model_validate(decision(None, kind, **overrides))


@pytest.mark.ac17
def test_responses_protocol_preserves_required_outputs_and_matching_call_id():
    first = call("search_documents", {"equipment_id": str(uuid4()), "query": "기록"})
    first.output.insert(0, {"type": "reasoning", "id": "transient-reasoning", "summary": []})
    transport = ScriptedTransport([first, ModelReply(output=[], text=json.dumps(decision(None)))])
    result = run_agent(context={"incident": {}}, transport=transport,
                       execute_tool=lambda *_: {"outcome": "EMPTY", "data": {"items": []},
                                                "source_refs": [], "partial": False, "error": None})
    assert result.final is not None
    assert transport.requests[1]["inputs"][2]["id"] == "transient-reasoning"
    output = transport.requests[1]["inputs"][-1]
    assert output["type"] == "function_call_output" and output["call_id"] == "tool-1"
    assert "transient-reasoning" not in json.dumps(result.steps)
    for tool in tool_definitions():
        assert tool["strict"] is True
        assert tool["parameters"]["additionalProperties"] is False
        assert set(tool["parameters"]["required"]) == set(tool["parameters"]["properties"])
    assert "selected_draft_id" in final_format()["schema"]["required"]


@pytest.mark.ac17
def test_live_adapter_sets_protocol_safety_options_without_network():
    class Client:
        def with_options(self, **options):
            self.options = options
            return self
        @property
        def responses(self):
            return self
        def create(self, **kwargs):
            self.kwargs = kwargs
            return type("Response", (), {"output": [], "output_text": "{}", "status": "completed",
                                          "usage": None, "model": "test-model"})()
    client = Client()
    adapter = OpenAIResponsesTransport(client=client, model_id="test-model")
    adapter.respond(inputs=[], tools=tool_definitions(), output_format=final_format(), timeout=2, max_output_tokens=2000)
    assert client.options == {"max_retries": 0}
    assert client.kwargs["store"] is False and client.kwargs["parallel_tool_calls"] is False
    assert client.kwargs["text"]["format"]["type"] == "json_schema"


@pytest.mark.ac18
@pytest.mark.parametrize("reply,code", [
    (TimeoutError("secret"), "TIMEOUT"), (RuntimeError("API key secret"), "API_ERROR"),
    (ModelReply(output=[], status="incomplete"), "INCOMPLETE"),
    (ModelReply(output=[{"type": "message", "content": [{"type": "refusal", "refusal": "No"}]}]), "REFUSAL"),
    (ModelReply(output=[], text="bad-json"), "SCHEMA_ERROR"),
])
def test_model_failure_categories_never_become_blocked(reply, code):
    result = run_agent(context={}, transport=ScriptedTransport([reply]), execute_tool=lambda *_: {})
    assert result.error["code"] == code and result.final is None
    assert "secret" not in json.dumps(result.error)


@pytest.mark.ac18
def test_budget_and_late_results_stop_before_more_work():
    calls = [call("get_equipment_context", {"equipment_id": str(uuid4())}, f"c{i}") for i in range(3)]
    invoked = []
    result = run_agent(context={}, transport=ScriptedTransport(calls), execute_tool=lambda *args: invoked.append(args) or {},
                       limits=RunLimits(max_tool_calls=1))
    assert result.error["code"] == "BUDGET_EXCEEDED" and len(invoked) == 1
    result = run_agent(context={}, transport=ScriptedTransport(calls), execute_tool=lambda *_: {},
                       limits=RunLimits(max_model_calls=1))
    assert result.error["code"] == "BUDGET_EXCEEDED" and result.model_calls == 1
    instant = [0]
    def late(_):
        instant[0] = 61
        return ModelReply(output=[], text=json.dumps(decision(None)))
    result = run_agent(context={}, transport=ScriptedTransport([late]), execute_tool=lambda *_: {}, clock=lambda: instant[0])
    assert result.error["code"] == "TIMEOUT" and result.final is None


@pytest.mark.ac19
@pytest.mark.ac20
def test_questions_are_required_persistent_deduplicated_and_wait_ends_run(session_factory, demo_ids):
    context = prepared(session_factory, demo_ids)
    result = finalize(session_factory, context.identity, execution(decision(context, "ASK_USER")), FeaturePorts())
    assert result["status"] == "WAITING_INPUT"
    with session_factory() as tx:
        question = tx.get(Request, result["request_ids"][0])
        assert question.is_required and question.status == "OPEN"
        assert tx.get(Job, context.identity.job_id).status == "SUCCEEDED"
        assert tx.get(AgentRun, context.identity.run_id).status == "WAITING_INPUT"
    assert claim_job(session_factory, mode="fake") is None
    with session_factory.begin() as tx:
        incident = tx.get(Incident, context.identity.incident_id)
        version = incident.version
        event = new_event(tx, incident, "EXPLICIT_TEST_TRIGGER")
        enqueue_job(tx, incident, event)
    second = prepare_run(session_factory, claim_job(session_factory, mode="fake"), FeaturePorts())
    replayed = finalize(session_factory, second.identity, execution(decision(second, "ASK_USER")), FeaturePorts())
    assert replayed["request_ids"] == result["request_ids"]
    with session_factory() as tx:
        assert tx.scalar(select(func.count(Request.id))) == 1
        assert tx.get(Incident, context.identity.incident_id).version == version


@pytest.mark.ac23
@pytest.mark.ac34
def test_f2_missing_or_failure_rolls_back_all_business_effects(session_factory, demo_ids):
    context = prepared(session_factory, demo_ids)
    tools = ToolExecutor(session_factory, context)
    draft = tools("propose_action", json.dumps({"scope": "범위 확인", "completion_criteria": ["기록 제출"],
                                                 "source_refs": sorted(context.source_ids)}))["data"]["draft_id"]
    dto = execution(decision(context, "PROPOSE_ACTION", selected_draft_id=draft))
    from app.core.errors import DomainError
    with pytest.raises(DomainError):
        finalize(session_factory, context.identity, dto, FeaturePorts())
    def broken(tx, **kwargs):
        tx.add(Action(incident_id=kwargs["incident_id"], scope="Test-only adapter partial write",
                      assignee_id=demo_ids["maintainer"]))
        tx.flush()
        raise RuntimeError("boundary failure")
    with pytest.raises(RuntimeError):
        finalize(session_factory, context.identity, dto, FeaturePorts(action_finalizer=broken))
    with session_factory() as tx:
        assert tx.scalar(select(func.count(Action.id))) == 0
        assert tx.get(Incident, context.identity.incident_id).version == context.identity.input_version
        assert tx.get(Incident, context.identity.incident_id).analysis is None
        assert tx.get(Job, context.identity.job_id).status == "RUNNING"


@pytest.mark.ac23
@pytest.mark.ac24
def test_explicit_f2_adapter_creates_once_and_existing_action_is_reused(session_factory, demo_ids):
    context = prepared(session_factory, demo_ids)
    draft = ToolExecutor(session_factory, context)("propose_action", json.dumps({
        "scope": "범위 확인", "completion_criteria": ["기록 제출"], "source_refs": sorted(context.source_ids)}))["data"]["draft_id"]
    def fake_f2(tx, **kwargs):
        proposal = tx.get(ActionDraft, kwargs["draft_id"])
        action = Action(incident_id=kwargs["incident_id"], scope=proposal.payload_json["scope"],
                        completion_criteria=proposal.payload_json["completion_criteria"],
                        evidence_refs=proposal.payload_json["source_refs"], trigger_event_id=kwargs["trigger_event_id"],
                        assignee_id=demo_ids["maintainer"], proposed_by_run_id=kwargs["run_id"])
        tx.add(action)
        tx.flush()
        return {"action_id": action.id, "created": True, "action_version": action.version}
    result = finalize(session_factory, context.identity, execution(decision(context, "PROPOSE_ACTION", selected_draft_id=draft)),
                      FeaturePorts(action_finalizer=fake_f2))
    with session_factory.begin() as tx:
        incident = tx.get(Incident, context.identity.incident_id)
        version = incident.version
        assert incident.status == "ACTION_REQUIRED"
        event = new_event(tx, incident, "TEST_REINVESTIGATION")
        enqueue_job(tx, incident, event)
    second = prepare_run(session_factory, claim_job(session_factory, mode="fake"), FeaturePorts())
    maintained = finalize(session_factory, second.identity, execution(decision(second, "WAIT_EXISTING",
                           existing_action_ids=result["action_ids"])), FeaturePorts())
    assert maintained["action_ids"] == result["action_ids"]
    with session_factory() as tx:
        assert tx.scalar(select(func.count(Action.id))) == 1
        assert tx.get(Incident, context.identity.incident_id).version == version


@pytest.mark.ac25
@pytest.mark.ac34
def test_readiness_and_review_required_cannot_be_bypassed(session_factory, demo_ids):
    context = prepared(session_factory, demo_ids)
    dto = execution(decision(context, "REQUEST_VERIFICATION"))
    with pytest.raises(DecisionRejected, match="readiness"):
        finalize(session_factory, context.identity, dto, FeaturePorts(readiness_evaluator=lambda *_args, **_kw: {"ready": False, "missing": ["ACTION_REQUIRED"]}))
    with session_factory.begin() as tx:
        incident = tx.get(Incident, context.identity.incident_id)
        incident.review_required = True
    with pytest.raises(DecisionRejected, match="human follow-up"):
        finalize(session_factory, context.identity, dto, FeaturePorts(readiness_evaluator=lambda *_args, **_kw: {"ready": True}))
    finalize(session_factory, context.identity, execution(decision(context)), FeaturePorts())
    with session_factory() as tx:
        incident = tx.get(Incident, context.identity.incident_id)
        assert incident.review_required and incident.status == "INVESTIGATING"


@pytest.mark.ac26
def test_new_business_version_supersedes_without_replacing_analysis_or_duplicating_job(session_factory, demo_ids):
    context = prepared(session_factory, demo_ids)
    with session_factory.begin() as tx:
        incident = tx.get(Incident, context.identity.incident_id)
        incident.analysis = {"reason": "newer-analysis"}
        event = new_event(tx, incident, "ACK_APPLIED")
        bump_incident(tx, incident, event, FeaturePorts())
        enqueue_job(tx, incident, event)
    result = finalize(session_factory, context.identity, execution(decision(context, "ASK_USER")), FeaturePorts())
    assert result["status"] == "SUPERSEDED"
    with session_factory() as tx:
        assert tx.get(Incident, context.identity.incident_id).analysis == {"reason": "newer-analysis"}
        assert tx.scalar(select(func.count(Request.id))) == 0
        assert tx.scalar(select(func.count(Job.id))) == 2


@pytest.mark.ac27
@pytest.mark.ac34
def test_expired_worker_cannot_finalize_fail_supersede_or_change_analysis(session_factory, demo_ids):
    old = prepared(session_factory, demo_ids)
    with session_factory.begin() as tx:
        tx.get(Job, old.identity.job_id).lease_expires_at = utcnow() - timedelta(seconds=1)
    current = prepare_run(session_factory, claim_job(session_factory, mode="fake"), FeaturePorts())
    finalize(session_factory, current.identity, execution(decision(current)), FeaturePorts())
    for dto in [decision(old), decision(old, "ASK_USER")]:
        with pytest.raises(LostLease):
            finalize(session_factory, old.identity, execution(dto), FeaturePorts())
    assert not finish_failure(session_factory, old.identity, {"code": "API_ERROR"})
    with session_factory() as tx:
        assert tx.get(Job, old.identity.job_id).status == "SUCCEEDED"
        assert tx.get(AgentRun, old.identity.run_id).error_json["code"] == "LEASE_EXPIRED"
        assert tx.get(Incident, old.identity.incident_id).analysis["run_id"] == current.identity.run_id
        assert tx.scalar(select(func.count(Request.id))) == 0


@pytest.mark.ac28
def test_last_attempt_expiry_is_recovered_without_another_claim_or_effect(session_factory, demo_ids):
    context = prepared(session_factory, demo_ids)
    with session_factory.begin() as tx:
        tx.get(Job, context.identity.job_id).lease_expires_at = utcnow() - timedelta(seconds=1)
    assert recover_exhausted(session_factory, max_attempts=1) == 1
    assert recover_exhausted(session_factory, max_attempts=1) == 0
    assert claim_job(session_factory, mode="fake", max_attempts=1) is None
    assert not finish_failure(session_factory, context.identity, {"code": "LATE_ERROR"})
    with session_factory() as tx:
        job, run = tx.get(Job, context.identity.job_id), tx.get(AgentRun, context.identity.run_id)
        assert job.status == run.status == "FAILED"
        assert job.last_error["code"] == "ATTEMPTS_EXHAUSTED" and job.lease_token is None
        assert tx.scalar(select(func.count(AgentRun.id))) == 1
        assert tx.get(Incident, context.identity.incident_id).analysis is None


@pytest.mark.ac12
@pytest.mark.ac18
@pytest.mark.ac32
def test_tool_error_reaches_model_and_valid_blocked_succeeds_with_private_data_omitted(session_factory, demo_ids):
    context = prepared(session_factory, demo_ids)
    tool = ToolExecutor(session_factory, context, injected_errors={"get_equipment_context": {
        "code": "SOURCE_UNAVAILABLE", "message": "No source connection", "retryable": True}})
    def finish(kwargs):
        assert json.loads(kwargs["inputs"][-1]["output"])["outcome"] == "ERROR"
        return ModelReply(output=[], text=json.dumps(decision(context)), usage=None)
    run_result = run_agent(context=context.payload, transport=ScriptedTransport([
        call("get_equipment_context", {"equipment_id": demo_ids["equipment"]}), finish]), execute_tool=tool)
    result = finalize(session_factory, context.identity, run_result, FeaturePorts())
    assert result["status"] == "SUCCEEDED"
    with session_factory() as tx:
        run = tx.get(AgentRun, context.identity.run_id)
        assert run.usage_json is None
        assert run.steps_json[0]["arguments"]["equipment_id"] == demo_ids["equipment"]
        assert run.steps_json[0]["result"]["outcome"] == "ERROR"
        assert run.metadata_json["app_sha"] == "a" * 40 and run.metadata_json["api_calls"] == 0
        assert "must-never-be-persisted" not in json.dumps(run.metadata_json)
        assert "private-thought" not in json.dumps(run.metadata_json)


@pytest.mark.ac32
def test_replay_records_provenance_and_has_no_new_api_calls(session_factory, settings, demo_ids):
    create_job(session_factory, demo_ids)
    replay = ReplayTransport([ModelReply(output=[], text=json.dumps(decision(None)))],
                             original_run_id=str(uuid4()), original_commit="b" * 40, recorded_at="2026-10-09T03:00:00Z")
    result = run_once(session_factory, settings, FeaturePorts(), replay)
    assert result["status"] == "SUCCEEDED"
    with session_factory() as tx:
        run = tx.get(AgentRun, result["run_id"])
        assert run.mode == "replay" and run.metadata_json["original_commit"] == "b" * 40
        assert run.metadata_json["original_run_id"] and run.metadata_json["recorded_at"]
        assert run.metadata_json["api_calls"] == 0


@pytest.mark.ac18
@pytest.mark.ac32
def test_worker_model_failure_preserves_original_and_does_not_fallback(session_factory, settings, demo_ids):
    incident_id, _ = create_job(session_factory, demo_ids)
    failed_live = ScriptedTransport([RuntimeError("secret-key")])
    failed_live.mode = "live"
    result = run_once(session_factory, settings, FeaturePorts(), failed_live)
    assert result["status"] == "FAILED" and result["error_code"] == "API_ERROR"
    with session_factory() as tx:
        assert tx.get(AgentRun, result["run_id"]).mode == "live"
        assert tx.get(Incident, incident_id).analysis is None
        assert tx.scalar(select(func.count(Message.id))) == 1
        assert tx.scalar(select(func.count(Action.id))) == 0


@pytest.mark.ac18
@pytest.mark.ac29
@pytest.mark.parametrize("status,body,code,retryable", [
    (401, {}, "API_ACCESS_DENIED", False), (403, {}, "API_ACCESS_DENIED", False),
    (400, {}, "API_REQUEST_REJECTED", False),
    (429, {"error": {"code": "insufficient_quota"}}, "API_REQUEST_REJECTED", False),
    (400, {"error": {"code": "content_filter"}}, "REFUSAL", False),
    (429, {}, "API_ERROR", True), (503, {}, "API_ERROR", True),
])
def test_sdk_shaped_security_failures_are_not_retryable(status, body, code, retryable):
    class SDKError(Exception):
        status_code = status
    error = SDKError("raw authentication details must not be recorded")
    error.body = body
    result = run_agent(context={}, transport=ScriptedTransport([error]), execute_tool=lambda *_: {})
    assert result.error["code"] == code and result.error["retryable"] is retryable
    assert "authentication details" not in json.dumps(result.error)


@pytest.mark.ac23
@pytest.mark.ac34
@pytest.mark.parametrize("invalid", ["created_type", "version", "assignee", "required", "scope", "unreported_creation"])
def test_f2_malformed_or_inconsistent_result_is_rolled_back(session_factory, demo_ids, invalid):
    context = prepared(session_factory, demo_ids)
    draft = ToolExecutor(session_factory, context)("propose_action", json.dumps({
        "scope": "범위 확인", "completion_criteria": ["기록 제출"], "source_refs": sorted(context.source_ids)}))["data"]["draft_id"]
    def fake_f2(tx, **kwargs):
        proposal = tx.get(ActionDraft, kwargs["draft_id"]).payload_json
        action = Action(incident_id=kwargs["incident_id"], scope=proposal["scope"],
                        completion_criteria=proposal["completion_criteria"], evidence_refs=proposal["source_refs"],
                        trigger_event_id=kwargs["trigger_event_id"], proposed_by_run_id=kwargs["run_id"],
                        assignee_id=demo_ids["maintainer"])
        tx.add(action)
        tx.flush()
        response = {"action_id": action.id, "created": True, "action_version": action.version}
        if invalid == "created_type": response["created"] = 1
        elif invalid == "version": response["action_version"] += 1
        elif invalid == "assignee": action.assignee_id = demo_ids["outgoing_supervisor"]
        elif invalid == "required": action.is_required = False
        elif invalid == "scope": action.scope = "unselected scope"
        elif invalid == "unreported_creation": response["created"] = False
        return response
    with pytest.raises(DecisionRejected):
        finalize(session_factory, context.identity, execution(decision(context, "PROPOSE_ACTION", selected_draft_id=draft)),
                 FeaturePorts(action_finalizer=fake_f2))
    with session_factory() as tx:
        assert tx.scalar(select(func.count(Action.id))) == 0
        assert tx.get(Incident, context.identity.incident_id).analysis is None
        assert tx.get(Incident, context.identity.incident_id).version == context.identity.input_version


@pytest.mark.ac20
@pytest.mark.ac34
def test_handover_boundary_sees_analysis_and_rolls_back_question_on_failure(session_factory, demo_ids):
    context = prepared(session_factory, demo_ids)
    def fail_refresh(tx, *, incident, event):
        assert incident.analysis["run_id"] == context.identity.run_id
        assert incident.analysis["applied_version"] == incident.version
        assert tx.scalar(select(func.count(Request.id))) == 1
        raise RuntimeError("test-only F3 boundary failure")
    with pytest.raises(RuntimeError):
        finalize(session_factory, context.identity, execution(decision(context, "ASK_USER")),
                 FeaturePorts(handover_refresher=fail_refresh))
    with session_factory() as tx:
        assert tx.scalar(select(func.count(Request.id))) == 0
        assert tx.get(Incident, context.identity.incident_id).analysis is None
        assert tx.get(Incident, context.identity.incident_id).version == context.identity.input_version


@pytest.mark.ac10
@pytest.mark.ac27
def test_model_call_does_not_hold_incident_lock(session_factory, settings, demo_ids):
    incident_id, _ = create_job(session_factory, demo_ids)
    def while_model_runs(kwargs):
        with session_factory.begin() as other_connection:
            incident = other_connection.scalar(select(Incident).where(Incident.id == incident_id)
                                               .with_for_update(nowait=True))
            assert incident.status == "INVESTIGATING"
        return ModelReply(output=[], text=json.dumps(decision(None)))
    result = run_once(session_factory, settings, FeaturePorts(), ScriptedTransport([while_model_runs]))
    assert result["status"] == "SUCCEEDED"


@pytest.mark.ac27
def test_claim_skips_job_locked_by_other_worker(session_factory, demo_ids):
    _, first_job = create_job(session_factory, demo_ids)
    _, second_job = create_job(session_factory, demo_ids)
    with session_factory.begin() as competing_worker:
        competing_worker.scalar(select(Job).where(Job.id == first_job).with_for_update())
        claimed = claim_job(session_factory, mode="fake")
        assert claimed.job_id == second_job
    with session_factory() as tx:
        assert tx.get(Job, first_job).status == "QUEUED"
        assert tx.get(Job, second_job).status == "RUNNING"


@pytest.mark.ac32
def test_runtime_records_build_and_public_settings_fingerprint_without_secrets(session_factory, settings, demo_ids):
    create_job(session_factory, demo_ids)
    adapter = ScriptedTransport([ModelReply(output=[], text=json.dumps(decision(None)))])
    public = runtime_metadata(settings, adapter)
    different = runtime_metadata(replace(settings, agent_max_tool_calls=settings.agent_max_tool_calls + 1), adapter)
    secret_only = runtime_metadata(replace(settings, openai_api_key="do-not-store-this-key"), adapter)
    assert public["settings_id"] != different["settings_id"]
    assert public["settings_id"] == secret_only["settings_id"]
    result = run_once(session_factory, settings, FeaturePorts(), adapter)
    with session_factory() as tx:
        metadata = tx.get(AgentRun, result["run_id"]).metadata_json
        assert len(metadata["app_sha"]) >= 40 and isinstance(metadata["dirty"], bool)
        assert metadata["settings_id"].startswith("sha256:")
        assert metadata["sdk_version"] and metadata["dataset_version"] and metadata["run_group_id"]
        assert settings.session_secret not in json.dumps(metadata)
        assert "do-not-store-this-key" not in json.dumps(metadata)


@pytest.mark.ac11
@pytest.mark.ac12
def test_unresolved_or_unreviewed_case_excluded_and_text_truncation_is_partial(session_factory, demo_ids):
    context = prepared(session_factory, demo_ids)
    executor = ToolExecutor(session_factory, context)
    with session_factory.begin() as tx:
        case = tx.scalar(select(ResolutionCase).limit(1))
        case.snapshot_json = {**case.snapshot_json, "status": "INVESTIGATING"}
    query = json.dumps({"equipment_id": demo_ids["equipment"], "query": "기록"})
    assert executor("search_similar_incidents", query)["outcome"] == "EMPTY"
    with session_factory.begin() as tx:
        case = tx.scalar(select(ResolutionCase).limit(1))
        case.snapshot_json = {"text": "기록", "status": "RESOLVED"}
        document = Document(site_id=demo_ids["site"], title="longsource", equipment_ids=[demo_ids["equipment"]])
        tx.add(document)
        tx.flush()
        tx.add(DocumentChunk(document_id=document.id, position=1, text="longsource " + "x" * 2200))
    assert executor("search_similar_incidents", query)["outcome"] == "EMPTY"
    result = executor("search_documents", json.dumps({"equipment_id": demo_ids["equipment"], "query": "longsource"}))
    assert result["outcome"] == "OK" and result["partial"] is True
    assert len(result["data"]["items"]) == 1
    assert len(result["data"]["items"][0]["excerpt"]) == 2000


@pytest.mark.ac18
def test_tool_after_deadline_cannot_create_even_a_draft(session_factory, demo_ids):
    context = prepared(session_factory, demo_ids)
    executor = ToolExecutor(session_factory, context, deadline_at=time.monotonic() - 1)
    result = executor("propose_action", json.dumps({"scope": "record scope", "completion_criteria": ["result"],
                                                  "source_refs": sorted(context.source_ids)}))
    assert result["error"]["code"] == "TIMEOUT"
    with session_factory() as tx:
        assert tx.scalar(select(func.count(ActionDraft.id))) == 0
