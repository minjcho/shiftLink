from __future__ import annotations

from copy import deepcopy
from uuid import UUID

from sqlalchemy import select

from app.core.models import Action, ActionDraft, Approval, Evidence, Event, Incident, Job, Request
from app.core.ports import FeaturePorts
from app.core.transactions import bump_incident, enqueue_job, new_event
from .context import RunIdentity, allowed_targets
from .jobs import LostLease, db_now, fence, lock_incident_graph, persist_execution
from .schemas import Decision, FinalDecision


class DecisionRejected(Exception):
    def __init__(self, message, code="DECISION_INVALID", details=None):
        super().__init__(message)
        self.code = code
        self.details = details


def validate_decision(tx, identity, incident, run, dto: FinalDecision):
    observed = set(run.metadata_json.get("observed_source_ids", []))
    refs = {str(ref) for ref in dto.source_refs}
    refs.update(str(ref) for fact in dto.facts for ref in fact.source_refs)
    refs.update(str(ref) for question in dto.questions for ref in question.source_refs)
    draft = None
    if dto.selected_draft_id is not None:
        draft = tx.get(ActionDraft, str(dto.selected_draft_id))
        if (draft is None or draft.run_id != identity.run_id or draft.incident_id != incident.id
                or draft.input_version != identity.input_version):
            raise DecisionRejected("The selected draft does not belong to this run and input version")
        refs.update(draft.payload_json.get("source_refs", []))
    if not refs.issubset(observed):
        raise DecisionRejected("The decision cites a source not observed in this run", "EVIDENCE_INVALID")
    evidence = list(tx.scalars(select(Evidence).where(Evidence.id.in_(refs)))) if refs else []
    if len(evidence) != len(refs) or any(e.site_id != incident.site_id or e.incident_id != incident.id for e in evidence):
        raise DecisionRejected("The decision cites an invalid incident source", "EVIDENCE_INVALID")
    for request_id in dto.existing_request_ids:
        request = tx.get(Request, str(request_id))
        if request is None or request.incident_id != incident.id or request.status != "OPEN":
            raise DecisionRejected("The referenced request is not an open request in this incident")
    for action_id in dto.existing_action_ids:
        action = tx.get(Action, str(action_id))
        if action is None or action.incident_id != incident.id:
            raise DecisionRejected("The referenced action belongs to another incident or does not exist")
    targets = allowed_targets(tx, incident)
    if any(str(question.target_user_id) not in targets for question in dto.questions):
        raise DecisionRejected("The question target is not a currently allowed maintenance user")
    if incident.status == "RESOLVED":
        raise DecisionRejected("A resolved incident cannot receive investigation effects", "INCIDENT_RESOLVED")
    if incident.review_required and dto.decision != Decision.BLOCKED:
        raise DecisionRejected("A rejected incident requires human follow-up", "REVIEW_REQUIRED")
    return draft


def _queue_latest_if_needed(tx, incident, identity):
    if incident.status == "RESOLVED" or incident.review_required:
        return
    current = tx.scalar(select(Job.id).where(Job.incident_id == incident.id,
                                            Job.id != identity.job_id, Job.status.in_(["QUEUED", "RUNNING"])))
    if current:
        return
    event = tx.scalar(select(Event).where(Event.incident_id == incident.id)
                      .order_by(Event.occurred_at.desc(), Event.id.desc()).limit(1))
    if event is not None:
        existing = tx.scalar(select(Job.id).where(Job.incident_id == incident.id,
                                                  Job.trigger_event_id == event.id,
                                                  Job.job_kind == "INVESTIGATE"))
        if existing is None:
            enqueue_job(tx, incident, event)


