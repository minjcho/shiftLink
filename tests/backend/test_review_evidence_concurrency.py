"""Concurrent real tool transactions reuse provenance under the shared Incident lock."""
from concurrent.futures import ThreadPoolExecutor
import json
from threading import Event as ThreadEvent
import time
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from app.agent import tools as tool_module
from app.agent.jobs import claim_job, prepare_run
from app.core.models import AgentRun, Evidence, Incident, Job, Message
from app.core.ports import FeaturePorts
from app.core.transactions import enqueue_job, new_event


def prepared_pair(factory, ids):
    with factory.begin() as tx:
        incident = Incident(id=str(uuid4()), display_id=f"EVIDENCE-{uuid4()}",
            site_id=ids["site"], equipment_id=ids["equipment"], reporter_id=ids["reporter"],
            origin_shift_occurrence_id=ids["outgoing_shift"],
            owner_shift_occurrence_id=ids["outgoing_shift"],
            owner_id=ids["outgoing_supervisor"], status="INVESTIGATING")
        tx.add(incident)
        tx.flush()
        tx.add(Message(site_id=incident.site_id, incident_id=incident.id,
            author_id=ids["reporter"], kind="REPORT", text="동일 출처 조회 경합 확인"))
        enqueue_job(tx, incident, new_event(tx, incident, "REPORT_CREATED"))
        enqueue_job(tx, incident, new_event(tx, incident, "NOTE_CREATED"))
    contexts = []
    for _ in range(2):
        identity = claim_job(factory, mode="fake", model_id="test-evidence-concurrency")
        contexts.append(prepare_run(factory, identity, FeaturePorts()))
    assert contexts[0].identity.incident_id == contexts[1].identity.incident_id
    assert contexts[0].identity.job_id != contexts[1].identity.job_id
    return contexts


def wait_for_blocker(factory, waiting_pid, blocking_pid):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with factory() as tx:
            blockers = tx.scalar(text("SELECT pg_blocking_pids(:pid)"), {"pid": waiting_pid})
        if blocking_pid in blockers:
            return
        time.sleep(0.01)
    pytest.fail("The second tool did not wait for the first tool's database transaction")


@pytest.mark.ac27
@pytest.mark.parametrize(("tool", "source_type"), [
    ("get_equipment_context", "log"),
    ("search_documents", "sop"),
    ("search_similar_incidents", "case"),
])
def test_overlapping_jobs_reuse_one_evidence_id(tool, source_type, session_factory, demo_ids, monkeypatch):
    first, second = prepared_pair(session_factory, demo_ids)
    first_issued, second_entered, release_first = ThreadEvent(), ThreadEvent(), ThreadEvent()
    first_pid, second_pid, issued_ids = [], [], []
    original_issue, original_lock = tool_module.issue_evidence, tool_module.lock_incident_graph

    def hold_first_uncommitted_evidence(tx, incident, **kwargs):
        evidence = original_issue(tx, incident, **kwargs)
        issued_ids.append(evidence.id)
        if len(issued_ids) == 1:
            first_pid.append(tx.scalar(text("SELECT pg_backend_pid()")))
            first_issued.set()
            assert release_first.wait(10), "test coordinator did not release the first tool"
        return evidence

    def observe_second_incident_lock(tx, identity):
        if identity.job_id == second.identity.job_id:
            second_pid.append(tx.scalar(text("SELECT pg_backend_pid()")))
            second_entered.set()
        return original_lock(tx, identity)

    monkeypatch.setattr(tool_module, "issue_evidence", hold_first_uncommitted_evidence)
    monkeypatch.setattr(tool_module, "lock_incident_graph", observe_second_incident_lock)
    arguments = {"equipment_id": demo_ids["equipment"]}
    if tool != "get_equipment_context":
        arguments["query"] = "점검"
    raw_arguments = json.dumps(arguments)
    with session_factory() as tx:
        assert not list(tx.scalars(select(Evidence).where(
            Evidence.incident_id == first.identity.incident_id, Evidence.source_type == source_type)))

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first_tool = tool_module.ToolExecutor(session_factory, first, max_chunks=1,
                deadline_at=time.monotonic() + 20)
            second_tool = tool_module.ToolExecutor(session_factory, second, max_chunks=1,
                deadline_at=time.monotonic() + 20)
            first_future = pool.submit(first_tool, tool, raw_arguments)
            try:
                assert first_issued.wait(5), "the first tool did not issue evidence"
                second_future = pool.submit(second_tool, tool, raw_arguments)
                assert second_entered.wait(5), "the second tool did not attempt its Incident lock"
                wait_for_blocker(session_factory, second_pid[0], first_pid[0])
                assert len(issued_ids) == 1
            finally:
                release_first.set()
            first_result, second_result = first_future.result(timeout=15), second_future.result(timeout=15)
    finally:
        release_first.set()

    assert first_result["outcome"] == second_result["outcome"] == "OK"
    assert len(first_result["source_refs"]) == 1
    assert first_result["source_refs"] == second_result["source_refs"]
    assert issued_ids == first_result["source_refs"] * 2
    with session_factory() as tx:
        rows = list(tx.scalars(select(Evidence).where(
            Evidence.incident_id == first.identity.incident_id, Evidence.source_type == source_type)))
        assert [row.id for row in rows] == first_result["source_refs"]
        incident = tx.get(Incident, first.identity.incident_id)
        assert incident.version == first.identity.input_version == second.identity.input_version
        assert incident.status == "INVESTIGATING"
        assert incident.owner_id == demo_ids["outgoing_supervisor"]
        for context in (first, second):
            assert tx.get(Job, context.identity.job_id).status == "RUNNING"
            run = tx.get(AgentRun, context.identity.run_id)
            assert run.status == "RUNNING"
            assert set(first_result["source_refs"]).issubset(run.metadata_json["observed_source_ids"])
