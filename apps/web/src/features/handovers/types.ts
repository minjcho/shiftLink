import type { Analysis, Evidence, Message, RequestItem } from '../../lib/types';

export interface Person { id: string; display_name?: string }
export interface Shift { id: string; label?: string; starts_at?: string; ends_at?: string; supervisor_id: string }
export interface ShiftPair { from_shift_occurrence_id: string; to_shift_occurrence_id: string }
export interface ShiftList { items: Shift[]; allowed_pairs: ShiftPair[] }
export interface SnapshotAction {
  id: string; title?: string; status: string; scope?: string; assignee_id: string;
  completion_criteria?: unknown; result_message_id?: string | null; completion_evidence_id?: string | null;
  evidence_refs?: string[]; due_at?: string | null; revision?: number;
}
export interface SnapshotApproval {
  id: string; action_id: string; decision: string; reason?: string; actor_id?: string;
  created_at?: string; action_revision?: number; payload_hash?: string; approved_payload_snapshot?: unknown;
}
export interface HandoverSnapshot {
  incident_id?: string; id?: string; display_id?: string; title?: string; equipment_id?: string;
  equipment?: { id?: string; code?: string; label?: string }; status: string; version: number;
  owner_id?: string; owner?: Person | null; owner_shift_occurrence_id?: string;
  assignee_id?: string | null; assignee?: Person | null; review_required?: boolean; review_reason?: string | null;
  messages: Message[]; requests: RequestItem[]; open_requests?: RequestItem[];
  actions: SnapshotAction[]; approvals: SnapshotApproval[]; evidence: Evidence[];
  analysis?: Analysis | null; facts?: { text: string; kind: string; source_refs: string[] }[];
}
export interface HandoverItem {
  id: string; incident_id: string; revision: number; latest_revision: number;
  snapshot_version: number; snapshot_token: string; snapshot: HandoverSnapshot;
  ack_status: string; ack_applied_version: number | null; is_stale: boolean;
  current_owner_id: string; current_owner?: Person | null; current_owner_shift_occurrence_id?: string;
  current_incident_version: number; current_incident_status: string;
  current_analysis_base_version?: number | null; current_analysis_is_stale?: boolean;
  current_assignee_id?: string | null; current_assignee?: Person | null;
  can_ack: boolean; is_resolved: boolean; requires_ack: boolean; previously_acknowledged: boolean;
  added_since_cutoff: boolean;
}
export interface PendingAddition {
  incident_id: string; display_id?: string; title?: string; status?: string;
  equipment?: { code?: string; label?: string }; equipment_id?: string; added_since_cutoff?: boolean;
}
export interface Handover {
  handover_id?: string; id?: string; from_shift_occurrence_id: string; to_shift_occurrence_id: string;
  from_shift?: Shift; to_shift?: Shift; receiver_id: string; receiver?: Person;
  cutoff_at: string; refreshed_at?: string; items: HandoverItem[]; pending_additions: PendingAddition[];
}
export interface AckResult { item_id: string; revision: number; ack_status: string; incident_version: number; owner_id: string; assignee_id: string | null }
export interface HandoverSummaryData {
  id?: string; handover_id?: string; item_id?: string; revision?: number; latest_revision?: number;
  ack_status?: string; snapshot_version?: number | null; ack_applied_version?: number | null;
  is_stale?: boolean; added_since_cutoff?: boolean; cutoff_at?: string; is_resolved?: boolean;
  previously_acknowledged?: boolean;
}
