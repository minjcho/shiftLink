from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateHandoverBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_shift_occurrence_id: UUID
    to_shift_occurrence_id: UUID


class AcknowledgeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    snapshot_token: str = Field(min_length=1, max_length=128)
    expected_version: int = Field(ge=1)
