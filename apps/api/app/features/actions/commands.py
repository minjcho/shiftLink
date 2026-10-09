from typing import Literal
from uuid import UUID

from pydantic import Field

from .models import FrozenModel, Text, Version


class StartCommand(FrozenModel):
    expected_version: Version
    expected_incident_version: Version


class ApprovalCommand(StartCommand):
    decision: Literal["APPROVE", "REJECT"]
    reason: Text


class CompletionCommand(StartCommand):
    result: Text = Field(max_length=20000)
    evidence_refs: tuple[UUID, ...] = Field(default=(), max_length=100)


ActionCommand = ApprovalCommand | CompletionCommand | StartCommand
