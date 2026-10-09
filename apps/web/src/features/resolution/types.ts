export interface Verification {
  id: string; decision: 'RESOLVE' | 'RETURN'; notes: string; checked_version: number;
  applied_version: number; created_at: string; evidence_refs: string[];
  reviewer: { id: string; display_name: string | null };
}
export interface ResolutionCase {
  id: string; resolved_version: number; evidence_refs: string[]; created_at: string;
  reviewer: { id: string; display_name: string | null } | null; resolved_at: string | null;
  snapshot_json: { verification?: Verification; messages?: { id: string; text: string; kind: string }[] };
}
export interface Resolution {
  ready: boolean; unmet_requirements: string[]; checked_version: number;
  can_resolve: boolean; can_return: boolean; latest_verification: Verification | null;
  case: ResolutionCase | null;
}
export interface VerificationResult {
  incident_id: string; incident_status: string; incident_version: number;
  verification_id: string; case_id: string | null; resolved_at: string | null;
}
