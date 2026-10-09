"""Feature-local immutable projections; F0 maps its persisted models into these.

These are not a second shared ORM/schema. Untrusted requests use commands.py.
"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field


def nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("내용을 입력해 주세요.")
    return value  # Preserve the author's exact text.


Text = Annotated[str, AfterValidator(nonblank)]
Version = Annotated[int, Field(strict=True, ge=1)]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Principal(FrozenModel):
    user_id: UUID
    site_id: UUID
    role: Literal["worker", "supervisor"]


class IncidentView(FrozenModel):
    id: UUID
    site_id: UUID
    equipment_id: UUID
    owner_id: UUID
    status: Literal["OPEN", "INVESTIGATING", "ACTION_REQUIRED", "IN_PROGRESS",
                    "PENDING_VERIFICATION", "RESOLVED"]
    version: Version
    review_required: bool = False
    review_reason: str | None = None


class Action(FrozenModel):
    id: UUID
    incident_id: UUID
    trigger_event_id: UUID
    proposed_by_run_id: UUID
    title: Text
    scope: Text
    completion_criteria: Annotated[tuple[Text, ...], Field(min_length=1)]
    assignee_id: UUID
    due_at: AwareDatetime
    evidence_refs: Annotated[tuple[UUID, ...], Field(min_length=1)]
    action_slot: Literal["MAIN_FOLLOWUP"] = "MAIN_FOLLOWUP"
    action_generation: Literal[1] = 1
    is_required: Literal[True] = True
    status: Literal["PROPOSED", "APPROVED", "IN_PROGRESS", "COMPLETED", "REJECTED"] = "PROPOSED"
    revision: Literal[1] = 1
    version: Version = 1
    result_message_id: UUID | None = None
    completion_evidence_id: UUID | None = None
    created_at: AwareDatetime
    started_at: AwareDatetime | None = None
    completed_at: AwareDatetime | None = None


class Approval(FrozenModel):
    id: UUID
    action_id: UUID
    action_revision: int
    decision: Literal["APPROVE", "REJECT"]
    reason: Text
    payload_hash: str
    approved_payload_snapshot: dict
    actor_id: UUID
    created_at: AwareDatetime


class MessageView(FrozenModel):
    id: UUID
    site_id: UUID
    incident_id: UUID
    author_id: UUID
    kind: str
    text: Text
    received_at: AwareDatetime
    action_id: UUID | None = None
    reply_to_request_id: UUID | None = None


class EvidenceView(FrozenModel):
    id: UUID
    site_id: UUID
    incident_id: UUID
    source_type: Literal["message", "log", "sop", "case", "completion_report"]
    source_id: UUID
    source_version: Text
    excerpt: Text
    content_hash: str
    captured_at: AwareDatetime
    # Server projection of F0's applicability/document approval policy, never client input.
    applicable: bool
    document_approved: bool | None = None


class RequestView(FrozenModel):
    id: UUID
    incident_id: UUID
    target_user_id: UUID
    is_required: bool
    status: Literal["OPEN", "ANSWERED"]
    response_message_id: UUID | None = None


class ActionContext(FrozenModel):
    incident: IncidentView
    actions: tuple[Action, ...] = ()
    approvals: tuple[Approval, ...] = ()
    messages: tuple[MessageView, ...] = ()
    evidence: tuple[EvidenceView, ...] = ()
    requests: tuple[RequestView, ...] = ()


class DraftView(FrozenModel):
    id: UUID
    run_id: UUID
    incident_id: UUID
    input_version: Version
    scope: Text
    completion_criteria: Annotated[tuple[Text, ...], Field(min_length=1)]
    source_refs: Annotated[tuple[UUID, ...], Field(min_length=1)]


class RunView(FrozenModel):
    id: UUID
    incident_id: UUID  # Joined from Job by the adapter.
    input_version: Version
    trigger_event_id: UUID
    status: str


class Assignment(FrozenModel):
    """Resolved by F0 from equipment/shift assignments and the server due-date policy."""

    assignee_id: UUID
    due_at: AwareDatetime


class Event(FrozenModel):
    type: str
    actor_id: UUID | None
    incident_id: UUID
    action_id: UUID
    occurred_at: AwareDatetime
    payload: dict = Field(default_factory=dict)


class Transition(FrozenModel):
    context: ActionContext
    event: Event
    data: dict


class CommandResponse(FrozenModel):
    status: int
    body: dict  # Entire original envelope, including its request_id, for exact replay.
    replayed: bool = False
