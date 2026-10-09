"""Model input limits: real persisted originals, no external model calls."""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.agent.context import issue_evidence
from app.agent.finalizer import DecisionRejected, finalize
from app.agent.jobs import claim_job, prepare_run
from app.agent.runner import (AgentExecution, ModelReply, RunLimits, ScriptedTransport,
                              initial_inputs, request_budget_bytes, run_agent)
from app.agent.schemas import FinalDecision
from app.agent.worker import run_once
from app.core.config import Settings
from app.core.models import (Action, AgentRun, Approval, Event, Evidence, Incident, Job,
                             Message, Request, utcnow)
from app.core.ports import FeaturePorts
from app.core.transactions import enqueue_job, new_event


def history_job(factory, ids, *, history_count=0, report="최초 원문", latest="최신 필수 원문"):
    with factory.begin() as tx:
        incident = Incident(display_id=f"BUDGET-{uuid4()}", site_id=ids["site"],
            equipment_id=ids["equipment"], reporter_id=ids["reporter"],
            origin_shift_occurrence_id=ids["outgoing_shift"],
            owner_shift_occurrence_id=ids["outgoing_shift"], owner_id=ids["outgoing_supervisor"],
            status="INVESTIGATING")
        tx.add(incident)
        tx.flush()
        now = utcnow()
        first = Message(site_id=incident.site_id, incident_id=incident.id, author_id=ids["reporter"],
                        kind="REPORT", text=report, received_at=now)
        tx.add(first)
        for i in range(history_count):
            tx.add(Message(site_id=incident.site_id, incident_id=incident.id, author_id=ids["reporter"],
                kind="NOTE", text=f"과거 {i}: " + "기록" * 9000, received_at=now + timedelta(seconds=i + 1)))
        last = Message(site_id=incident.site_id, incident_id=incident.id, author_id=ids["reporter"],
                       kind="NOTE", text=latest, received_at=now + timedelta(seconds=history_count + 1))
        tx.add(last)
        tx.flush()
        event = new_event(tx, incident, "message_added", related_ids={"message_id": last.id})
        enqueue_job(tx, incident, event)
        return incident.id, first.id, last.id


def test_long_irrelevant_history_is_bounded_without_losing_current_originals(session_factory, demo_ids):
    incident_id, first_id, last_id = history_job(session_factory, demo_ids, history_count=12)
    context = prepare_run(session_factory, claim_job(session_factory, mode="fake"), FeaturePorts())
    encoded = json.dumps(context.payload, ensure_ascii=False).encode()
    assert len(encoded) < 262144
    originals = {m["id"]: m["text"] for m in context.payload["messages"]}
    assert originals[first_id] == "최초 원문"
    assert originals[last_id] == "최신 필수 원문"
    assert encoded.count("최신 필수 원문".encode()) == 1
    with session_factory() as tx:
        stored = list(tx.scalars(select(Message).where(Message.incident_id == incident_id)))
        assert len(stored) == 14
        assert sum(len(m.text) for m in stored) > 200000
        all_evidence = list(tx.scalars(select(Evidence).where(Evidence.incident_id == incident_id)))
        assert len(all_evidence) == 14
        stored_text = {m.id: m.text for m in stored}
        assert all(e.excerpt == stored_text[e.source_id] for e in all_evidence)
    assert context.payload["context_selection"]["omitted_messages"] > 0
    assert request_budget_bytes(initial_inputs(context.payload), 2000) <= 262144


def blocked(**overrides):
    return {"facts": [], "hypotheses": [], "missing_information": [], "decision": "BLOCKED",
            "questions": [], "selected_draft_id": None, "existing_request_ids": [],
            "existing_action_ids": [], "source_refs": [], "reason": "명시적 시험 판단", **overrides}


def test_small_context_keeps_all_originals_once_and_still_runs(session_factory, demo_ids):
    history_job(session_factory, demo_ids)
    context = prepare_run(session_factory, claim_job(session_factory, mode="fake"), FeaturePorts())
    assert context.payload["context_selection"]["omitted_messages"] == 0
    assert context.payload["context_selection"]["omitted_evidence"] == 0
    encoded = json.dumps(context.payload, ensure_ascii=False)
    assert encoded.count("최초 원문") == encoded.count("최신 필수 원문") == 1
    assert all("excerpt_from" in e and "excerpt" not in e for e in context.payload["evidence"])
    transport = ScriptedTransport([ModelReply(output=[], text=json.dumps(blocked()))])
    result = run_agent(context=context.payload, transport=transport, execute_tool=lambda *_: {})
    assert result.error is None and result.final.decision.value == "BLOCKED"
    assert len(transport.requests) == 1


