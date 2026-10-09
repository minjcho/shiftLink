from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)


class User(Identity, Base):
    __tablename__ = "users"
    site_id: Mapped[str] = mapped_column(String(36), index=True)
    account_key: Mapped[str] = mapped_column(String(80), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (CheckConstraint("role IN ('worker','supervisor')"),)


class Shift(Identity, Base):
    __tablename__ = "shifts"
    site_id: Mapped[str] = mapped_column(String(36), index=True)
    label: Mapped[str] = mapped_column(String(100))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    supervisor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (Index("uq_active_shift_site", "site_id", unique=True,
                           postgresql_where=text("active = true")),)


class SessionToken(Identity, Base):
    __tablename__ = "session_tokens"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ShiftAssignment(Base):
    __tablename__ = "shift_assignments"
    shift_occurrence_id: Mapped[str] = mapped_column(ForeignKey("shifts.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    duty: Mapped[str] = mapped_column(String(30))


class Equipment(Identity, Base):
    __tablename__ = "equipment"
    site_id: Mapped[str] = mapped_column(String(36), index=True)
    code: Mapped[str] = mapped_column(String(80))
    label: Mapped[str] = mapped_column(String(200))
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    default_maintainer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (UniqueConstraint("site_id", "code"),)


class Incident(Identity, Base):
    __tablename__ = "incidents"
    display_id: Mapped[str] = mapped_column(String(60), unique=True)
    title: Mapped[str] = mapped_column(String(120), default="새 제보")
    site_id: Mapped[str] = mapped_column(String(36), index=True)
    equipment_id: Mapped[str] = mapped_column(ForeignKey("equipment.id"))
    reporter_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    origin_shift_occurrence_id: Mapped[str] = mapped_column(ForeignKey("shifts.id"))
    owner_shift_occurrence_id: Mapped[str] = mapped_column(ForeignKey("shifts.id"))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(30), default="OPEN")
    version: Mapped[int] = mapped_column(Integer, default=1)
    action_generation: Mapped[int] = mapped_column(Integer, default=1)
    review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    review_reason: Mapped[str | None] = mapped_column(Text)
    analysis: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("version >= 1"), CheckConstraint("action_generation = 1"),
        CheckConstraint("status IN ('OPEN','INVESTIGATING','ACTION_REQUIRED','IN_PROGRESS','PENDING_VERIFICATION','RESOLVED')"),)


class Message(Identity, Base):
    __tablename__ = "messages"
    site_id: Mapped[str] = mapped_column(String(36), index=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(30))
    text: Mapped[str] = mapped_column(Text)
    reply_to_request_id: Mapped[str | None] = mapped_column(ForeignKey("requests.id", use_alter=True, name="fk_message_request"))
    action_id: Mapped[str | None] = mapped_column(ForeignKey("actions.id", use_alter=True, name="fk_message_action"))
    correction_of: Mapped[str | None] = mapped_column(ForeignKey("messages.id"))
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (CheckConstraint("kind IN ('REPORT','NOTE','REPLY','ACTION_RESULT','CORRECTION')"),)


class Request(Identity, Base):
    __tablename__ = "requests"
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    target_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    purpose_code: Mapped[str] = mapped_column(String(30))
    question: Mapped[str] = mapped_column(Text)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    response_message_id: Mapped[str | None] = mapped_column(ForeignKey("messages.id", use_alter=True, name="fk_request_response"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("purpose_code IN ('VERIFY_SCOPE','VERIFY_RESULT')"),
        CheckConstraint("status IN ('OPEN','ANSWERED')"), CheckConstraint("is_required = true"),
        Index("uq_open_request_purpose", "incident_id", "target_user_id", "purpose_code", unique=True,
              postgresql_where=text("status = 'OPEN'")),
    )


class Evidence(Identity, Base):
    __tablename__ = "evidence"
    site_id: Mapped[str] = mapped_column(String(36), index=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(30))
    source_id: Mapped[str] = mapped_column(String(100))
    source_version: Mapped[str] = mapped_column(String(50), default="1")
    equipment_id: Mapped[str | None] = mapped_column(ForeignKey("equipment.id"))
    applicability: Mapped[dict] = mapped_column(JSON, default=dict)
    document_approval: Mapped[str | None] = mapped_column(String(30))
    excerpt: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    source_location: Mapped[str] = mapped_column(Text, default="")
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Document(Identity, Base):
    __tablename__ = "documents"
    site_id: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(50), default="1")
    approval_status: Mapped[str] = mapped_column(String(30), default="approved")
    equipment_ids: Mapped[list] = mapped_column(JSON, default=list)
    source_location: Mapped[str] = mapped_column(Text, default="")


class DocumentChunk(Identity, Base):
    __tablename__ = "document_chunks"
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    source_location: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (UniqueConstraint("document_id", "position"),)


class EquipmentLog(Identity, Base):
    __tablename__ = "equipment_logs"
    site_id: Mapped[str] = mapped_column(String(36), index=True)
    equipment_id: Mapped[str] = mapped_column(ForeignKey("equipment.id"))
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source_location: Mapped[str] = mapped_column(Text, default="")


class Action(Identity, Base):
    """Shared persisted projection; F1 does not implement F2 commands."""
    __tablename__ = "actions"
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    action_slot: Mapped[str] = mapped_column(String(30), default="MAIN_FOLLOWUP")
    action_generation: Mapped[int] = mapped_column(Integer, default=1)
    trigger_event_id: Mapped[str | None] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(200), default="후속 작업")
    scope: Mapped[str] = mapped_column(Text)
    completion_criteria: Mapped[list] = mapped_column(JSON, default=list)
    assignee_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default="PROPOSED")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    version: Mapped[int] = mapped_column(Integer, default=1)
    proposed_by_run_id: Mapped[str | None] = mapped_column(String(36))
    result_message_id: Mapped[str | None] = mapped_column(String(36))
    completion_evidence_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("incident_id", "action_slot", "action_generation"),
        CheckConstraint("action_generation = 1"),
        Index("uq_active_main_action", "incident_id", "action_slot", unique=True,
              postgresql_where=text("status IN ('PROPOSED','APPROVED','IN_PROGRESS')")),)


