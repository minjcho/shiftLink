"""F2's existing HTTP contract for OpenAPI; F0 composes the shared detail DTO."""

from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import AwareDatetime

from .models import FrozenModel, Version


class ActionResult(FrozenModel):
    action_id: UUID
    action_status: Literal["PROPOSED", "APPROVED", "IN_PROGRESS", "COMPLETED", "REJECTED"]
    action_version: Version
    incident_status: Literal["OPEN", "INVESTIGATING", "ACTION_REQUIRED", "IN_PROGRESS",
                             "PENDING_VERIFICATION", "RESOLVED"]
    incident_version: Version


class ApprovalResult(ActionResult):
    approval_id: UUID
    payload_hash: str
    review_required: bool


class StartResult(ActionResult):
    started_at: AwareDatetime


class CompletionResult(ActionResult):
    result_message_id: UUID
    completion_evidence_id: UUID
    verification_ready: bool
    unmet_requirements: tuple[str, ...]


T = TypeVar("T")


class SuccessEnvelope(FrozenModel, Generic[T]):
    data: T
    meta: dict
