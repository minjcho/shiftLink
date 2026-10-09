export interface Envelope<T> { data: T; meta?: { request_id?: string; dataset_id?: string; demo_mode?: boolean; build?: Build } }
export interface Build { app_commit_sha: string | null; working_tree_dirty: boolean | null; agent_mode: string | null; search_mode: string | null }
export interface Me { user_id: string; display_name: string; role: 'worker' | 'supervisor'; site_id: string; shift_occurrence_id: string | null; duties: string[] }
export interface Equipment { id: string; code: string; label?: string; aliases: string[] }
export interface Page<T> { items: T[]; next_cursor: string | null }
export interface Incident { id: string; display_id: string; title?: string; equipment_id: string; status: string; version: number; owner_id: string; owner_shift_occurrence_id?: string; waiting_for_input: boolean; open_request_count?: number; unfinished_action_count?: number; review_required: boolean; review_reason: string | null; updated_at?: string; allowed_commands: string[] }
export interface Message { id: string; kind: string; text: string; author_id?: string; received_at?: string; observed_at?: string | null; reply_to_request_id?: string | null; correction_of?: string | null }
export interface RequestItem { id: string; purpose_code: string; question: string; target_user_id: string; is_required: boolean; status: 'OPEN' | 'ANSWERED'; evidence_refs: string[]; response_message_id: string | null; created_at: string }
export interface Fact { text: string; kind: string; source_refs: string[] }
export interface Analysis { run_id: string; base_version: number; is_stale: boolean; decision: string; facts: Fact[]; hypotheses: string[]; missing_information: string[]; source_refs: string[]; reason: string }
export interface Evidence { id: string; source_type: string; source_id: string; source_version: string; excerpt: string; equipment_id?: string; source_location?: string; applicability?: unknown; observed_at?: string | null; captured_at?: string }
export interface Job { id: string; incident_id?: string; status: string; attempt?: number; latest_run_id?: string | null; latest_run_status?: string | null; mode?: string; started_at?: string | null; finished_at?: string | null; error_code?: string | null; retryable?: boolean; run_summary?: Record<string, unknown> }
export interface ActionSummary { id: string; status: string; assignee_id: string; scope?: string; is_required?: boolean }
export interface IncidentDetail extends Incident { messages: Message[]; requests: RequestItem[]; actions: ActionSummary[]; analysis: Analysis | null; evidence: Evidence[]; latest_job: Job | null; recent_events: { id: string; type: string; occurred_at: string; actor_id: string | null; related_ids?: unknown; payload?: unknown }[]; handover: { ack_status?: string; is_stale?: boolean; handover_id?: string } | null }
export interface IntakeResult { incident_id: string; display_id: string; message_id: string; job_id: string; status: string; version: number }
export interface MessageResult { message_id: string; incident_id: string; incident_version: number; incident_status: string; job_id: string | null; request_id: string | null }
