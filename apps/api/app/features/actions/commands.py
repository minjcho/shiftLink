from typing import Literal
from uuid import UUID

from .models import FrozenModel, Text, Version


class StartCommand(FrozenModel):
    expected_version: Version
    expected_incident_version: Version


class ApprovalCommand(StartCommand):
    decision: Literal["APPROVE", "REJECT"]
    reason: Text


class CompletionCommand(StartCommand):
    result: Text
    evidence_refs: tuple[UUID, ...] = ()


ActionCommand = ApprovalCommand | CompletionCommand | StartCommand
