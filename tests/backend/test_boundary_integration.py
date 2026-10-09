"""F1 integration contracts exercised with explicit test-only F2/F3/F4 adapters.

These adapters are test oracles, not implementations or proof of the other products.
"""
from copy import deepcopy
from hashlib import sha256
import json
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.agent.context import issue_evidence
from app.agent.finalizer import DecisionRejected, finalize
from app.agent.jobs import claim_job, prepare_run
from app.agent.runner import AgentExecution, ModelReply, ScriptedTransport
from app.agent.schemas import FinalDecision
from app.agent.tools import ToolExecutor
from app.agent.worker import run_once
from app.core.errors import DomainError
from app.core.models import (Action, ActionDraft, AgentRun, Approval, Event, Evidence, Handover,
    HandoverItem, HandoverRevision, Incident, Job, Message, Request, ResolutionCase, Verification)
from app.core.ports import FeaturePorts
from app.core.transactions import enqueue_job, new_event


def new_incident(factory, ids, *, status="IN_PROGRESS", review=False):
    with factory.begin() as tx:
        incident = Incident(id=str(uuid4()), display_id=f"BOUNDARY-{uuid4()}", site_id=ids["site"],
            equipment_id=ids["equipment"], reporter_id=ids["reporter"],
            origin_shift_occurrence_id=ids["outgoing_shift"], owner_shift_occurrence_id=ids["outgoing_shift"],
            owner_id=ids["outgoing_supervisor"], status=status, review_required=review)
        tx.add(incident)
        tx.flush()
        tx.add(Message(site_id=incident.site_id, incident_id=incident.id, author_id=ids["reporter"],
            kind="REPORT", text="실제 상태를 확인하기 위한 합성 제보"))
        event = new_event(tx, incident, "TEST_BOUNDARY_TRIGGER")
        job = enqueue_job(tx, incident, event)
        return incident.id, job.id


def prepare(factory, ports=None):
    identity = claim_job(factory, mode="fake", model_id="boundary-contract-test")
    assert identity is not None
    return prepare_run(factory, identity, ports or FeaturePorts())


def decision(kind, **kwargs):
    return {"facts": [], "hypotheses": [], "missing_information": [], "decision": kind,
        "questions": [], "selected_draft_id": None, "existing_request_ids": [],
        "existing_action_ids": [], "source_refs": [], "reason": "Explicit test-only boundary contract.", **kwargs}


def execution(dto):
    return AgentExecution(final=FinalDecision.model_validate(dto), mode="fake", model_id="boundary-contract-test")


def row_values(row):
    return {column.name: deepcopy(getattr(row, column.name)) for column in row.__table__.columns}


def approved_payload(action):
    return {key: getattr(action, key) for key in ("scope", "completion_criteria", "assignee_id", "evidence_refs")}


def payload_hash(payload):
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def ready_action(factory, incident_id, ids, *, defect=None, status="COMPLETED"):
    """Seed a contract-valid F4 input, then remove exactly one prerequisite if requested."""
    with factory.begin() as tx:
        incident = tx.get(Incident, incident_id)
        if defect == "empty":
            return None
        action = Action(incident_id=incident_id, scope="정의된 범위의 기록 확인", completion_criteria=["결과 원문 제출"],
            assignee_id=ids["maintainer"], status="IN_PROGRESS" if defect == "incomplete" else status,
            revision=2, version=4, action_generation=1, is_required=True)
        tx.add(action)
        tx.flush()
        message = Message(site_id=incident.site_id, incident_id=incident_id, author_id=ids["maintainer"],
            kind="ACTION_RESULT", action_id=action.id, text="지정 범위를 확인했고 결과 원문을 제출합니다.")
        tx.add(message)
        tx.flush()
        evidence = issue_evidence(tx, incident, source_type="completion_report", source_id=message.id,
            excerpt=message.text, equipment_id=incident.equipment_id, source_location=f"messages/{message.id}",
            applicability={"author_id": message.author_id, "received_at": message.received_at.isoformat()})
        action.result_message_id = None if defect == "no_result" else message.id
        action.completion_evidence_id = None if defect == "no_completion_evidence" else evidence.id
        action.evidence_refs = [evidence.id]
        tx.flush()
        payload = approved_payload(action)
        if defect != "unapproved":
            tx.add(Approval(action_id=action.id, action_revision=action.revision,
                decision="REJECT" if status == "REJECTED" else "APPROVE", reason="사람의 승인 기록",
                payload_hash="0" * 64 if defect == "approval_mismatch" else payload_hash(payload),
                approved_payload_snapshot=payload, actor_id=ids["outgoing_supervisor"]))
        if defect == "open_question":
            tx.add(Request(incident_id=incident.id, target_user_id=ids["maintainer"],
                purpose_code="VERIFY_RESULT", question="결과를 확인했습니까?", is_required=True))
        if defect == "wrong_evidence_scope":
            evidence.site_id = str(uuid4())
        return action.id


