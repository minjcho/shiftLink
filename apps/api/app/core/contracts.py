from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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


class SessionView(BaseModel):
    """F1 session wire format, generated for the browser from this definition."""
    model_config = ConfigDict(extra="forbid")
    user_id: UUID
    site_id: UUID
    role: Literal["worker", "supervisor"]
    display_name: str
    shift_occurrence_id: UUID
    duties: list[str]
