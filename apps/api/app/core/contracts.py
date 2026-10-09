from enum import StrEnum
from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, AwareDatetime, Field


class IncidentStatus(StrEnum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    RESOLVED = "RESOLVED"


class ActionStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


class Principal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    user_id: UUID
    site_id: UUID
    role: Literal["worker", "supervisor"]


class SessionView(Principal):
    display_name: str
    site_name: str
    shift_occurrence_id: UUID
    duties: list[str]


T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    data: T
    meta: dict


class MessageDetail(BaseModel):
    id: UUID
    kind: Literal["REPORT", "NOTE", "REPLY", "ACTION_RESULT", "CORRECTION"]
    text: str
    author_id: UUID
    received_at: AwareDatetime
    reply_to_request_id: UUID | None
    action_id: UUID | None


class RequestDetail(BaseModel):
    id: UUID
    target_user_id: UUID
    question: str
    purpose_code: Literal["VERIFY_SCOPE", "VERIFY_RESULT"]
    is_required: bool
    status: Literal["OPEN", "ANSWERED"]
    response_message_id: UUID | None
    version: int = Field(ge=1)


class ActionDetail(BaseModel):
    id: UUID
    status: ActionStatus
    version: int = Field(ge=1)
    revision: int = Field(ge=1)
    title: str
    scope: str
    completion_criteria: list[str]
    evidence_refs: list[UUID]
    assignee_id: UUID
    due_at: AwareDatetime
    is_required: bool
    result_message_id: UUID | None
    completion_evidence_id: UUID | None


class ApprovalDetail(BaseModel):
    id: UUID
    action_id: UUID
    action_revision: int
    decision: Literal["APPROVE", "REJECT"]
    reason: str
    payload_hash: str
    approved_payload_snapshot: dict
    actor_id: UUID
    created_at: AwareDatetime


class EvidenceDetail(BaseModel):
    id: UUID
    source_type: Literal["message", "log", "sop", "case", "completion_report"]
    source_id: UUID
    source_version: str
    excerpt: str
    content_hash: str
    captured_at: AwareDatetime


class IncidentDetail(BaseModel):
    """One authoritative read, shared by all panels; F1 provides the scoped query.

    Feature-owned analysis/handover/job/event payloads are expanded by their owner
    in a reviewed contract change. Required collections must never be filled with
    empty defaults to hide an unavailable feature query.
    """
    id: UUID
    display_id: str
    equipment_id: UUID
    status: IncidentStatus
    version: int = Field(ge=1)
    owner_id: UUID
    review_required: bool
    review_reason: str | None
    waiting_for_input: bool
    messages: list[MessageDetail]
    requests: list[RequestDetail]
    actions: list[ActionDetail]
    approvals: list[ApprovalDetail]
    evidence: list[EvidenceDetail]
    analysis: dict | None
    handover: dict | None
    recent_events: list[dict]
    latest_job: dict | None
    allowed_commands: list[str]