class ReadinessContract:
    """Test oracle for the documented F4 contract; production F1 only calls its port."""
    def __init__(self):
        self.calls = []

    def __call__(self, tx, *, incident):
        reasons = []
        self.calls.append((incident.id, incident.status, incident.version))
        if incident.review_required:
            reasons.append("REVIEW_REQUIRED")
        actions = list(tx.scalars(select(Action).where(Action.incident_id == incident.id,
            Action.action_generation == 1, Action.action_slot == "MAIN_FOLLOWUP", Action.is_required.is_(True))))
        if not actions:
            reasons.append("REQUIRED_ACTION_MISSING")
        for action in actions:
            if action.status != "COMPLETED":
                reasons.append("ACTION_INCOMPLETE")
            approvals = list(tx.scalars(select(Approval).where(Approval.action_id == action.id,
                Approval.action_revision == action.revision, Approval.decision == "APPROVE")))
            if not any(a.payload_hash == payload_hash(approved_payload(action)) and
                       a.approved_payload_snapshot == approved_payload(action) for a in approvals):
                reasons.append("MATCHING_APPROVAL_MISSING")
            result = tx.get(Message, action.result_message_id) if action.result_message_id else None
            if result is None or result.incident_id != incident.id or not result.author_id or not result.received_at:
                reasons.append("RESULT_MESSAGE_MISSING")
            completion = tx.get(Evidence, action.completion_evidence_id) if action.completion_evidence_id else None
            if completion is None or completion.source_type != "completion_report":
                reasons.append("COMPLETION_EVIDENCE_MISSING")
            for ref in set(action.evidence_refs + ([action.completion_evidence_id] if action.completion_evidence_id else [])):
                source = tx.get(Evidence, ref)
                if source is None or source.site_id != incident.site_id or source.incident_id != incident.id or not source.content_hash:
                    reasons.append("EVIDENCE_SCOPE_INVALID")
        if tx.scalar(select(Request.id).where(Request.incident_id == incident.id,
                Request.is_required.is_(True), Request.status != "ANSWERED").limit(1)):
            reasons.append("REQUIRED_REQUEST_OPEN")
        return {"ready": not reasons, "unmet_requirements": sorted(set(reasons))}


def attach_handover(factory, incident_id, ids):
    with factory.begin() as tx:
        incident = tx.get(Incident, incident_id)
        handover = Handover(site_id=ids["site"], from_shift_occurrence_id=ids["outgoing_shift"],
            to_shift_occurrence_id=ids["incoming_shift"], receiver_id=ids["incoming_supervisor"],
            created_by=ids["outgoing_supervisor"])
        tx.add(handover)
        tx.flush()
        item = HandoverItem(handover_id=handover.id, incident_id=incident_id)
        tx.add(item)
        tx.flush()
        tx.add(HandoverRevision(item_id=item.id, revision=1, snapshot_version=incident.version,
            snapshot_json={"status": incident.status}, snapshot_token=str(uuid4())))
        return item.id


class SnapshotContract:
    """Capture state visible inside the caller transaction, optionally fail after flushing."""
    def __init__(self, item_id, *, fail=False):
        self.item_id, self.fail, self.calls = item_id, fail, []

    def __call__(self, tx, *, incident, event):
        state = {"version": incident.version, "status": incident.status, "owner_id": incident.owner_id,
            "event": event.type, "analysis": deepcopy(incident.analysis),
            "questions": [row_values(q) for q in tx.scalars(select(Request).where(Request.incident_id == incident.id))],
            "actions": [row_values(a) for a in tx.scalars(select(Action).where(Action.incident_id == incident.id))]}
        self.calls.append(state)
        item = tx.get(HandoverItem, self.item_id)
        item.latest_revision += 1
        tx.add(HandoverRevision(item_id=item.id, revision=item.latest_revision, snapshot_version=incident.version,
            snapshot_json={"version": state["version"], "status": state["status"], "event": state["event"],
                "question_ids": [q["id"] for q in state["questions"]], "action_ids": [a["id"] for a in state["actions"]]},
            snapshot_token=str(uuid4())))
        tx.flush()
        if self.fail:
            raise DomainError(503, "SERVICE_UNAVAILABLE", "Test-only F3 adapter rejected the revision")


