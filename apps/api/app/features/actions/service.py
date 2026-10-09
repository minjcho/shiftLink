from datetime import UTC, datetime
from typing import Callable
from uuid import UUID, uuid4

from .commands import ActionCommand, ApprovalCommand, CompletionCommand
from .domain import decide
from .errors import ActionError
from .integrity import canonical_hash, valid_evidence
from .models import Action, CommandResponse, Event, Principal
from .ports import ActionTransaction, TransactionFactory


def finalize_action_proposal(tx: ActionTransaction, *, incident_id: UUID, run_id: UUID,
                             input_version: int, draft_id: UUID, trigger_event_id: UUID) -> dict:
    context = tx.lock_context(incident_id)
    incident = context.incident
    if incident.status == "RESOLVED":
        raise ActionError(409, "INCIDENT_RESOLVED", "이미 해결된 사건입니다.")
    if incident.review_required:
        raise ActionError(409, "REVIEW_REQUIRED", "후속 검토가 필요합니다.")
    if incident.version != input_version:
        raise ActionError(409, "VERSION_CONFLICT", "후보가 이전 사건 정보로 작성됐습니다.",
                          current_version=incident.version, details={"target": "incident"})
    draft, run = tx.load_draft(draft_id), tx.load_run(run_id)
    if (draft.incident_id != incident_id or draft.run_id != run_id
            or draft.input_version != input_version or run.incident_id != incident_id
            or run.input_version != input_version or run.trigger_event_id != trigger_event_id
            or run.status != "RUNNING"):
        raise ActionError(422, "VALIDATION_ERROR", "현재 조사에 속하지 않는 작업 후보입니다.")
    if any(valid_evidence(context, ref) is None for ref in draft.source_refs):
        raise ActionError(422, "EVIDENCE_INVALID", "작업 후보의 근거를 확인할 수 없습니다.")
    existing = [a for a in context.actions if a.incident_id == incident_id
                and a.action_slot == "MAIN_FOLLOWUP" and a.action_generation == 1]
    if len(existing) > 1:
        raise ActionError(409, "INVALID_STATE", "주 작업 고유 제약이 충족되지 않았습니다.")
    if existing:
        return {"action_id": str(existing[0].id), "created": False, "action_version": existing[0].version}
    if incident.status != "INVESTIGATING":
        raise ActionError(409, "INVALID_STATE", "조사 중인 사건에만 작업을 생성할 수 있습니다.")
    assignment = tx.resolve_assignment(context)
    now = datetime.now(UTC)
    action = Action(id=uuid4(), incident_id=incident_id, trigger_event_id=trigger_event_id,
                    proposed_by_run_id=run_id, title=draft.scope[:120], scope=draft.scope,
                    completion_criteria=draft.completion_criteria,
                    evidence_refs=tuple(dict.fromkeys(draft.source_refs)),
                    assignee_id=assignment.assignee_id, due_at=assignment.due_at, created_at=now)
    tx.stage_proposal(action, Event(type="ACTION_PROPOSED", actor_id=None,
                                    incident_id=incident_id, action_id=action.id, occurred_at=now,
                                    payload={"run_id": str(run_id), "draft_id": str(draft_id)}))
    return {"action_id": str(action.id), "created": True, "action_version": action.version}


class ActionApplication:
    def __init__(self, transaction: TransactionFactory,
                 clock: Callable[[], datetime] = lambda: datetime.now(UTC)):
        self.transaction = transaction
        self.clock = clock

    def execute(self, principal: Principal, action_id: UUID, key: str,
                command: ActionCommand, meta: dict) -> CommandResponse:
        if not key.strip():
            raise ActionError(422, "VALIDATION_ERROR", "Idempotency-Key가 필요합니다.")
        suffix = "approval-decisions" if isinstance(command, ApprovalCommand) else (
            "completion" if isinstance(command, CompletionCommand) else "start")
        payload = command.model_dump(mode="json")
        fingerprint = canonical_hash({"method": "POST", "route": f"/api/v1/actions/{action_id}/{suffix}",
                                      "body": payload})
        with self.transaction() as tx:
            tx.assert_action_scope(action_id, principal.site_id)
            cached = tx.reserve_command(principal, key, fingerprint)
            if cached:
                return cached.model_copy(update={"replayed": True})
            context = tx.lock_context(action_id=action_id)
            try:
                transition = decide(context, principal, action_id, command, self.clock())
            except ActionError as exc:
                # decide is pure: rejection cannot leave a partial approval or result.
                response = CommandResponse(status=exc.status, body=exc.envelope(meta))
                if exc.code == "INCIDENT_RESOLVED":
                    tx.append_event(Event(type="rejected_input", actor_id=principal.user_id,
                                          incident_id=context.incident.id, action_id=action_id,
                                          occurred_at=self.clock(),
                                          payload={"command": suffix, "input": payload}))
            else:
                # Persistence/readiness errors escape; the UoW must roll everything back.
                tx.save_transition(context, transition)
                response = CommandResponse(status=200, body={"data": transition.data, "meta": meta})
            tx.finish_command(principal, key, response)
            return response
