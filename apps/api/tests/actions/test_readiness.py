import pytest

from app.features.actions.models import MessageView, RequestView
from app.features.resolution.readiness import evaluate_resolution_readiness
from support import MAINTAINER, NOW, uid
from test_commands import complete


@pytest.mark.parametrize("defect,code", [
    ("no_action", "REQUIRED_ACTION_MISSING"), ("incomplete", "ACTION_NOT_COMPLETED"),
    ("no_approval", "APPROVAL_INVALID"), ("hash", "APPROVAL_INVALID"),
    ("snapshot", "APPROVAL_INVALID"), ("no_message", "RESULT_MISSING"),
    ("wrong_author", "RESULT_MISSING"), ("wrong_incident", "RESULT_MISSING"),
    ("no_evidence", "COMPLETION_EVIDENCE_INVALID"),
    ("source", "COMPLETION_EVIDENCE_INVALID"), ("excerpt", "COMPLETION_EVIDENCE_INVALID"),
    ("sop", "EVIDENCE_INVALID"), ("review", "REVIEW_REQUIRED"),
    ("resolved", "INCIDENT_RESOLVED"),
])
def test_readiness_rejects_each_missing_or_corrupt_requirement(store, defect, code):
    complete(store)
    c = store.context
    changes = {}
    if defect == "no_action": changes["actions"] = ()
    if defect == "incomplete": changes["actions"] = (c.actions[0].model_copy(update={"status": "APPROVED"}),)
    if defect == "no_approval": changes["approvals"] = ()
    if defect == "hash": changes["approvals"] = (c.approvals[0].model_copy(update={"payload_hash": "bad"}),)
    if defect == "snapshot": changes["approvals"] = (c.approvals[0].model_copy(update={"approved_payload_snapshot": {}}),)
    if defect == "no_message": changes["messages"] = ()
    if defect == "wrong_author": changes["messages"] = (c.messages[0].model_copy(update={"author_id": uid(201)}),)
    if defect == "wrong_incident": changes["messages"] = (c.messages[0].model_copy(update={"incident_id": uid(999)}),)
    if defect == "no_evidence": changes["evidence"] = c.evidence[:1]
    if defect == "source": changes["evidence"] = (c.evidence[0], c.evidence[1].model_copy(update={"source_id": uid(999)}))
    if defect == "excerpt": changes["evidence"] = (c.evidence[0], c.evidence[1].model_copy(update={"excerpt": "변조"}))
    if defect == "sop": changes["evidence"] = (c.evidence[0].model_copy(update={"document_approved": False}), c.evidence[1])
    if defect == "review": changes["incident"] = c.incident.model_copy(update={"review_required": True})
    if defect == "resolved": changes["incident"] = c.incident.model_copy(update={"status": "RESOLVED"})
    result = evaluate_resolution_readiness(c.model_copy(update=changes))
    assert not result.verification_ready and code in result.unmet_requirements


def test_answered_flag_requires_actual_reply_by_target(store):
    complete(store)
    question = RequestView(id=uid(901), incident_id=uid(401), target_user_id=MAINTAINER.user_id,
                           is_required=True, status="ANSWERED", response_message_id=uid(902))
    c = store.context.model_copy(update={"requests": (question,)})
    assert not evaluate_resolution_readiness(c).verification_ready
    reply = MessageView(id=uid(902), incident_id=uid(401), site_id=uid(1), author_id=MAINTAINER.user_id,
                        kind="REPLY", text="확인 답변", received_at=NOW, reply_to_request_id=question.id)
    c = c.model_copy(update={"messages": c.messages + (reply,)})
    assert evaluate_resolution_readiness(c).verification_ready
    # Predicate must work before transition to PENDING_VERIFICATION.
    c = c.model_copy(update={"incident": c.incident.model_copy(update={"status": "IN_PROGRESS"})})
    assert evaluate_resolution_readiness(c).verification_ready