def proposal(factory, context):
    result = ToolExecutor(factory, context)("propose_action", json.dumps({"scope": "기록 범위 확인",
        "completion_criteria": ["확인한 범위의 원문 제출"], "source_refs": sorted(context.source_ids)}))
    assert result["outcome"] == "OK"
    return decision("PROPOSE_ACTION", selected_draft_id=result["data"]["draft_id"])


def creating_action_adapter(ids):
    def create(tx, **kwargs):
        draft = tx.get(ActionDraft, kwargs["draft_id"])
        assert draft.run_id == kwargs["run_id"] and draft.input_version == kwargs["input_version"]
        action = Action(incident_id=kwargs["incident_id"], scope=draft.payload_json["scope"],
            completion_criteria=draft.payload_json["completion_criteria"], evidence_refs=draft.payload_json["source_refs"],
            assignee_id=ids["maintainer"], trigger_event_id=kwargs["trigger_event_id"], proposed_by_run_id=kwargs["run_id"])
        tx.add(action)
        tx.flush()
        return {"action_id": action.id, "created": True, "action_version": action.version}
    return create


@pytest.mark.ac25
@pytest.mark.ac34
def test_readiness_moves_completed_work_from_nonpending_state_only_to_pending(session_factory, demo_ids):
    incident_id, job_id = new_incident(session_factory, demo_ids)
    action_id = ready_action(session_factory, incident_id, demo_ids)
    item_id = attach_handover(session_factory, incident_id, demo_ids)
    context = prepare(session_factory)
    evaluator, snapshot = ReadinessContract(), SnapshotContract(item_id)
    result = finalize(session_factory, context.identity, execution(decision("REQUEST_VERIFICATION")),
        FeaturePorts(readiness_evaluator=evaluator, handover_refresher=snapshot))
    assert result["status"] == "SUCCEEDED" and result["incident_version"] == 2
    assert evaluator.calls == [(incident_id, "IN_PROGRESS", 1)]
    assert snapshot.calls[0]["status"] == "PENDING_VERIFICATION"
    assert snapshot.calls[0]["analysis"]["applied_version"] == 2
    assert snapshot.calls[0]["actions"][0]["id"] == action_id
    with session_factory() as tx:
        incident = tx.get(Incident, incident_id)
        assert incident.status == "PENDING_VERIFICATION" and incident.resolved_at is None
        assert tx.get(HandoverItem, item_id).latest_revision == 2
        assert tx.get(HandoverRevision, (item_id, 2)).snapshot_version == incident.version
        assert tx.get(Job, job_id).status == tx.get(AgentRun, context.identity.run_id).status == "SUCCEEDED"
        assert tx.scalar(select(func.count(Verification.id))) == 0
        assert tx.scalar(select(func.count(ResolutionCase.id)).where(ResolutionCase.incident_id == incident_id)) == 0


@pytest.mark.ac25
@pytest.mark.ac34
@pytest.mark.parametrize("defect,reason", [
    ("empty", "REQUIRED_ACTION_MISSING"), ("unapproved", "MATCHING_APPROVAL_MISSING"),
    ("approval_mismatch", "MATCHING_APPROVAL_MISSING"), ("incomplete", "ACTION_INCOMPLETE"),
    ("open_question", "REQUIRED_REQUEST_OPEN"), ("no_result", "RESULT_MESSAGE_MISSING"),
    ("no_completion_evidence", "COMPLETION_EVIDENCE_MISSING"), ("wrong_evidence_scope", "EVIDENCE_SCOPE_INVALID")])
def test_unmet_readiness_is_persisted_with_reason_without_business_effects(session_factory, demo_ids, settings, defect, reason):
    incident_id, job_id = new_incident(session_factory, demo_ids)
    ready_action(session_factory, incident_id, demo_ids, defect=defect)
    evaluator = ReadinessContract()
    adapter = ScriptedTransport([ModelReply(output=[], text=json.dumps(decision("REQUEST_VERIFICATION")))])
    result = run_once(session_factory, settings, FeaturePorts(readiness_evaluator=evaluator), model_adapter=adapter)
    assert result["status"] == "FAILED" and result["error_code"] == "READINESS_NOT_MET"
    with session_factory() as tx:
        incident, job = tx.get(Incident, incident_id), tx.get(Job, job_id)
        assert incident.status == "IN_PROGRESS" and incident.version == 1 and incident.analysis is None
        assert reason in job.last_error["details"]["unmet_requirements"]
        run = tx.get(AgentRun, result["run_id"])
        assert run.status == "FAILED" and run.error_json == job.last_error
        assert run.decision_json["decision"] == "REQUEST_VERIFICATION"
        assert tx.scalar(select(func.count(Event.id)).where(Event.incident_id == incident_id)) == 1


