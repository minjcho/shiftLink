"""Shared foundation tables. Feature migrations add their own tables/FKs."""
from sqlalchemy import (MetaData, Table, Column as C, Uuid, String, Text, Integer,
                        Boolean, DateTime, ForeignKey as FK, CheckConstraint as Check,
                        UniqueConstraint as Unique, Index, func)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData(naming_convention={"ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"})


def pk(): return C("id", Uuid, primary_key=True)
def ref(name, target, **kw): return C(name, Uuid, FK(target), nullable=False, **kw)
def stamp(name="created_at"): return C(name, DateTime(timezone=True), nullable=False, server_default=func.now())


sites = Table("sites", metadata, pk(), C("name", Text, nullable=False))
users = Table("users", metadata, pk(), ref("site_id", "sites.id"), C("account_key", String(40), unique=True),
    C("display_name", Text, nullable=False), C("role", String(16), nullable=False),
    C("enabled", Boolean, nullable=False, server_default="true"),
    Check("role IN ('worker','supervisor')", name="ck_users_role"))
shifts = Table("shifts", metadata, pk(), ref("site_id", "sites.id"), C("label", Text, nullable=False),
    stamp("starts_at"), stamp("ends_at"), ref("supervisor_id", "users.id"),
    Check("ends_at > starts_at", name="ck_shifts_interval"))
shift_assignments = Table("shift_assignments", metadata,
    ref("shift_occurrence_id", "shifts.id", primary_key=True), ref("user_id", "users.id", primary_key=True),
    C("duty", String(32), primary_key=True))
shift_pairs = Table("shift_pairs", metadata, ref("from_shift_occurrence_id", "shifts.id", primary_key=True),
    ref("to_shift_occurrence_id", "shifts.id", primary_key=True),
    Check("from_shift_occurrence_id != to_shift_occurrence_id", name="ck_shift_pairs_distinct"))
equipment = Table("equipment", metadata, pk(), ref("site_id", "sites.id"),
    C("code", String(32), nullable=False), C("label", Text, nullable=False),
    C("aliases", JSONB, nullable=False), ref("default_maintainer_id", "users.id"), Unique("site_id", "code"))
sessions = Table("sessions", metadata, C("token_hash", String(64), primary_key=True),
    ref("user_id", "users.id"), ref("shift_occurrence_id", "shifts.id"), stamp(), stamp("expires_at"))
incidents = Table("incidents", metadata, pk(), ref("site_id", "sites.id"),
    C("display_id", String(40), nullable=False, unique=True), ref("equipment_id", "equipment.id"),
    ref("reporter_id", "users.id"), ref("owner_id", "users.id"),
    ref("origin_shift_occurrence_id", "shifts.id"), ref("owner_shift_occurrence_id", "shifts.id"),
    C("status", String(32), nullable=False), C("version", Integer, nullable=False, server_default="1"),
    C("action_generation", Integer, nullable=False, server_default="1"),
    C("review_required", Boolean, nullable=False, server_default="false"), C("review_reason", Text),
    C("analysis", JSONB), stamp(), stamp("updated_at"), C("resolved_at", DateTime(timezone=True)),
    Check("version >= 1 AND action_generation = 1", name="ck_incidents_version"),
    Check("status IN ('OPEN','INVESTIGATING','ACTION_REQUIRED','IN_PROGRESS','PENDING_VERIFICATION','RESOLVED')", name="ck_incidents_status"))
events = Table("events", metadata, pk(), ref("site_id", "sites.id"), ref("incident_id", "incidents.id"),
    C("type", String(64), nullable=False), C("actor_id", Uuid, FK("users.id")),
    C("related_ids", JSONB, nullable=False), C("payload", JSONB, nullable=False), stamp("occurred_at"))
messages = Table("messages", metadata, pk(), ref("site_id", "sites.id"), ref("incident_id", "incidents.id"),
    ref("author_id", "users.id"), C("kind", String(32), nullable=False), C("text", Text, nullable=False),
    C("reply_to_request_id", Uuid), C("action_id", Uuid), C("correction_of", Uuid, FK("messages.id")),
    C("observed_at", DateTime(timezone=True)), stamp("received_at"),
    Check("length(btrim(text)) > 0", name="ck_messages_text"),
    Check("kind IN ('REPORT','NOTE','REPLY','ACTION_RESULT','CORRECTION')", name="ck_messages_kind"))
