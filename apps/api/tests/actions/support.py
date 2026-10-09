from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.features.actions.errors import ActionError
from app.features.actions.integrity import content_hash
from app.features.actions.models import (Action, ActionContext, Assignment, DraftView,
                                        EvidenceView, IncidentView, Principal, RunView)


def uid(number):
    return UUID(f"00000000-0000-4000-8000-{number:012d}")


NOW = datetime(2026, 10, 9, 3, tzinfo=UTC)
OWNER = Principal(user_id=uid(203), site_id=uid(1), role="supervisor")
MAINTAINER = Principal(user_id=uid(202), site_id=uid(1), role="worker")
REPORTER = Principal(user_id=uid(201), site_id=uid(1), role="worker")
INCOMING = Principal(user_id=uid(204), site_id=uid(1), role="supervisor")


def fixture_context():
    incident = IncidentView(id=uid(401), site_id=uid(1), equipment_id=uid(103), owner_id=OWNER.user_id,
                            status="ACTION_REQUIRED", version=5)
    evidence = EvidenceView(id=uid(801), site_id=uid(1), incident_id=incident.id,
                            source_type="sop", source_id=uid(701), source_version="1", excerpt="합성 SOP",
                            content_hash=content_hash("합성 SOP"), captured_at=NOW,
                            applicable=True, document_approved=True)
    action = Action(id=uid(501), incident_id=incident.id, trigger_event_id=uid(901),
                    proposed_by_run_id=uid(601), title="기록 확인", scope="초기 점검 기록 범위 확인",
                    completion_criteria=("확인 범위와 남은 내용을 기록",),
                    assignee_id=MAINTAINER.user_id, due_at=NOW + timedelta(hours=1),
                    evidence_refs=(evidence.id,), created_at=NOW)
    return ActionContext(incident=incident, actions=(action,), evidence=(evidence,))


class MemoryStore:
    """Transactional test double only. Does NOT prove DB locks or race safety."""

    def __init__(self, context):
        self.context = context
        self.receipts = {}
        self.events = []
        self.failure = None
        self.draft = DraftView(id=uid(701), incident_id=context.incident.id, run_id=uid(601),
                               input_version=5, scope="기록 확인", completion_criteria=("결과 기록",),
                               source_refs=(uid(801),))
        self.run = RunView(id=uid(601), incident_id=context.incident.id, input_version=5,
                          trigger_event_id=uid(901), status="RUNNING")

    @contextmanager
    def transaction(self):
        snapshot = deepcopy((self.context, self.receipts, self.events))
        try:
            yield self
        except BaseException:
            self.context, self.receipts, self.events = snapshot
            raise

    def assert_action_scope(self, action_id, site_id):
        if self.context.incident.site_id != site_id or not any(a.id == action_id for a in self.context.actions):
            raise ActionError(404, "RESOURCE_NOT_FOUND", "작업을 찾을 수 없습니다.")

    def reserve_command(self, principal, key, fingerprint):
        scope = principal.site_id, principal.user_id, key
        if scope in self.receipts:
            previous, response = self.receipts[scope]
            if previous != fingerprint:
                raise ActionError(409, "IDEMPOTENCY_CONFLICT", "다른 입력입니다.")
            if response is None:
                raise ActionError(409, "COMMAND_IN_PROGRESS", "처리 중입니다.")
            return response
        self.receipts[scope] = fingerprint, None
        return None

    def lock_context(self, incident_id=None, *, action_id=None):
        return self.context

    def save_transition(self, before, transition):
        assert before == self.context
        self.context = transition.context
        if self.failure == "after_write":
            raise RuntimeError("injected storage failure")
        self.events.append(transition.event)

    def append_event(self, event):
        self.events.append(event)

    def finish_command(self, principal, key, response):
        if self.failure == "receipt":
            raise RuntimeError("injected receipt failure")
        scope = principal.site_id, principal.user_id, key
        self.receipts[scope] = self.receipts[scope][0], response

    def load_draft(self, draft_id):
        assert draft_id == self.draft.id
        return self.draft

    def load_run(self, run_id):
        return self.run

    def resolve_assignment(self, context):
        return Assignment(assignee_id=MAINTAINER.user_id, due_at=NOW + timedelta(hours=1))

    def stage_proposal(self, action):
        self.context = self.context.model_copy(update={"actions": self.context.actions + (action,)})
