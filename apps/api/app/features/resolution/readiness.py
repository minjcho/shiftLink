from ..actions.integrity import has_valid_approval, valid_evidence
from ..actions.models import ActionContext, FrozenModel


class Readiness(FrozenModel):
    verification_ready: bool
    unmet_requirements: tuple[str, ...]


def evaluate_resolution_readiness(context: ActionContext) -> Readiness:
    """Pure predicate. Caller loads a complete snapshot under the Incident lock.

Does not require PENDING_VERIFICATION; that would prevent completion from
entering it. Does not authorize RESOLVE or mutate any record.
"""
    missing: list[str] = []
    incident = context.incident
    if incident.review_required:
        missing.append("REVIEW_REQUIRED")
    if incident.status == "RESOLVED":
        missing.append("INCIDENT_RESOLVED")
    actions = [a for a in context.actions if a.incident_id == incident.id
               and a.is_required and a.action_slot == "MAIN_FOLLOWUP"
               and a.action_generation == 1]
    if len(actions) != 1:
        missing.append("REQUIRED_ACTION_MISSING" if not actions else "MULTIPLE_MAIN_ACTIONS")
    for action in actions:
        if action.status != "COMPLETED":
            missing.append("ACTION_NOT_COMPLETED")
        if not has_valid_approval(context, action):
            missing.append("APPROVAL_INVALID")
        if any(valid_evidence(context, ref) is None for ref in action.evidence_refs):
            missing.append("EVIDENCE_INVALID")
        message = next((m for m in context.messages if m.id == action.result_message_id), None)
        evidence = (valid_evidence(context, action.completion_evidence_id)
                    if action.completion_evidence_id else None)
        if (message is None or message.kind != "ACTION_RESULT"
                or message.site_id != incident.site_id or message.incident_id != incident.id
                or message.action_id != action.id or message.author_id != action.assignee_id
                or action.completed_at is None):
            missing.append("RESULT_MISSING")
        if (evidence is None or evidence.source_type != "completion_report"
                or message is None or evidence.source_id != message.id
                or evidence.excerpt != message.text):
            missing.append("COMPLETION_EVIDENCE_INVALID")
    for request in context.requests:
        if request.incident_id != incident.id or not request.is_required:
            continue
        reply = next((m for m in context.messages if m.id == request.response_message_id), None)
        if (request.status != "ANSWERED" or reply is None or reply.kind != "REPLY"
                or reply.incident_id != incident.id or reply.site_id != incident.site_id
                or reply.author_id != request.target_user_id or reply.reply_to_request_id != request.id):
            missing.append("REQUIRED_QUESTION_UNANSWERED")
    return Readiness(verification_ready=not missing,
                     unmet_requirements=tuple(dict.fromkeys(missing)))
