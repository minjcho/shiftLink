// F2 projections of the shared Incident detail response. F0 owns the full DTO.
export type ActionStatus = 'PROPOSED' | 'APPROVED' | 'IN_PROGRESS' | 'COMPLETED' | 'REJECTED'
export interface ActionView {
  id: string
  status: ActionStatus
  version: number
  scope: string
  assignee_id: string
  due_at: string
  completion_criteria: string[]
  evidence_refs: string[]
  result_message_id: string | null
}
export interface ApprovalView {
  id: string
  action_id: string
  decision: 'APPROVE' | 'REJECT'
  reason: string
  actor_id: string
  created_at: string
  payload_hash: string
}
export interface IncidentView {
  id: string
  version: number
  status: string
  owner_id: string
  review_required: boolean
  review_reason: string | null
}
export interface SessionView { user_id: string; role: 'worker' | 'supervisor' }
export interface ResultView { id: string; text: string; author_id: string; received_at: string }
export interface EvidenceOption { id: string; label: string }
export type CommandKind = 'approval-decisions' | 'start' | 'completion'
export interface Versions { expected_version: number; expected_incident_version: number }
export type CommandBody = Versions & {
  decision?: 'APPROVE' | 'REJECT'; reason?: string; result?: string; evidence_refs?: string[]
}
export interface PendingCommand {
  readonly actionId: string
  readonly actorId: string
  readonly kind: CommandKind
  readonly key: string
  readonly serializedBody: string
}
export interface CommandData {
  action_id: string
  action_status: ActionStatus
  action_version: number
  incident_status: string
  incident_version: number
  verification_ready?: boolean
  unmet_requirements?: string[]
}
export type SendCommand = (command: PendingCommand) => Promise<CommandData>