def finalize(session_factory, identity: RunIdentity, execution, ports: FeaturePorts, *, now=None) -> dict:
    if execution.final is None:
        raise DecisionRejected("There is no valid final decision")
    dto = execution.final
    with session_factory.begin() as tx:
        incident = lock_incident_graph(tx, identity)
        job, run = fence(tx, identity, now=now)
        if incident.version != identity.input_version:
            persist_execution(run, execution)
            run.status, job.status = "SUPERSEDED", "SUPERSEDED"
            run.finished_at, job.updated_at = db_now(tx, now), db_now(tx, now)
            job.lease_token = None
            _queue_latest_if_needed(tx, incident, identity)
            return {"status": "SUPERSEDED", "run_id": run.id, "job_id": job.id}
        selected_draft = validate_decision(tx, identity, incident, run, dto)
        request_ids, action_ids = [], [str(value) for value in dto.existing_action_ids]
        event = None
        run_status = "SUCCEEDED"
        if dto.decision == Decision.ASK_USER:
            created = []
            for question in dto.questions:
                target = str(question.target_user_id)
                request = tx.scalar(select(Request).where(
                    Request.incident_id == incident.id, Request.target_user_id == target,
                    Request.purpose_code == question.purpose_code, Request.status == "OPEN"))
                if request is None:
                    request = Request(incident_id=incident.id, target_user_id=target,
                                      purpose_code=question.purpose_code, question=question.question,
                                      is_required=True, evidence_refs=[str(ref) for ref in question.source_refs])
                    tx.add(request)
                    tx.flush()
                    created.append(request.id)
                request_ids.append(request.id)
            if not request_ids:
                raise DecisionRejected("WAITING_INPUT requires a persisted open request")
            if created:
                event = new_event(tx, incident, "QUESTIONS_CREATED", related_ids={"request_ids": created, "run_id": run.id})
            run_status = "WAITING_INPUT"
        elif dto.decision == Decision.PROPOSE_ACTION:
            previous = {action.id: {column.name: deepcopy(getattr(action, column.name))
                                    for column in Action.__table__.columns}
                        for action in tx.scalars(select(Action).where(Action.incident_id == incident.id))}
            previous_approvals = {approval.id: {column.name: deepcopy(getattr(approval, column.name))
                                               for column in Approval.__table__.columns}
                                  for approval in tx.scalars(select(Approval).where(Approval.action_id.in_(previous)))}
            parent_before = (incident.version, incident.status, incident.owner_id, incident.review_required)
            result = ports.finalize_action_proposal(
                tx, incident_id=incident.id, run_id=run.id, input_version=identity.input_version,
                draft_id=str(dto.selected_draft_id), trigger_event_id=job.trigger_event_id,
            )
            tx.flush()
            if (not isinstance(result, dict) or set(result) != {"action_id", "created", "action_version"}
                    or type(result["created"]) is not bool or type(result["action_version"]) is not int
                    or not isinstance(result["action_id"], str)):
                raise DecisionRejected("The Action boundary returned an invalid result shape")
            try:
                UUID(result["action_id"])
            except ValueError as exc:
                raise DecisionRejected("The Action boundary returned an invalid ID") from exc
            current_ids = set(tx.scalars(select(Action.id).where(Action.incident_id == incident.id)))
            expected_ids = set(previous) | {result["action_id"]}
            if current_ids != expected_ids:
                raise DecisionRejected("The Action boundary changed more than the returned Action")
            action = tx.get(Action, result["action_id"])
            if (action is None or action.incident_id != incident.id or action.action_generation != 1
                    or action.version != result["action_version"]):
                raise DecisionRejected("The Action boundary did not return a persisted generation-one Action")
            if parent_before != (incident.version, incident.status, incident.owner_id, incident.review_required):
                raise DecisionRejected("The Action boundary changed caller-owned incident state")
            for action_id, before in previous.items():
                current = tx.get(Action, action_id)
                if current is None or any(getattr(current, key) != value for key, value in before.items()):
                    raise DecisionRejected("The Action boundary changed an existing Action")
            for approval_id, before in previous_approvals.items():
                current = tx.get(Approval, approval_id)
                if current is None or any(getattr(current, key) != value for key, value in before.items()):
                    raise DecisionRejected("The Action boundary changed an existing approval")
            if result["created"] == (action.id in previous):
                raise DecisionRejected("The Action boundary misreported creation versus reuse")
            if result["created"]:
                proposal = selected_draft.payload_json
                if (action.status != "PROPOSED" or not action.is_required or action.action_slot != "MAIN_FOLLOWUP"
                        or action.assignee_id not in allowed_targets(tx, incident)
                        or action.scope != proposal["scope"] or action.completion_criteria != proposal["completion_criteria"]
                        or set(action.evidence_refs) != set(proposal["source_refs"])
                        or action.proposed_by_run_id != run.id or action.trigger_event_id != job.trigger_event_id
                        or tx.scalar(select(Approval.id).where(Approval.action_id == action.id).limit(1))):
                    raise DecisionRejected("A new Action violated the validated proposal or server assignment contract")
                incident.status = "ACTION_REQUIRED"
                event = new_event(tx, incident, "ACTION_PROPOSAL_FINALIZED", related_ids={"action_id": action.id, "run_id": run.id})
            action_ids = [action.id]
        elif dto.decision == Decision.REQUEST_VERIFICATION:
            readiness = ports.evaluate_resolution_readiness(tx, incident=incident)
            if not isinstance(readiness, dict) or type(readiness.get("ready")) is not bool:
                raise DecisionRejected("The readiness boundary returned an invalid result", "READINESS_INVALID")
            if not readiness["ready"]:
                missing = readiness.get("unmet_requirements", readiness.get("missing", []))
                if (not isinstance(missing, list) or len(missing) > 20
                        or any(not isinstance(item, str) or not 0 < len(item) <= 200 for item in missing)):
                    raise DecisionRejected("The readiness boundary returned invalid unmet requirements", "READINESS_INVALID")
                raise DecisionRejected("The incident does not satisfy resolution readiness", "READINESS_NOT_MET",
                                       {"unmet_requirements": missing})
            if incident.status != "PENDING_VERIFICATION":
                incident.status = "PENDING_VERIFICATION"
                event = new_event(tx, incident, "VERIFICATION_REQUESTED", related_ids={"run_id": run.id})
        elif dto.decision == Decision.WAIT_EXISTING:
            request_ids = [str(value) for value in dto.existing_request_ids]
        # BLOCKED records only analysis; it cannot silently clear review_required.
        incident.analysis = {"run_id": run.id, "base_version": identity.input_version,
                             "applied_version": incident.version + (1 if event is not None else 0), "decision": dto.decision.value,
                             "facts": [fact.model_dump(mode="json") for fact in dto.facts],
                             "hypotheses": dto.hypotheses, "missing_information": dto.missing_information,
                             "source_refs": [str(ref) for ref in dto.source_refs], "reason": dto.reason}
        if event is not None:
            bump_incident(tx, incident, event, ports)
        # Recheck expiry immediately before authoritative writes, including after injected ports.
        fence(tx, identity, now=now)
        persist_execution(run, execution)
        run.status, run.finished_at, run.applied_version = run_status, db_now(tx, now), incident.version
        run.metadata_json = {**run.metadata_json, "request_ids": request_ids, "action_ids": action_ids}
        job.status, job.last_error, job.updated_at, job.lease_token = "SUCCEEDED", None, run.finished_at, None
        return {"status": run_status, "job_id": job.id, "run_id": run.id,
                "request_ids": request_ids, "action_ids": action_ids, "incident_version": incident.version}
