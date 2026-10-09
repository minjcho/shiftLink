import hashlib
import json
from datetime import UTC
from uuid import UUID

from .models import Action, ActionContext, EvidenceView


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_hash(payload: dict) -> str:
    return content_hash(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                   ensure_ascii=False, allow_nan=False))


def approval_payload(action: Action) -> dict:
    return {"title": action.title, "scope": action.scope,
            "assignee_id": str(action.assignee_id),
            "due_at": action.due_at.astimezone(UTC).isoformat(),
            "completion_criteria": list(action.completion_criteria),
            "revision": action.revision,
            "evidence_refs": sorted({str(ref) for ref in action.evidence_refs})}


def has_valid_approval(context: ActionContext, action: Action) -> bool:
    payload = approval_payload(action)
    approvals = [a for a in context.approvals if a.action_id == action.id]
    # Phase 1 permits one immutable approval decision, never REJECT -> APPROVE.
    return len(approvals) == 1 and all(
        a.decision == "APPROVE" and a.action_revision == action.revision
        and a.payload_hash == canonical_hash(payload)
        and a.approved_payload_snapshot == payload
        for a in approvals
    )


def valid_evidence(context: ActionContext, ref: UUID) -> EvidenceView | None:
    evidence = next((e for e in context.evidence if e.id == ref), None)
    if (evidence is None or evidence.site_id != context.incident.site_id
            or evidence.incident_id != context.incident.id or not evidence.applicable
            or evidence.content_hash != content_hash(evidence.excerpt)
            or (evidence.source_type == "sop" and evidence.document_approved is not True)):
        return None
    return evidence
