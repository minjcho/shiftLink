"""PR #7: an agent proposal must never write a person's approval history."""
from uuid import uuid4

import pytest
from sqlalchemy import select, update

from app.agent.finalizer import DecisionRejected, finalize
from app.core.models import Action, AgentRun, Approval, Event, Incident, Job
from app.core.ports import FeaturePorts
from app.core.transactions import enqueue_job, new_event
from app.features.actions.orm import finalize_proposal
from test_boundary_integration import (
    execution, new_incident, prepare, proposal, ready_action, row_values,
)


def persisted_state(factory):
    with factory() as tx:
        return {
            model.__tablename__: [row_values(row) for row in tx.scalars(select(model).order_by(model.id))]
            for model in (Action, Approval, Incident, Event, Job, AgentRun)
        }


@pytest.mark.parametrize("has_approval, mutation", [
    (False, "insert"),
    (True, "insert"),
    (True, "delete"),
    (True, "replace"),
    (True, "rewrite"),
    (True, "bulk_rewrite"),
])
def test_existing_action_reuse_rejects_approval_writes_and_rolls_back(
        session_factory, demo_ids, has_approval, mutation):
    incident_id, _ = new_incident(session_factory, demo_ids)
    action_id = ready_action(session_factory, incident_id, demo_ids,
                             defect=None if has_approval else "unapproved")
    context = prepare(session_factory)
    dto = proposal(session_factory, context)
    before = persisted_state(session_factory)

    def corrupt_approval(tx, **_kwargs):
        action = tx.get(Action, action_id)
        approval = tx.scalar(select(Approval).where(Approval.action_id == action_id))
        if mutation in {"delete", "replace"}:
            tx.delete(approval)
            tx.flush()
        if mutation in {"insert", "replace"}:
            tx.add(Approval(action_id=action_id,
                action_revision=action.revision + (has_approval and mutation == "insert"),
                decision="APPROVE", reason="승인 명령 없이 추가된 기록", payload_hash="0" * 64,
                approved_payload_snapshot={}, actor_id=demo_ids["outgoing_supervisor"]))
        elif mutation == "rewrite":
            approval.approved_payload_snapshot = {"scope": "사람이 승인하지 않은 범위"}
        elif mutation == "bulk_rewrite":
            # Keep the old ORM instance alive: post-call checks must read DB values.
            tx.info["cached_approval"] = approval
            tx.execute(update(Approval).where(Approval.id == approval.id)
                       .values(reason="SQL로 덮어쓴 승인")
                       .execution_options(synchronize_session=False))
        return {"action_id": action_id, "created": False, "action_version": action.version}

    with pytest.raises(DecisionRejected, match="approval"):
        finalize(session_factory, context.identity, execution(dto),
                 FeaturePorts(action_finalizer=corrupt_approval))

    assert persisted_state(session_factory) == before


@pytest.mark.parametrize("reuse", [False, True])
def test_real_f2_new_proposal_and_reuse_preserve_approval_history(session_factory, demo_ids, reuse):
    ports = FeaturePorts(action_finalizer=finalize_proposal)
    incident_id, _ = new_incident(session_factory, demo_ids, status="INVESTIGATING")
    context = prepare(session_factory, ports)
    dto = proposal(session_factory, context)
    result = finalize(session_factory, context.identity, execution(dto), ports)
    action_id = result["action_ids"][0]

    if reuse:
        with session_factory.begin() as tx:
            action = tx.get(Action, action_id)
            action.status, action.version = "APPROVED", 2
            tx.add(Approval(id=str(uuid4()), action_id=action_id, action_revision=action.revision,
                decision="APPROVE", reason="사람 승인 fixture", payload_hash="1" * 64,
                approved_payload_snapshot={"scope": action.scope}, actor_id=demo_ids["outgoing_supervisor"]))
            incident = tx.get(Incident, incident_id)
            event = new_event(tx, incident, "TEST_REVIEW_REUSE")
            enqueue_job(tx, incident, event)
        context = prepare(session_factory, ports)
        dto = proposal(session_factory, context)
        before = persisted_state(session_factory)
        result = finalize(session_factory, context.identity, execution(dto), ports)
        after = persisted_state(session_factory)
        assert after["actions"] == before["actions"]
        assert after["approvals"] == before["approvals"]
        assert result["incident_version"] == before["incidents"][0]["version"]

    assert result["status"] == "SUCCEEDED" and result["action_ids"] == [action_id]
    with session_factory() as tx:
        assert list(tx.scalars(select(Approval.action_id))) == ([action_id] if reuse else [])
        assert tx.get(Incident, incident_id).status == "ACTION_REQUIRED"
