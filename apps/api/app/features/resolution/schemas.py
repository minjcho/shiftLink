from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VerificationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["RESOLVE", "RETURN"]
    expected_version: int = Field(ge=1, strict=True)
    notes: str = Field(min_length=1, max_length=20000)
    evidence_refs: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator("notes")
    @classmethod
    def meaningful_notes(cls, value):
        if not value.strip():
            raise ValueError("검토 사유를 입력해 주세요.")
        return value


class VerificationResult(BaseModel):
    incident_id: UUID
    incident_status: Literal["RESOLVED", "INVESTIGATING"]
    incident_version: int = Field(ge=1)
    verification_id: UUID
    case_id: UUID | None
    resolved_at: str | None


class VerificationResponse(BaseModel):
    data: VerificationResult
    meta: dict
