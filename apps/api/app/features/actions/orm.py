"""F2 bridge to the authoritative F1 ORM and caller-owned transaction.

No engines, commits, receipt reservations, or model calls live here. HTTP uses
core.transactions.execute_command; the worker uses its finalizer transaction.
"""
from datetime import timedelta
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select

from app.core import models as db
from app.core.errors import DomainError, not_found
from app.core.transactions import bump_incident, new_event
from . import models as view
from .commands import ApprovalCommand, CompletionCommand
from .domain import decide
from .errors import ActionError
from .service import finalize_action_proposal
from ..resolution.readiness import evaluate_resolution_readiness


def project(model, row, **overrides):
    values = {name: getattr(row, name) for name in model.model_fields if hasattr(row, name)}
    return model.model_validate(values | overrides)


def values(model):
    """Keep aware timestamps while translating UUIDs/tuples to ORM string/JSON values."""
    def convert(value):
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, (tuple, list)):
            return [convert(item) for item in value]
        if isinstance(value, dict):
            return {key: convert(item) for key, item in value.items()}
        return value
    return convert(model.model_dump())


def load_context(tx, incident):
    """Read complete collections, never the paginated UI or bounded model context."""
    actions = list(tx.scalars(select(db.Action).where(db.Action.incident_id == incident.id).order_by(db.Action.id)))
    approvals = tx.scalars(select(db.Approval).where(db.Approval.action_id.in_([a.id for a in actions])))
    evidence = tx.scalars(select(db.Evidence).where(db.Evidence.incident_id == incident.id))
    return view.ActionContext(
        incident=project(view.IncidentView, incident),
        actions=tuple(project(view.Action, row) for row in actions),
        approvals=tuple(project(view.Approval, row) for row in approvals),
        messages=tuple(project(view.MessageView, row) for row in tx.scalars(
            select(db.Message).where(db.Message.incident_id == incident.id))),
        requests=tuple(project(view.RequestView, row) for row in tx.scalars(
            select(db.Request).where(db.Request.incident_id == incident.id))),
        evidence=tuple(project(view.EvidenceView, row,
            applicable=(row.site_id == incident.site_id and (
                row.equipment_id == incident.equipment_id or
                (row.source_type == "case" and row.applicability.get("comparison_only") is True))
                and (row.source_type != "sop" or incident.equipment_id in row.applicability.get("equipment_ids", []))),
            document_approved=row.document_approval == "approved") for row in evidence),
    )


def lock_context(tx, incident_id):
    incident = tx.scalar(select(db.Incident).where(db.Incident.id == str(incident_id)).with_for_update())
    if incident is None:
        raise not_found()
    for model in (db.Action, db.Request):
        list(tx.scalars(select(model).where(model.incident_id == incident.id).order_by(model.id).with_for_update()))
    return incident


def readiness(tx, *, incident):
    # A malformed persisted prerequisite is not permission to close an incident.
    try:
        result = evaluate_resolution_readiness(load_context(tx, incident))
    except (ValidationError, ValueError):
        return {"ready": False, "unmet_requirements": ["INVALID_RESOLUTION_INPUT"]}
    return {"ready": result.verification_ready, "unmet_requirements": list(result.unmet_requirements)}


class ProposalAdapter:
    def __init__(self, tx):
        self.tx = tx

    def lock_context(self, incident_id):
        # F1 already holds the entire graph before its Job fence. Re-locking
        # child rows here would obscure the shared lock order.
        incident = self.tx.get(db.Incident, str(incident_id))
        if incident is None:
            raise not_found()
        return load_context(self.tx, incident)

    def load_draft(self, draft_id):
        row = self.tx.get(db.ActionDraft, str(draft_id))
        if row is None:
            raise ActionError(422, "VALIDATION_ERROR", "작업 후보가 없습니다.")
        return project(view.DraftView, row, **{
            key: row.payload_json.get(key) for key in ("scope", "completion_criteria", "source_refs")})

    def load_run(self, run_id):
        row = self.tx.get(db.AgentRun, str(run_id))
        job = self.tx.get(db.Job, row.job_id) if row else None
        if row is None or job is None:
            raise ActionError(422, "VALIDATION_ERROR", "조사 실행이 없습니다.")
        return project(view.RunView, row, incident_id=job.incident_id)

    def resolve_assignment(self, context):
        incident = self.tx.get(db.Incident, str(context.incident.id))
        equipment = self.tx.get(db.Equipment, incident.equipment_id)
        assignee = self.tx.scalar(select(db.User).join(db.ShiftAssignment,
            db.ShiftAssignment.user_id == db.User.id).where(
                db.User.id == equipment.default_maintainer_id, db.User.site_id == incident.site_id,
                db.User.enabled.is_(True), db.ShiftAssignment.shift_occurrence_id == incident.owner_shift_occurrence_id,
                db.ShiftAssignment.duty == "MAINTENANCE"))
        if assignee is None:
            raise ActionError(422, "SHIFT_ASSIGNMENT_MISSING", "현재 교대의 정비 담당자가 필요합니다.")
        # Phase 1 demo deadline, determined by the server rather than model output.
        return view.Assignment(assignee_id=assignee.id, due_at=db.utcnow() + timedelta(hours=1))

    def stage_proposal(self, action):
        self.tx.add(db.Action(**values(action)))
        self.tx.flush()


