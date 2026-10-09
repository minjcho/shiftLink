from __future__ import annotations

import json
import re
import time
import unicodedata

from pydantic import ValidationError
from sqlalchemy import select, text

from app.core.models import (ActionDraft, Document, DocumentChunk, Equipment, EquipmentLog,
                             Incident, ResolutionCase)
from .context import RunContext, evidence_data, issue_evidence
from .jobs import fence, lock_incident_graph
from .schemas import TOOL_ARGUMENTS


def error_result(code, message, retryable=False):
    return {"outcome": "ERROR", "data": None, "source_refs": [], "partial": False,
            "error": {"code": code, "message": message, "retryable": retryable}}


def tokens(text):
    return re.findall(r"[\w]+", unicodedata.normalize("NFKC", text).casefold())


def search_score(query, text, equipment):
    query_tokens = set(tokens(query))
    names = [equipment.code, *equipment.aliases]
    if any(name.casefold() in query.casefold() for name in names):
        for name in names:
            query_tokens.update(tokens(name))
    haystack = unicodedata.normalize("NFKC", text).casefold()
    return sum(1 for token in query_tokens if token in haystack)


class ToolExecutor:
    def __init__(self, session_factory, context: RunContext, *, max_chunks=5, max_chunk_chars=2000,
                 injected_errors: dict[str, dict] | None = None, deadline_at: float | None = None):
        self.session_factory, self.context = session_factory, context
        self.max_chunks, self.max_chunk_chars = max_chunks, max_chunk_chars
        # Explicit dependency injection only. Never derive test behavior from report text or dataset names.
        self.injected_errors = injected_errors or {}
        self.deadline_at = deadline_at
        self.steps: list[dict] = []

    def __call__(self, name: str, raw_arguments: str) -> dict:
        start = time.monotonic()
        schema = TOOL_ARGUMENTS.get(name)
        if schema is None:
            return error_result("TOOL_NOT_ALLOWED", "This tool is not allowed")
        try:
            args = schema.model_validate_json(raw_arguments)
        except (ValidationError, ValueError):
            return error_result("INVALID_TOOL_ARGUMENTS", "The arguments do not satisfy the tool schema")
        arguments = args.model_dump(mode="json")
        remaining = self.deadline_at - time.monotonic() if self.deadline_at is not None else None
        if remaining is not None and remaining <= 0:
            return error_result("TIMEOUT", "The investigation deadline has elapsed", True)
        if name in self.injected_errors:
            result = error_result(**self.injected_errors[name])
        else:
            with self.session_factory.begin() as tx:
                if remaining is not None:
                    tx.execute(text("SELECT set_config('statement_timeout', :timeout, true)"),
                               {"timeout": str(max(1, int(remaining * 1000)))})
                incident = lock_incident_graph(tx, self.context.identity)
                _, run = fence(tx, self.context.identity)
                if incident.site_id != self.context.identity.site_id:
                    return error_result("SCOPE_INVALID", "The incident scope changed")
                equipment = tx.get(Equipment, incident.equipment_id)
                if name != "propose_action" and (str(args.equipment_id) != equipment.id
                                                   or equipment.site_id != incident.site_id):
                    result = error_result("SCOPE_INVALID", "The requested equipment is outside this incident")
                elif name == "propose_action":
                    refs = {str(ref) for ref in args.source_refs}
                    observed = set(run.metadata_json.get("observed_source_ids", []))
                    if not refs.issubset(observed):
                        result = error_result("EVIDENCE_INVALID", "The draft cites sources not seen in this run")
                    else:
                        draft = ActionDraft(run_id=run.id, incident_id=incident.id,
                                            input_version=self.context.identity.input_version,
                                            payload_json=arguments)
                        tx.add(draft)
                        tx.flush()
                        result = {"outcome": "OK", "data": {"draft_id": draft.id,
                                  "incident_id": incident.id, "input_version": draft.input_version},
                                  "source_refs": sorted(refs), "partial": False, "error": None}
                else:
                    result = self._read(tx, incident, equipment, name, args)
                fence(tx, self.context.identity)
                new_ids = set(result["source_refs"])
                self.context.source_ids.update(new_ids)
                run.metadata_json = {**run.metadata_json, "observed_source_ids": sorted(
                    set(run.metadata_json.get("observed_source_ids", [])) | new_ids)}
        step = {"tool": name, "arguments": arguments, "result": result,
                "elapsed_seconds": time.monotonic() - start}
        self.steps.append(step)
        return result

    def _read(self, tx, incident, equipment, name, args):
        items, refs, total, truncated = [], [], 0, False
        if name == "get_equipment_context":
            records = list(tx.scalars(select(EquipmentLog).where(EquipmentLog.site_id == incident.site_id,
                                                                EquipmentLog.equipment_id == equipment.id)
                                     .order_by(EquipmentLog.observed_at.desc(), EquipmentLog.id)))
            total = len(records)
            for record in records[:self.max_chunks]:
                truncated |= len(record.text) > self.max_chunk_chars
                ev = issue_evidence(tx, incident, source_type="log", source_id=record.id,
                                    equipment_id=record.equipment_id, excerpt=record.text[:self.max_chunk_chars],
                                    observed_at=record.observed_at, source_location=record.source_location,
                                    applicability={"author_id": record.author_id})
                items.append({"log_id": record.id, "author_id": record.author_id, **evidence_data(ev)})
                refs.append(ev.id)
            data = {"equipment": {"id": equipment.id, "code": equipment.code, "aliases": equipment.aliases},
                    "allowed_question_target_ids": sorted(self.context.target_user_ids), "items": items}
            # The equipment exists even when it has no logs.
            outcome = "OK"
        elif name == "search_documents":
            ranked = []
            rows = tx.execute(select(Document, DocumentChunk).join(DocumentChunk).where(
                Document.site_id == incident.site_id, Document.approval_status == "approved"))
            for document, chunk in rows:
                if equipment.id not in document.equipment_ids:
                    continue
                score = search_score(args.query, document.title + " " + chunk.text + " " + equipment.code, equipment)
                if score:
                    ranked.append((-score, document.id, chunk.position, document, chunk))
            ranked.sort(key=lambda item: item[:3])
            total = len(ranked)
            for _, _, _, document, chunk in ranked[:self.max_chunks]:
                truncated |= len(chunk.text) > self.max_chunk_chars
                ev = issue_evidence(tx, incident, source_type="sop", source_id=document.id,
                                    source_version=document.version, equipment_id=equipment.id,
                                    excerpt=chunk.text[:self.max_chunk_chars], document_approval="approved",
                                    source_location=chunk.source_location or f"{document.source_location}#{chunk.position}",
                                    applicability={"equipment_ids": document.equipment_ids, "section": chunk.position})
                items.append({"document_id": document.id, "title": document.title,
                              "chunk_position": chunk.position, **evidence_data(ev)})
                refs.append(ev.id)
            data, outcome = {"items": items, "query": args.query, "search_mode": "keyword"}, "OK" if items else "EMPTY"
        else:
            ranked = []
            for case in tx.scalars(select(ResolutionCase).where(ResolutionCase.site_id == incident.site_id)):
                if not isinstance(case.snapshot_json, dict) or case.snapshot_json.get("status") != "RESOLVED":
                    continue
                if case.incident_id is not None:
                    original = tx.get(Incident, case.incident_id)
                    if original is None or original.status != "RESOLVED" or case.verification_id is None:
                        continue
                elif case.snapshot_json.get("synthetic") is not True:
                    # Legacy synthetic reference cases are explicit; unknown unlinked records
                    # do not become reviewed/resolved evidence merely by occupying this table.
                    continue
                text = json.dumps(case.snapshot_json, ensure_ascii=False, sort_keys=True)
                score = search_score(args.query, case.title + " " + text, equipment)
                if score:
                    ranked.append((-score, case.id, case, text))
            ranked.sort(key=lambda item: item[:2])
            total = len(ranked)
            for _, _, case, text in ranked[:self.max_chunks]:
                truncated |= len(text) > self.max_chunk_chars
                comparison = case.equipment_id != equipment.id
                ev = issue_evidence(tx, incident, source_type="case", source_id=case.id,
                                    equipment_id=case.equipment_id, source_version=str(case.resolved_version),
                                    excerpt=text[:self.max_chunk_chars], observed_at=case.created_at,
                                    source_location=f"cases/{case.id}",
                                    applicability={"comparison_only": comparison})
                items.append({"case_id": case.id, "title": case.title, "comparison_only": comparison,
                              **evidence_data(ev)})
                refs.append(ev.id)
            data, outcome = {"items": items, "query": args.query, "search_mode": "keyword"}, "OK" if items else "EMPTY"
        return {"outcome": outcome, "data": data, "source_refs": refs,
                "partial": total > self.max_chunks or truncated, "error": None}