def test_omitted_existing_evidence_stays_stored_but_cannot_be_cited(session_factory, demo_ids):
    incident_id, _, _ = history_job(session_factory, demo_ids, history_count=12)
    context = prepare_run(session_factory, claim_job(session_factory, mode="fake"), FeaturePorts())
    sent = {e["id"] for e in context.payload["evidence"]}
    with session_factory() as tx:
        all_ids = set(tx.scalars(select(Evidence.id).where(Evidence.incident_id == incident_id)))
        omitted = sorted(all_ids - sent)[0]
        assert set(tx.get(AgentRun, context.identity.run_id).metadata_json["observed_source_ids"]) == sent
    assert context.source_ids == sent
    execution = AgentExecution(final=FinalDecision.model_validate(blocked(source_refs=[omitted])))
    with pytest.raises(DecisionRejected) as rejected:
        finalize(session_factory, context.identity, execution, FeaturePorts())
    assert rejected.value.code == "EVIDENCE_INVALID"
    with session_factory() as tx:
        assert tx.get(Evidence, omitted) is not None
        assert tx.get(Incident, incident_id).analysis is None


def test_required_trigger_answers_result_approval_and_targets_survive_history(session_factory, demo_ids):
    incident_id, first_id, latest_id = history_job(session_factory, demo_ids, history_count=12)
    with session_factory.begin() as tx:
        incident = tx.get(Incident, incident_id)
        old = tx.scalar(select(Message).where(Message.incident_id == incident_id, Message.kind == "NOTE")
                        .order_by(Message.received_at).limit(1))
        # An older queued trigger must be supplied as well as the latest DB message.
        job = tx.scalar(select(Job).where(Job.incident_id == incident_id))
        tx.get(Event, job.trigger_event_id).related_ids = {"message_id": old.id}
        old_id = old.id
        request = Request(incident_id=incident_id, target_user_id=demo_ids["maintainer"],
                          purpose_code="VERIFY_SCOPE", question="필수 확인 질문", status="ANSWERED")
        tx.add(request)
        tx.flush()
        answer = Message(site_id=incident.site_id, incident_id=incident_id, author_id=demo_ids["maintainer"],
                         kind="REPLY", text="필수 답변 원문", reply_to_request_id=request.id,
                         received_at=utcnow() - timedelta(days=1))
        tx.add(answer)
        tx.flush()
        request.response_message_id = answer.id
        ev = issue_evidence(tx, incident, source_type="message", source_id=answer.id, excerpt=answer.text,
                            equipment_id=incident.equipment_id, source_location=f"messages/{answer.id}")
        request.evidence_refs = [ev.id]
        result = Message(site_id=incident.site_id, incident_id=incident_id, author_id=demo_ids["maintainer"],
                         kind="ACTION_RESULT", text="완료 결과 원문", received_at=utcnow() - timedelta(hours=1))
        tx.add(result)
        tx.flush()
        action = Action(incident_id=incident_id, assignee_id=demo_ids["maintainer"], scope="현재 작업 범위",
                        completion_criteria=["필수 완료 기준"], status="COMPLETED", result_message_id=result.id)
        tx.add(action)
        tx.flush()
        tx.add(Approval(action_id=action.id, action_revision=1, decision="APPROVE", reason="허가 사유",
                        payload_hash="a" * 64, approved_payload_snapshot={"scope": action.scope},
                        actor_id=demo_ids["outgoing_supervisor"]))
        answer_id, result_id, action_id = answer.id, result.id, action.id
        incident.version = 9
        incident.status = "PENDING_VERIFICATION"
        # Keep the first report explicitly; answer timestamps need not be insertion order.
        tx.get(Message, first_id).received_at = utcnow() - timedelta(days=2)
    context = prepare_run(session_factory, claim_job(session_factory, mode="fake"), FeaturePorts())
    ids = {m["id"] for m in context.payload["messages"]}
    assert {first_id, latest_id, old_id, answer_id, result_id}.issubset(ids)
    assert context.payload["incident"]["status"] == "PENDING_VERIFICATION"
    assert context.payload["input_version"] == 9
    assert context.payload["requests"][0]["response_message_id"] == answer_id
    assert context.payload["actions"][0]["id"] == action_id
    assert context.payload["actions"][0]["status"] == "COMPLETED"
    assert context.payload["approvals"][0]["reason"] == "허가 사유"
    assert context.payload["allowed_question_target_ids"] == [demo_ids["maintainer"]]
    assert context.payload["context_selection"]["omitted_messages"] > 0


def test_accumulated_search_evidence_has_deterministic_bounded_selection(session_factory, demo_ids):
    incident_id, _, _ = history_job(session_factory, demo_ids)
    with session_factory.begin() as tx:
        incident = tx.get(Incident, incident_id)
        for i in range(12):
            issue_evidence(tx, incident, source_type="sop", source_id=str(uuid4()),
                           excerpt=f"문서 {i}: " + "자료" * 7000, equipment_id=incident.equipment_id)
    identity = claim_job(session_factory, mode="fake")
    first = prepare_run(session_factory, identity, FeaturePorts())
    again = prepare_run(session_factory, identity, FeaturePorts())
    assert first.payload == again.payload and first.source_ids == again.source_ids
    assert first.payload["context_selection"]["omitted_evidence"] > 0
    assert request_budget_bytes(initial_inputs(first.payload), 2000) <= 262144
    with session_factory() as tx:
        assert tx.scalar(select(func.count(Evidence.id)).where(Evidence.incident_id == incident_id)) == 14