requests = Table("requests", metadata, pk(), ref("incident_id", "incidents.id"), ref("target_user_id", "users.id"),
    C("purpose_code", String(32), nullable=False), C("question", Text, nullable=False),
    C("is_required", Boolean, nullable=False), C("status", String(16), nullable=False),
    C("evidence_refs", JSONB, nullable=False), C("response_message_id", Uuid, FK("messages.id")),
    C("version", Integer, nullable=False, server_default="1"), stamp(), C("answered_at", DateTime(timezone=True)),
    Check("status IN ('OPEN','ANSWERED') AND version >= 1", name="ck_requests_state"),
    Check("purpose_code IN ('VERIFY_SCOPE','VERIFY_RESULT')", name="ck_requests_purpose"))
Index("uq_requests_open", requests.c.incident_id, requests.c.target_user_id, requests.c.purpose_code,
      unique=True, postgresql_where=requests.c.status == "OPEN")
evidence = Table("evidence", metadata, pk(), ref("site_id", "sites.id"), ref("incident_id", "incidents.id"),
    C("source_type", String(32), nullable=False), C("source_id", Uuid, nullable=False),
    C("source_version", String(80), nullable=False), ref("equipment_id", "equipment.id"),
    C("applicability", JSONB, nullable=False), C("document_approval", JSONB),
    C("excerpt", Text, nullable=False), C("content_hash", String(64), nullable=False),
    C("source_location", Text, nullable=False), C("observed_at", DateTime(timezone=True)), stamp("captured_at"),
    Check("source_type IN ('message','log','sop','case','completion_report')", name="ck_evidence_source"))
jobs = Table("jobs", metadata, pk(), ref("incident_id", "incidents.id"), ref("trigger_event_id", "events.id"),
    C("job_kind", String(32), nullable=False), C("dedupe_key", Text, nullable=False, unique=True),
    C("status", String(32), nullable=False, server_default="QUEUED"),
    C("attempt", Integer, nullable=False, server_default="0"), C("lease_token", Uuid),
    C("lease_expires_at", DateTime(timezone=True)), stamp("available_at"), C("last_error", JSONB), stamp(), stamp("updated_at"),
    Unique("incident_id", "trigger_event_id", "job_kind", name="uq_jobs_trigger"),
    Check("attempt >= 0", name="ck_jobs_attempt"),
    Check("status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','SUPERSEDED')", name="ck_jobs_status"),
    Check("status != 'RUNNING' OR (lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)", name="ck_jobs_lease"))
agent_runs = Table("agent_runs", metadata, pk(), ref("job_id", "jobs.id"),
    C("attempt", Integer, nullable=False), ref("trigger_event_id", "events.id"),
    C("input_version", Integer, nullable=False), C("applied_version", Integer),
    C("status", String(32), nullable=False), C("mode", String(16), nullable=False),
    C("model_id", Text), C("prompt_version", Text), C("tool_schema_version", Text),
    stamp("started_at"), C("finished_at", DateTime(timezone=True)), C("decision_json", JSONB),
    C("steps_json", JSONB), C("usage_json", JSONB), C("error_json", JSONB), C("metadata_json", JSONB),
    Unique("job_id", "attempt"), Check("attempt >= 1 AND input_version >= 1", name="ck_runs_version"),
    Check("status IN ('RUNNING','WAITING_INPUT','SUCCEEDED','FAILED','SUPERSEDED')", name="ck_runs_status"))
action_drafts = Table("action_drafts", metadata, pk(), ref("run_id", "agent_runs.id"),
    ref("incident_id", "incidents.id"), C("input_version", Integer, nullable=False),
    C("payload_json", JSONB, nullable=False), stamp())
command_receipts = Table("command_receipts", metadata,
    ref("site_id", "sites.id", primary_key=True), ref("actor_id", "users.id", primary_key=True),
    C("idempotency_key", String(200), primary_key=True), C("payload_hash", String(64), nullable=False),
    C("status", String(16), nullable=False), C("http_status", Integer), C("response_json", JSONB), stamp(),
    Check("status IN ('RUNNING','COMPLETED')", name="ck_receipts_state"),
    Check("status != 'COMPLETED' OR (http_status IS NOT NULL AND response_json IS NOT NULL)", name="ck_receipts_response"))
