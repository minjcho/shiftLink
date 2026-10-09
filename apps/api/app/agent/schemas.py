"""The model-facing contract contains no actor or authorization overrides."""
from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
SourceIds = Annotated[list[UUID], Field(max_length=50)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Decision(StrEnum):
    ASK_USER = "ASK_USER"
    PROPOSE_ACTION = "PROPOSE_ACTION"
    WAIT_EXISTING = "WAIT_EXISTING"
    REQUEST_VERIFICATION = "REQUEST_VERIFICATION"
    BLOCKED = "BLOCKED"


class Fact(StrictModel):
    text: Text
    kind: Literal["HUMAN_STATEMENT", "RECORD", "SYSTEM_STATE"]
    source_refs: SourceIds


class Question(StrictModel):
    question: Text
    purpose_code: Literal["VERIFY_SCOPE", "VERIFY_RESULT"]
    target_user_id: UUID
    source_refs: Annotated[list[UUID], Field(min_length=1, max_length=50)]


class FinalDecision(StrictModel):
    facts: Annotated[list[Fact], Field(max_length=40)]
    hypotheses: Annotated[list[Text], Field(max_length=20)]
    missing_information: Annotated[list[Text], Field(max_length=20)]
    decision: Decision
    questions: Annotated[list[Question], Field(max_length=2)]
    selected_draft_id: UUID | None
    existing_request_ids: Annotated[list[UUID], Field(max_length=100)]
    existing_action_ids: Annotated[list[UUID], Field(max_length=100)]
    source_refs: SourceIds
    reason: Text

    @model_validator(mode="after")
    def branch_contract(self):
        if self.decision == Decision.ASK_USER:
            if not self.questions or self.selected_draft_id is not None:
                raise ValueError("ASK_USER requires 1-2 questions and no selected draft")
        elif self.questions:
            raise ValueError("Only ASK_USER can contain new questions")
        if self.decision == Decision.PROPOSE_ACTION:
            if self.selected_draft_id is None:
                raise ValueError("PROPOSE_ACTION requires a selected draft")
        elif self.selected_draft_id is not None:
            raise ValueError("Only PROPOSE_ACTION can select a draft")
        if self.decision == Decision.WAIT_EXISTING and not (
            self.existing_request_ids or self.existing_action_ids
        ):
            raise ValueError("WAIT_EXISTING requires an existing request or action")
        return self


class EquipmentArguments(StrictModel):
    equipment_id: UUID


class SearchArguments(EquipmentArguments):
    query: ShortText


class ProposalArguments(StrictModel):
    scope: Text
    completion_criteria: Annotated[list[Text], Field(min_length=1, max_length=20)]
    source_refs: Annotated[list[UUID], Field(min_length=1, max_length=50)]


TOOL_ARGUMENTS = {
    "get_equipment_context": EquipmentArguments,
    "search_documents": SearchArguments,
    "search_similar_incidents": SearchArguments,
    "propose_action": ProposalArguments,
}

TOOL_DESCRIPTIONS = {
    "get_equipment_context": "Read the incident equipment, recorded logs and server-assigned maintenance users.",
    "search_documents": "Search approved SOP passages applicable to the incident equipment at this site.",
    "search_similar_incidents": "Find resolved cases at this site. Other equipment cases are comparison records, not current observations.",
    "propose_action": "Save a run-local draft with scope, completion criteria and observed source IDs. This does not create an Action or approve work.",
}


def tool_definitions() -> list[dict]:
    return [
        {"type": "function", "name": name, "description": TOOL_DESCRIPTIONS[name],
         "parameters": model.model_json_schema(), "strict": True}
        for name, model in TOOL_ARGUMENTS.items()
    ]


def final_format() -> dict:
    return {"type": "json_schema", "name": "investigation_decision", "strict": True,
            "schema": FinalDecision.model_json_schema()}