@pytest.mark.ac25
@pytest.mark.ac34
def test_review_required_rejects_readiness_before_external_service(session_factory, demo_ids, settings):
    incident_id, job_id = new_incident(session_factory, demo_ids, review=True)
    action_id = ready_action(session_factory, incident_id, demo_ids, status="REJECTED")
    with session_factory() as tx:
        before = row_values(tx.get(Action, action_id))
    evaluator = ReadinessContract()
    adapter = ScriptedTransport([ModelReply(output=[], text=json.dumps(decision("REQUEST_VERIFICATION")))])
    result = run_once(session_factory, settings, FeaturePorts(readiness_evaluator=evaluator), model_adapter=adapter)
    assert result["error_code"] == "REVIEW_REQUIRED" and not evaluator.calls
    with session_factory() as tx:
        incident = tx.get(Incident, incident_id)
        assert incident.review_required and incident.status == "IN_PROGRESS" and incident.version == 1
        assert row_values(tx.get(Action, action_id)) == before
        assert tx.get(Job, job_id).status == "FAILED"


@pytest.mark.ac23
@pytest.mark.ac24
@pytest.mark.ac34
@pytest.mark.parametrize("status", ["COMPLETED", "REJECTED"])
def test_propose_action_reuses_terminal_generation_without_modifying_work_or_approval(session_factory, demo_ids, status):
    incident_id, _ = new_incident(session_factory, demo_ids)
    action_id = ready_action(session_factory, incident_id, demo_ids, status=status)
    context = prepare(session_factory)
    dto = proposal(session_factory, context)
    with session_factory() as tx:
        before = row_values(tx.get(Action, action_id))
        approval_before = row_values(tx.scalar(select(Approval).where(Approval.action_id == action_id)))
    def reuse(tx, **kwargs):
        assert kwargs["incident_id"] == incident_id
        action = tx.get(Action, action_id)
        return {"action_id": action.id, "created": False, "action_version": action.version}
    result = finalize(session_factory, context.identity, execution(dto), FeaturePorts(action_finalizer=reuse))
    assert result["action_ids"] == [action_id] and result["incident_version"] == 1
    with session_factory() as tx:
        assert row_values(tx.get(Action, action_id)) == before
        assert row_values(tx.get(Approval, approval_before["id"])) == approval_before
        incident = tx.get(Incident, incident_id)
        assert incident.version == 1 and incident.status == "IN_PROGRESS"
        assert incident.analysis["applied_version"] == 1
        assert tx.scalar(select(func.count(Action.id))) == 1 and tx.scalar(select(func.count(Request.id))) == 0
        assert tx.scalar(select(func.count(Event.id))) == 1


@pytest.mark.ac23
@pytest.mark.ac24
@pytest.mark.ac34
def test_existing_action_adapter_cannot_rewrite_approval(session_factory, demo_ids):
    incident_id, _ = new_incident(session_factory, demo_ids)
    action_id = ready_action(session_factory, incident_id, demo_ids)
    context = prepare(session_factory)
    dto = proposal(session_factory, context)
    def mutate_approval(tx, **_kwargs):
        tx.scalar(select(Approval).where(Approval.action_id == action_id)).decision = "REJECT"
        return {"action_id": action_id, "created": False, "action_version": 4}
    with pytest.raises(DecisionRejected):
        finalize(session_factory, context.identity, execution(dto), FeaturePorts(action_finalizer=mutate_approval))
    with session_factory() as tx:
        assert tx.scalar(select(Approval).where(Approval.action_id == action_id)).decision == "APPROVE"
        assert tx.get(Incident, incident_id).analysis is None