def finalize_proposal(tx, **kwargs):
    try:
        return finalize_action_proposal(ProposalAdapter(tx), **{
            key: UUID(value) if key.endswith("_id") and isinstance(value, str) else value
            for key, value in kwargs.items()})
    except ActionError as error:
        raise DomainError(error.status, error.code, error.message,
                          current_version=error.current_version, details=error.details) from error
    except ValidationError as error:
        raise DomainError(422, "VALIDATION_ERROR", "작업 후보 또는 근거 자료가 올바르지 않습니다.") from error


def assert_scope(tx, principal, action_id):
    incident_id = tx.scalar(select(db.Action.incident_id).join(db.Incident).where(
        db.Action.id == str(action_id), db.Incident.site_id == principal.site_id))
    if incident_id is None:
        raise not_found()
    return incident_id


def save_transition(tx, incident, before, transition, ports):
    after = transition.context
    for model, previous, updated in (
        (db.Approval, before.approvals, after.approvals),
        (db.Message, before.messages, after.messages),
        (db.Evidence, before.evidence, after.evidence),
    ):
        known = {row.id for row in previous}
        for row in updated:
            if row.id in known:
                continue
            data = values(row)
            if model is db.Evidence:
                data.pop("applicable")
                data.pop("document_approved")
                data.update(equipment_id=incident.equipment_id,
                    source_location=f"messages/{row.source_id}",
                    applicability={"author_id": str(transition.event.actor_id),
                                   "received_at": transition.event.occurred_at.isoformat()})
            tx.add(model(**data))
        tx.flush()
    for row in after.actions:
        old = next(a for a in before.actions if a.id == row.id)
        target = tx.get(db.Action, str(row.id))
        for name, value in values(row).items():
            if getattr(old, name) != getattr(row, name):
                setattr(target, name, value)
    incident.status = after.incident.status
    incident.review_required = after.incident.review_required
    incident.review_reason = after.incident.review_reason
    event = new_event(tx, incident, transition.event.type, str(transition.event.actor_id),
                      payload=transition.event.payload,
                      related_ids={"action_id": str(transition.event.action_id)})
    bump_incident(tx, incident, event, ports)
    if incident.version != after.incident.version:
        raise RuntimeError("F2 parent version must advance exactly once")


def execute(tx, principal, action_id, body, ports):
    incident_id = assert_scope(tx, principal, action_id)
    incident = lock_context(tx, incident_id)
    try:
        before = load_context(tx, incident)
    except ValidationError as error:
        raise DomainError(409, "INVALID_STATE", "저장된 작업 자료를 확인해 주세요.") from error
    actor = view.Principal(user_id=principal.user_id, site_id=principal.site_id, role=principal.role)
    try:
        transition = decide(before, actor, UUID(str(action_id)), body, db.utcnow())
    except ActionError as error:
        if error.code == "INCIDENT_RESOLVED":
            suffix = "approval-decisions" if isinstance(body, ApprovalCommand) else (
                "completion" if isinstance(body, CompletionCommand) else "start")
            new_event(tx, incident, "rejected_input", principal.user_id,
                payload={"command": suffix, "input": body.model_dump(mode="json")},
                related_ids={"action_id": str(action_id)})
        return error.status, {"error": error.envelope({})["error"]}
    save_transition(tx, incident, before, transition, ports)
    return 200, {"data": transition.data}
