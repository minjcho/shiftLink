import pytest

from app.features.actions.errors import ActionError
from app.features.actions.service import finalize_action_proposal
from support import uid


def finalize(store, **overrides):
    params = dict(incident_id=uid(401), run_id=uid(601), input_version=5,
                  draft_id=uid(701), trigger_event_id=uid(901))
    params.update(overrides)
    return finalize_action_proposal(store, **params)


def test_proposal_staged_in_caller_transaction_and_id_reused(store):
    store.context = store.context.model_copy(update={"actions": (), "incident": store.context.incident.model_copy(
        update={"status": "INVESTIGATING"})})
    with store.transaction():
        first = finalize(store)
        second = finalize(store)
        assert first["created"] and not second["created"] and first["action_id"] == second["action_id"]
        assert store.context.incident.version == 5  # Caller owns the single parent bump.
    assert len(store.context.actions) == len(store.events) == 1


def test_caller_failure_rolls_back_proposed_action_and_event(store):
    store.context = store.context.model_copy(update={"actions": (), "incident": store.context.incident.model_copy(
        update={"status": "INVESTIGATING"})})
    before = store.context
    with pytest.raises(RuntimeError):
        with store.transaction():
            finalize(store)
            raise RuntimeError("F1 final lease check failed")
    assert store.context == before and not store.events


@pytest.mark.parametrize("status", ["APPROVED", "IN_PROGRESS", "COMPLETED", "REJECTED"])
def test_existing_generation_never_reactivated(store, status):
    store.context = store.context.model_copy(update={"actions": (store.context.actions[0].model_copy(
        update={"status": status}),)})
    result = finalize(store)
    assert not result["created"] and result["action_id"] == str(uid(501))
    assert store.context.actions[0].status == status and not store.events


@pytest.mark.parametrize("defect", ["version", "draft_run", "draft_incident", "draft_version", "run_incident",
                                  "run_version", "run_event", "run_status", "evidence", "review", "resolved"])
def test_rejects_stale_or_cross_context_proposals(store, defect):
    if defect == "version": store.context = store.context.model_copy(update={"incident": store.context.incident.model_copy(update={"version": 6})})
    if defect.startswith("draft_"):
        field = {"draft_run": "run_id", "draft_incident": "incident_id", "draft_version": "input_version"}[defect]
        store.draft = store.draft.model_copy(update={field: 99 if field == "input_version" else uid(999)})
    if defect.startswith("run_"):
        field = {"run_incident": "incident_id", "run_version": "input_version", "run_event": "trigger_event_id", "run_status": "status"}[defect]
        store.run = store.run.model_copy(update={field: 99 if field == "input_version" else "FAILED" if field == "status" else uid(999)})
    if defect == "evidence": store.context = store.context.model_copy(update={"evidence": ()})
    if defect == "review": store.context = store.context.model_copy(update={"incident": store.context.incident.model_copy(update={"review_required": True})})
    if defect == "resolved": store.context = store.context.model_copy(update={"incident": store.context.incident.model_copy(update={"status": "RESOLVED"})})
    before = store.context
    with pytest.raises(ActionError): finalize(store)
    assert store.context == before and not store.events