@pytest.mark.parametrize("large", [False, True])
def test_optional_correction_chain_is_included_or_omitted_as_a_whole(session_factory, demo_ids, large):
    incident_id, first_id, _ = history_job(session_factory, demo_ids)
    with session_factory.begin() as tx:
        first = tx.get(Message, first_id)
        original = Message(site_id=demo_ids["site"], incident_id=incident_id, author_id=demo_ids["reporter"],
                           kind="NOTE", text="틀린 기록" + ("가" * 19990 if large else ""),
                           received_at=first.received_at + timedelta(milliseconds=200))
        tx.add(original)
        tx.flush()
        correction = Message(site_id=demo_ids["site"], incident_id=incident_id,
                             author_id=demo_ids["reporter"], kind="CORRECTION", text="정정된 기록",
                             correction_of=original.id, received_at=first.received_at + timedelta(milliseconds=400))
        tx.add(correction)
        tx.flush()
        component = {original.id, correction.id}
    context = prepare_run(session_factory, claim_job(session_factory, mode="fake"), FeaturePorts(),
                          max_input_bytes=65536)
    selected = {m["id"] for m in context.payload["messages"]}
    assert selected & component == (set() if large else component)
    supplied_sources = {e["source_id"] for e in context.payload["evidence"]}
    assert supplied_sources & component == (set() if large else component)
    with session_factory() as tx:
        assert tx.get(Message, original.id).text.startswith("틀린 기록")
        assert tx.get(Message, correction.id).text == "정정된 기록"


def test_oversized_required_original_fails_without_model_or_business_effect(session_factory, demo_ids, settings):
    raw = "가" * 20000
    incident_id, first_id, _ = history_job(session_factory, demo_ids, report=raw)
    with session_factory.begin() as tx:
        incident = tx.get(Incident, incident_id)
        evidence = issue_evidence(tx, incident, source_type="message", source_id=first_id, excerpt=raw,
                                  equipment_id=incident.equipment_id)
        evidence_id = evidence.id
    transport = ScriptedTransport([])
    result = run_once(session_factory, replace(settings, agent_max_input_bytes=32768),
                      FeaturePorts(), transport)
    assert result["status"] == "FAILED" and result["error_code"] == "CONTEXT_LIMIT"
    assert transport.requests == []
    with session_factory() as tx:
        incident = tx.get(Incident, incident_id)
        assert incident.version == 1 and incident.status == "INVESTIGATING" and incident.analysis is None
        assert tx.get(Message, first_id).text == tx.get(Evidence, evidence_id).excerpt == raw
        run, job = tx.get(AgentRun, result["run_id"]), tx.get(Job, result["job_id"])
        assert run.status == job.status == "FAILED"
        assert run.error_json["code"] == job.last_error["code"] == "CONTEXT_LIMIT"
        assert job.last_error["retryable"] is False
        assert tx.scalar(select(func.count(Request.id))) == tx.scalar(select(func.count(Action.id))) == 0


def test_each_call_counts_accumulated_protocol_tool_results_schema_and_output_headroom():
    replies = [ModelReply(output=[{"type": "function_call", "name": "get_equipment_context",
                "arguments": json.dumps({"equipment_id": str(uuid4())}), "call_id": f"call-{i}"}])
               for i in range(3)]
    transport = ScriptedTransport(replies)
    result = run_agent(context={}, transport=transport,
                       execute_tool=lambda *_: {"outcome": "OK", "data": "x" * 10000,
                                                "source_refs": [], "partial": False, "error": None},
                       limits=RunLimits(max_input_bytes=35000))
    assert result.error["code"] == "CONTEXT_LIMIT" and result.final is None
    assert result.model_calls == result.tool_calls == len(transport.requests) == 2
    assert request_budget_bytes(transport.requests[-1]["inputs"], 2000) <= 35000
    assert len(result.steps) == 2 and all(len(step["result"]["data"]) == 10000 for step in result.steps)

    # Raw context fits; the complete envelope plus schemas/output allowance does not.
    context = {"text": "가" * 7000}
    assert len(json.dumps(context, ensure_ascii=False).encode()) < 35000
    transport = ScriptedTransport([])
    result = run_agent(context=context, transport=transport, execute_tool=lambda *_: {},
                       limits=RunLimits(max_input_bytes=35000))
    assert result.error["code"] == "CONTEXT_LIMIT" and result.model_calls == 0
    assert transport.requests == []


@pytest.mark.parametrize("value", [0, 32767, 1048577])
def test_input_budget_configuration_rejects_out_of_range(settings, value):
    with pytest.raises(ValueError, match="AGENT_MAX_INPUT_BYTES"):
        replace(settings, agent_max_input_bytes=value).validate()


def test_input_budget_configuration_accepts_process_environment(monkeypatch, settings):
    monkeypatch.setenv("AGENT_MAX_INPUT_BYTES", "131072")
    assert Settings.from_env().agent_max_input_bytes == 131072
    replace(settings, agent_max_input_bytes=32768).validate()
    replace(settings, agent_max_input_bytes=1048576).validate()
