"""F2-owned table definitions for F0's shared MetaData/Alembic registration.

Does not create an engine, call create_all, or define any F0/F1 table.
"""

from sqlalchemy import (Boolean, CheckConstraint, Column, DateTime, ForeignKey,
                        Index, Integer, MetaData, String, Table, Text, UniqueConstraint, Uuid)
from sqlalchemy.dialects.postgresql import JSONB


def define_action_tables(metadata: MetaData) -> tuple[Table, Table]:
    actions = Table(
        "actions", metadata,
        Column("id", Uuid, primary_key=True),
        Column("incident_id", Uuid, ForeignKey("incidents.id"), nullable=False),
        Column("trigger_event_id", Uuid, ForeignKey("events.id"), nullable=False),
        Column("proposed_by_run_id", Uuid, ForeignKey("agent_runs.id"), nullable=False),
        Column("title", Text, nullable=False), Column("scope", Text, nullable=False),
        Column("completion_criteria", JSONB, nullable=False),
        Column("assignee_id", Uuid, ForeignKey("users.id"), nullable=False),
        Column("due_at", DateTime(timezone=True), nullable=False),
        Column("is_required", Boolean, nullable=False),
        Column("evidence_refs", JSONB, nullable=False),
        Column("action_slot", String(32), nullable=False),
        Column("action_generation", Integer, nullable=False),
        Column("status", String(32), nullable=False),
        Column("revision", Integer, nullable=False), Column("version", Integer, nullable=False),
        Column("result_message_id", Uuid, ForeignKey("messages.id")),
        Column("completion_evidence_id", Uuid, ForeignKey("evidence.id")),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("started_at", DateTime(timezone=True)), Column("completed_at", DateTime(timezone=True)),
        UniqueConstraint("incident_id", "action_slot", "action_generation", name="uq_actions_generation"),
        CheckConstraint("action_slot = 'MAIN_FOLLOWUP' AND action_generation = 1 AND is_required",
                        name="ck_actions_phase1"),
        CheckConstraint("status IN ('PROPOSED','APPROVED','IN_PROGRESS','COMPLETED','REJECTED')",
                        name="ck_actions_status"),
        CheckConstraint("version >= 1 AND revision = 1", name="ck_actions_version"),
        CheckConstraint("length(btrim(scope)) > 0 AND length(btrim(title)) > 0", name="ck_actions_text"),
        CheckConstraint("jsonb_typeof(completion_criteria) = 'array' AND jsonb_array_length(completion_criteria) > 0",
                        name="ck_actions_criteria"),
        CheckConstraint("jsonb_typeof(evidence_refs) = 'array' AND jsonb_array_length(evidence_refs) > 0",
                        name="ck_actions_evidence"),
        CheckConstraint("status NOT IN ('IN_PROGRESS','COMPLETED') OR started_at IS NOT NULL",
                        name="ck_actions_started"),
        CheckConstraint("status != 'COMPLETED' OR (result_message_id IS NOT NULL AND "
                        "completion_evidence_id IS NOT NULL AND completed_at IS NOT NULL)",
                        name="ck_actions_completed"),
    )
    Index("uq_actions_active_main", actions.c.incident_id, actions.c.action_slot, unique=True,
          postgresql_where=actions.c.status.in_(("PROPOSED", "APPROVED", "IN_PROGRESS")))
    approvals = Table(
        "approvals", metadata,
        Column("id", Uuid, primary_key=True),
        Column("action_id", Uuid, ForeignKey("actions.id"), nullable=False),
        Column("action_revision", Integer, nullable=False),
        Column("decision", String(16), nullable=False), Column("reason", Text, nullable=False),
        Column("payload_hash", String(64), nullable=False),
        Column("approved_payload_snapshot", JSONB, nullable=False),
        Column("actor_id", Uuid, ForeignKey("users.id"), nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
        UniqueConstraint("action_id", "action_revision", name="uq_approvals_action_revision"),
        CheckConstraint("decision IN ('APPROVE','REJECT')", name="ck_approvals_decision"),
        CheckConstraint("action_revision = 1 AND length(btrim(reason)) > 0", name="ck_approvals_content"),
        CheckConstraint("payload_hash ~ '^[0-9a-f]{64}$'", name="ck_approvals_hash"),
    )
    return actions, approvals