@pytest.mark.ac5
@pytest.mark.ac34
@pytest.mark.parametrize("fail", [False, True])
def test_initial_investigation_transition_and_handover_revision_share_transaction(session_factory, demo_ids, fail):
    incident_id, job_id = new_incident(session_factory, demo_ids, status="OPEN")
    item_id = attach_handover(session_factory, incident_id, demo_ids)
    snapshot = SnapshotContract(item_id, fail=fail)
    if fail:
        with pytest.raises(DomainError):
            prepare(session_factory, FeaturePorts(handover_refresher=snapshot))
    else:
        context = prepare(session_factory, FeaturePorts(handover_refresher=snapshot))
        assert context.identity.input_version == 2
    assert snapshot.calls[0]["version"] == 2 and snapshot.calls[0]["status"] == "INVESTIGATING"
    with session_factory() as tx:
        incident = tx.get(Incident, incident_id)
        assert (incident.status, incident.version) == (("OPEN", 1) if fail else ("INVESTIGATING", 2))
        assert tx.get(HandoverItem, item_id).latest_revision == (1 if fail else 2)
        assert tx.scalar(select(func.count(HandoverRevision.revision))) == (1 if fail else 2)
        assert tx.scalar(select(func.count(Event.id))) == (1 if fail else 2)
        assert tx.get(Job, job_id).status == "RUNNING"


@pytest.mark.ac5
@pytest.mark.ac23
@pytest.mark.ac25
@pytest.mark.ac34
@pytest.mark.parametrize("kind", ["ASK_USER", "PROPOSE_ACTION", "REQUEST_VERIFICATION"])
@pytest.mark.parametrize("fail", [False, True])
def test_final_business_effects_are_visible_to_handover_and_rollback_together(session_factory, demo_ids, kind, fail):
    incident_id, job_id = new_incident(session_factory, demo_ids)
    if kind == "REQUEST_VERIFICATION":
        ready_action(session_factory, incident_id, demo_ids)
    item_id = attach_handover(session_factory, incident_id, demo_ids)
    context = prepare(session_factory)
    snapshot = SnapshotContract(item_id, fail=fail)
    feature_ports = FeaturePorts(action_finalizer=creating_action_adapter(demo_ids),
        readiness_evaluator=ReadinessContract(), handover_refresher=snapshot)
    dto = decision(kind)
    if kind == "PROPOSE_ACTION":
        dto = proposal(session_factory, context)
    elif kind == "ASK_USER":
        dto["questions"] = [{"question": "확인 범위를 알려 주세요.", "purpose_code": "VERIFY_SCOPE",
            "target_user_id": demo_ids["maintainer"], "source_refs": sorted(context.source_ids)}]
    if fail:
        with pytest.raises(DomainError):
            finalize(session_factory, context.identity, execution(dto), feature_ports)
    else:
        result = finalize(session_factory, context.identity, execution(dto), feature_ports)
        assert result["incident_version"] == 2
    captured = snapshot.calls[0]
    assert captured["version"] == 2 and captured["analysis"]["decision"] == kind
    assert captured["analysis"]["applied_version"] == 2
    if kind == "ASK_USER":
        assert captured["questions"][0]["is_required"] and captured["questions"][0]["status"] == "OPEN"
        assert captured["questions"][0]["target_user_id"] == demo_ids["maintainer"]
    if kind == "PROPOSE_ACTION":
        assert captured["status"] == "ACTION_REQUIRED" and captured["actions"][0]["status"] == "PROPOSED"
    if kind == "REQUEST_VERIFICATION":
        assert captured["status"] == "PENDING_VERIFICATION" and captured["actions"][0]["status"] == "COMPLETED"
    with session_factory() as tx:
        incident = tx.get(Incident, incident_id)
        assert incident.version == (1 if fail else 2)
        assert (incident.analysis is None) == fail
        assert tx.get(HandoverItem, item_id).latest_revision == (1 if fail else 2)
        assert tx.scalar(select(func.count(HandoverRevision.revision))) == (1 if fail else 2)
        assert tx.scalar(select(func.count(Event.id))) == (1 if fail else 2)
        assert tx.get(Job, job_id).status == ("RUNNING" if fail else "SUCCEEDED")
        assert tx.get(AgentRun, context.identity.run_id).status == ("RUNNING" if fail else ("WAITING_INPUT" if kind == "ASK_USER" else "SUCCEEDED"))
        assert tx.scalar(select(func.count(Request.id))) == (1 if kind == "ASK_USER" and not fail else 0)
        assert tx.scalar(select(func.count(Action.id))) == (1 if kind == "REQUEST_VERIFICATION" or (kind == "PROPOSE_ACTION" and not fail) else 0)
