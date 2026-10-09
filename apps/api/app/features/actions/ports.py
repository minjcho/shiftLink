"""F0 integration contract. There is deliberately no in-memory production adapter."""

from contextlib import AbstractContextManager
from typing import Protocol
from uuid import UUID

from .models import (Action, ActionContext, Assignment, CommandResponse, DraftView,
                     Event, Principal, RunView, Transition)


class ActionTransaction(Protocol):
    def assert_action_scope(self, action_id: UUID, site_id: UUID) -> None:
        """Check immutable Action -> Incident -> site relation, or raise 404."""
        ...

    def reserve_command(self, principal: Principal, key: str, fingerprint: str) -> CommandResponse | None:
        """F0 receipt: exact replay first, else reserve (site, actor, key).

        Conflicting payload -> IDEMPOTENCY_CONFLICT; in-flight -> COMMAND_IN_PROGRESS.
        Reservation and response share the transaction; rollback releases reservation.
        """
        ...

    def lock_context(self, incident_id: UUID | None = None, *, action_id: UUID | None = None) -> ActionContext:
        """Load complete context: lock Incident first, then related rows in ID order.

        All sibling writers must follow the same Incident lock discipline.
        No filtered/paginated subset of required questions, approvals, or evidence.
        """
        ...

    def save_transition(self, before: ActionContext, transition: Transition) -> None:
        """Update changed Incident/Action; append only new approval/result/evidence/event.

        Apply F0/F3 handover revision hook in this same transaction, then flush.
        Never replace/delete the old collections or commit here.
        """
        ...

    def append_event(self, event: Event) -> None: ...

    def finish_command(self, principal: Principal, key: str, response: CommandResponse) -> None: ...

    def load_draft(self, draft_id: UUID) -> DraftView: ...

    def load_run(self, run_id: UUID) -> RunView: ...

    def resolve_assignment(self, context: ActionContext) -> Assignment:
        """Server equipment/shift mapping; no mapping -> 422 SHIFT_ASSIGNMENT_MISSING."""
        ...

    def stage_proposal(self, action: Action, event: Event) -> None:
        """Insert Action/event; set Incident ACTION_REQUIRED, but DO NOT bump its version.

        Caller F1 performs version +1, handover revision, final Job/Run and lease check
        atomically. Caller must roll back every staged row if the final check fails.
        """
        ...


class TransactionFactory(Protocol):
    def __call__(self) -> AbstractContextManager[ActionTransaction]:
        """Commit on normal exit; roll back every change on any exception."""
        ...