class Approval(Identity, Base):
    __tablename__ = "approvals"
    action_id: Mapped[str] = mapped_column(ForeignKey("actions.id"), index=True)
    action_revision: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)
    payload_hash: Mapped[str] = mapped_column(String(64))
    approved_payload_snapshot: Mapped[dict] = mapped_column(JSON)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Verification(Identity, Base):
    __tablename__ = "verifications"
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"))
    decision: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str] = mapped_column(Text)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    checked_version: Mapped[int] = mapped_column(Integer)
    applied_version: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResolutionCase(Identity, Base):
    __tablename__ = "resolution_cases"
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("incidents.id"))
    site_id: Mapped[str] = mapped_column(String(36), index=True)
    equipment_id: Mapped[str] = mapped_column(ForeignKey("equipment.id"))
    title: Mapped[str] = mapped_column(String(200))
    resolved_version: Mapped[int] = mapped_column(Integer, default=1)
    verification_id: Mapped[str | None] = mapped_column(String(36))
    snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("incident_id", "resolved_version"),)


class Handover(Identity, Base):
    __tablename__ = "handovers"
    site_id: Mapped[str] = mapped_column(String(36))
    from_shift_occurrence_id: Mapped[str] = mapped_column(ForeignKey("shifts.id"))
    to_shift_occurrence_id: Mapped[str] = mapped_column(ForeignKey("shifts.id"))
    receiver_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("site_id", "from_shift_occurrence_id", "to_shift_occurrence_id"),)


class HandoverItem(Identity, Base):
    __tablename__ = "handover_items"
    handover_id: Mapped[str] = mapped_column(ForeignKey("handovers.id"))
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    latest_revision: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (UniqueConstraint("handover_id", "incident_id"),)


class HandoverRevision(Base):
    __tablename__ = "handover_item_revisions"
    item_id: Mapped[str] = mapped_column(ForeignKey("handover_items.id"), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_version: Mapped[int] = mapped_column(Integer)
    snapshot_json: Mapped[dict] = mapped_column(JSON)
    snapshot_token: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HandoverAck(Identity, Base):
    __tablename__ = "handover_acks"
    item_id: Mapped[str] = mapped_column(ForeignKey("handover_items.id"))
    revision: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    previous_owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    new_owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    ack_applied_version: Mapped[int] = mapped_column(Integer)
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("item_id", "revision"),)


class Event(Identity, Base):
    __tablename__ = "events"
    site_id: Mapped[str] = mapped_column(String(36), index=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    type: Mapped[str] = mapped_column(String(80))
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    related_ids: Mapped[dict] = mapped_column(JSON, default=dict)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CommandReceipt(Identity, Base):
    __tablename__ = "command_receipts"
    site_id: Mapped[str] = mapped_column(String(36))
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    idempotency_key: Mapped[str] = mapped_column(String(200))
    payload_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="COMPLETED")
    http_status: Mapped[int] = mapped_column(Integer)
    response_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("site_id", "actor_id", "idempotency_key"),)


class Job(Identity, Base):
    __tablename__ = "jobs"
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    trigger_event_id: Mapped[str] = mapped_column(ForeignKey("events.id"))
    job_kind: Mapped[str] = mapped_column(String(30), default="INVESTIGATE")
    dedupe_key: Mapped[str] = mapped_column(String(160), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    lease_token: Mapped[str | None] = mapped_column(String(80))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_error: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("incident_id", "trigger_event_id", "job_kind"),
        CheckConstraint("status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','SUPERSEDED')"),)


class AgentRun(Identity, Base):
    __tablename__ = "agent_runs"
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    attempt: Mapped[int] = mapped_column(Integer)
    trigger_event_id: Mapped[str] = mapped_column(String(36))
    input_version: Mapped[int | None] = mapped_column(Integer)
    applied_version: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="RUNNING")
    mode: Mapped[str] = mapped_column(String(20), default="live")
    model_id: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(40), default="f1-v1")
    tool_schema_version: Mapped[str] = mapped_column(String(40), default="f1-v1")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_json: Mapped[dict | None] = mapped_column(JSON)
    steps_json: Mapped[list] = mapped_column(JSON, default=list)
    usage_json: Mapped[dict | None] = mapped_column(JSON)
    error_json: Mapped[dict | None] = mapped_column(JSON)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("job_id", "attempt"),)


class ActionDraft(Identity, Base):
    __tablename__ = "action_drafts"
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"))
    input_version: Mapped[int] = mapped_column(Integer)
    payload_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
