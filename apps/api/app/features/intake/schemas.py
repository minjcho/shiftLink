from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DemoSessionBody(StrictBody):
    account_key: Literal["reporter", "maintainer", "outgoing_supervisor", "incoming_supervisor"]


class ReportBody(StrictBody):
    equipment_id: UUID
    text: str = Field(min_length=1, max_length=20000)
    observed_at: datetime | None = None

    @field_validator("text")
    @classmethod
    def meaningful_text(cls, value):
        if not value.strip():
            raise ValueError("원문을 입력해 주세요.")
        return value  # Preserve user's exact original, including whitespace.

    @field_validator("observed_at")
    @classmethod
    def aware_timestamp(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("observed_at requires an explicit timezone")
        return value


class MessageBody(StrictBody):
    text: str = Field(min_length=1, max_length=20000)
    expected_version: int = Field(ge=1)
    reply_to_request_id: UUID | None = None
    observed_at: datetime | None = None
    correction_of: UUID | None = None
    meaningful_text = field_validator("text")(ReportBody.meaningful_text.__func__)
    aware_timestamp = field_validator("observed_at")(ReportBody.aware_timestamp.__func__)


class RetryBody(StrictBody):
    pass
