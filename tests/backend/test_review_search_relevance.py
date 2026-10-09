"""PostgreSQL search regressions: applicability does not imply text relevance."""
import json
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update

from app.agent.tools import ToolExecutor
from app.core.models import AgentRun, Document, DocumentChunk, Evidence
from test_agent import prepared


def add_document(tx, ids, *, title, passages, document_id=None, **overrides):
    values = {"id": document_id or str(uuid4()), "site_id": ids["site"], "title": title,
              "equipment_ids": [ids["equipment"]], "approval_status": "approved", **overrides}
    document = Document(**values)
    tx.add(document)
    tx.flush()
    for position, passage in passages:
        tx.add(DocumentChunk(document_id=document.id, position=position, text=passage))
    return document.id


def search(executor, ids, query):
    return executor("search_documents", json.dumps({"equipment_id": ids["equipment"], "query": query}))


@pytest.mark.ac11
@pytest.mark.ac14
@pytest.mark.parametrize("query", ["CV-03 unfindable-xyz", "3호기 unfindable-xyz"])
def test_equipment_scope_does_not_make_unrelated_passages_relevant(session_factory, demo_ids, query):
    context = prepared(session_factory, demo_ids)
    with session_factory.begin() as tx:
        tx.execute(update(Document).values(approval_status="draft"))
        add_document(tx, demo_ids, title="Electrical isolation procedure",
                     passages=[(1, "Verify breaker labels against the approved register.")])

    executor = ToolExecutor(session_factory, context)
    result = search(executor, demo_ids, query)

    assert result == {"outcome": "EMPTY", "data": {"items": [], "query": query, "search_mode": "keyword"},
                      "source_refs": [], "partial": False, "error": None}
    with session_factory() as tx:
        assert tx.scalar(select(func.count(Evidence.id)).where(Evidence.source_type == "sop")) == 0
        assert set(tx.get(AgentRun, context.identity.run_id).metadata_json["observed_source_ids"]) == context.source_ids

    unavailable = ToolExecutor(session_factory, context, injected_errors={"search_documents": {
        "code": "SOURCE_UNAVAILABLE", "message": "Source unavailable", "retryable": True}})
    failure = search(unavailable, demo_ids, query)
    assert failure["outcome"] == "ERROR" and failure["data"] is None
    assert failure["error"]["code"] == "SOURCE_UNAVAILABLE"


@pytest.mark.ac11
@pytest.mark.parametrize(("query", "title", "passage"), [
    ("CV-03 unfindable-xyz", "CV-03 reference manual", "Verify breaker labels."),
    ("CV-03 overheating", "Temperature observation", "Record overheating symptoms before assessment."),
    ("3호기 unfindable-xyz", "Reference manual", "CV-03 uses the approved register."),
])
def test_real_title_content_and_alias_matches_remain_searchable(session_factory, demo_ids, query, title, passage):
    context = prepared(session_factory, demo_ids)
    with session_factory.begin() as tx:
        tx.execute(update(Document).values(approval_status="draft"))
        relevant_id = add_document(tx, demo_ids, title=title, passages=[(1, passage)])
        add_document(tx, demo_ids, title="Electrical isolation procedure",
                     passages=[(1, "Verify breaker labels against the approved register.")])

    result = search(ToolExecutor(session_factory, context), demo_ids, query)

    assert result["outcome"] == "OK" and result["error"] is None
    assert [(item["document_id"], item["excerpt"]) for item in result["data"]["items"]] == [(relevant_id, passage)]
    assert result["source_refs"] == [result["data"]["items"][0]["id"]]


@pytest.mark.ac11
@pytest.mark.ac12
def test_relevance_keeps_scope_approval_order_and_chunk_limits(session_factory, demo_ids):
    context = prepared(session_factory, demo_ids)
    first_id, second_id = str(UUID(int=8001)), str(UUID(int=8002))
    with session_factory.begin() as tx:
        tx.execute(update(Document).values(approval_status="draft"))
        add_document(tx, demo_ids, document_id=second_id, title="Temperature record",
                     passages=[(1, "overheating recorded")])
        add_document(tx, demo_ids, document_id=first_id, title="Temperature record",
                     passages=[(3, "overheating " + "x" * 100), (1, "overheating recorded"),
                               (2, "overheating vibration recorded")])
        for overrides in [{"approval_status": "draft"}, {"site_id": str(uuid4())},
                          {"equipment_ids": [demo_ids["comparison_equipment"]]}]:
            add_document(tx, demo_ids, title="overheating vibration",
                         passages=[(1, "overheating vibration recorded")], **overrides)

    executor = ToolExecutor(session_factory, context, max_chunks=3, max_chunk_chars=30)
    result = search(executor, demo_ids, "CV-03 overheating vibration")
    repeated = search(executor, demo_ids, "CV-03 overheating vibration")
    expected = [(first_id, 2), (first_id, 1), (first_id, 3)]

    for response in [result, repeated]:
        assert response["outcome"] == "OK" and response["partial"] is True
        items = response["data"]["items"]
        assert [(item["document_id"], item["chunk_position"]) for item in items] == expected
        assert all(item["document_approval"] == "approved" and len(item["excerpt"]) <= 30 for item in items)
        assert len(items[-1]["excerpt"]) == 30
