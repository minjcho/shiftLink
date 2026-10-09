"""Pure F2 decisions: no IO, commit, authentication bootstrap, or model calls."""

from datetime import datetime
from uuid import UUID, uuid4

from ..resolution.readiness import evaluate_resolution_readiness
from .commands import ActionCommand, ApprovalCommand, CompletionCommand
from .errors import ActionError
from .integrity import approval_payload, canonical_hash, content_hash, has_valid_approval, valid_evidence
from .models import Action, ActionContext, Approval, Event, EvidenceView, MessageView, Principal, Transition


def find_action(context: ActionContext, action_id: UUID) -> Action:
    action = next((a for a in context.actions if a.id == action_id
                   and a.incident_id == context.incident.id), None)
    if action is None:
        raise ActionError(404, "RESOURCE_NOT_FOUND", "작업을 찾을 수 없습니다.")
    return action


def decide(context: ActionContext, principal: Principal, action_id: UUID,
           command: ActionCommand, now: datetime) -> Transition:
    incident = context.incident
    if incident.site_id != principal.site_id:
        raise ActionError(404, "RESOURCE_NOT_FOUND", "작업을 찾을 수 없습니다.")
    action = find_action(context, action_id)
    is_approval = isinstance(command, ApprovalCommand)
    permitted = (principal.role == "supervisor" and principal.user_id == incident.owner_id
                 if is_approval else principal.user_id == action.assignee_id)
    if not permitted:
        raise ActionError(403, "FORBIDDEN", "이 작업을 처리할 권한이 없습니다.")
    if incident.status == "RESOLVED":
        raise ActionError(409, "INCIDENT_RESOLVED", "해결된 사건입니다. 새 제보를 작성해 주세요.")
    for target, expected, current in (
        ("action", command.expected_version, action.version),
        ("incident", command.expected_incident_version, incident.version),
    ):
        if expected != current:
            raise ActionError(409, "VERSION_CONFLICT", "내용이 변경됐습니다. 다시 확인해 주세요.",
                              current_version=current,
                              details={"target": target, "expected_version": expected})
    if incident.review_required:
        raise ActionError(409, "REVIEW_REQUIRED", "후속 검토가 필요한 사건입니다.")
    expected_state = "PROPOSED" if is_approval else (
        "IN_PROGRESS" if isinstance(command, CompletionCommand) else "APPROVED")
    if action.status != expected_state:
        raise ActionError(409, "INVALID_STATE", "현재 작업 상태에서 실행할 수 없습니다.")
    if not is_approval and not has_valid_approval(context, action):
        raise ActionError(409, "INVALID_STATE", "승인된 작업 내용과 일치하지 않습니다.")
    refs = action.evidence_refs + (command.evidence_refs if isinstance(command, CompletionCommand) else ())
    rejecting = is_approval and command.decision == "REJECT"
    if not rejecting and any(valid_evidence(context, ref) is None for ref in refs):
        raise ActionError(422, "EVIDENCE_INVALID", "이 사건에서 사용할 수 없는 근거입니다.")

    approvals, messages, evidence = context.approvals, context.messages, context.evidence
    incident_changes: dict = {"version": incident.version + 1}
    action_changes: dict = {"version": action.version + 1}
    data: dict = {}
    if is_approval:
        if any(a.action_id == action.id for a in approvals):
            raise ActionError(409, "INVALID_STATE", "이미 승인 또는 반려된 작업입니다.")
        payload = approval_payload(action)
        approval = Approval(id=uuid4(), action_id=action.id, action_revision=action.revision,
                            decision=command.decision, reason=command.reason,
                            payload_hash=canonical_hash(payload), approved_payload_snapshot=payload,
                            actor_id=principal.user_id, created_at=now)
        approvals += (approval,)
        action_changes["status"] = "APPROVED" if command.decision == "APPROVE" else "REJECTED"
        if command.decision == "REJECT":
            incident_changes.update(status="INVESTIGATING", review_required=True,
                                    review_reason=command.reason)
        data.update(approval_id=str(approval.id), payload_hash=approval.payload_hash)
        event_type = f"ACTION_{action_changes['status']}"
    elif isinstance(command, CompletionCommand):
        message = MessageView(id=uuid4(), site_id=incident.site_id, incident_id=incident.id,
                              author_id=principal.user_id, kind="ACTION_RESULT", text=command.result,
                              received_at=now, action_id=action.id)
        report = EvidenceView(id=uuid4(), site_id=incident.site_id, incident_id=incident.id,
                              source_type="completion_report", source_id=message.id,
                              source_version="1", excerpt=command.result,
                              content_hash=content_hash(command.result), captured_at=now, applicable=True)
        messages += (message,)
        evidence += (report,)
        action_changes.update(status="COMPLETED", completed_at=now,
                              result_message_id=message.id, completion_evidence_id=report.id)
        data.update(result_message_id=str(message.id), completion_evidence_id=str(report.id))
        event_type = "ACTION_COMPLETED"
    else:
        action_changes.update(status="IN_PROGRESS", started_at=now)
        incident_changes["status"] = "IN_PROGRESS"
        data["started_at"] = now.isoformat()
        event_type = "ACTION_STARTED"

    action = action.model_copy(update=action_changes)
    incident = incident.model_copy(update=incident_changes)
    updated = context.model_copy(update={
        "incident": incident, "actions": tuple(action if a.id == action.id else a for a in context.actions),
        "approvals": approvals, "messages": messages, "evidence": evidence,
    })
    if isinstance(command, CompletionCommand):
        readiness = evaluate_resolution_readiness(updated)
        data.update(readiness.model_dump(mode="json"))
        if readiness.verification_ready:
            incident = incident.model_copy(update={"status": "PENDING_VERIFICATION"})
            updated = updated.model_copy(update={"incident": incident})
    data.update(action_id=str(action.id), action_status=action.status, action_version=action.version,
                incident_status=incident.status, incident_version=incident.version)
    if is_approval:
        data["review_required"] = incident.review_required
    event_payload = {"action_version": action.version, "incident_version": incident.version}
    if isinstance(command, CompletionCommand):
        event_payload.update(result_message_id=str(action.result_message_id),
                             evidence_refs=[str(ref) for ref in command.evidence_refs])
    return Transition(context=updated, data=data, event=Event(
        type=event_type, actor_id=principal.user_id, incident_id=incident.id,
        action_id=action.id, occurred_at=now, payload=event_payload))
