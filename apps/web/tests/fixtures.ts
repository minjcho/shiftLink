import type { IncidentDetail, Job, Me } from '../src/lib/types';
export const maintainer: Me = { user_id: '00000000-0000-4000-8000-000000000202', display_name: '정비 담당자', role: 'worker', site_id: 'site-1', shift_occurrence_id: 'shift-1', duties: ['MAINTENANCE'] };
export const reporter: Me = { ...maintainer, user_id: '00000000-0000-4000-8000-000000000201', display_name: '제보 작업자', duties: ['OPERATOR'] };
export const supervisor: Me = { ...maintainer, user_id: '00000000-0000-4000-8000-000000000203', display_name: '출발 책임자', role: 'supervisor', duties: [] };
export const equipment = [{ id: 'eq-1', code: 'CV-03', label: '이송 설비', aliases: ['3호기'] }];
export function detail(patch: Partial<IncidentDetail> = {}): IncidentDetail {
  return { id: 'incident-1', display_id: 'INC-001', title: '소음 기록', equipment_id: 'eq-1', status: 'INVESTIGATING', version: 3, owner_id: supervisor.user_id, waiting_for_input: true, review_required: false, review_reason: null,
    messages: [{ id: 'message-1', kind: 'REPORT', text: '들었다는 사실과 직접 관찰을 구분한 원문', author_id: reporter.user_id, received_at: '2026-10-09T02:00:00Z' }],
    requests: [{ id: 'request-1', purpose_code: 'VERIFY_SCOPE', question: '점검 범위는 무엇인가요?', target_user_id: maintainer.user_id, is_required: true, status: 'OPEN', evidence_refs: ['evidence-1'], response_message_id: null, created_at: '2026-10-09T02:01:00Z' }],
    actions: [], analysis: { run_id: 'run-1', base_version: 2, is_stale: true, decision: 'ASK_USER', facts: [{ text: '사람이 소리를 들었다고 진술함', kind: 'HUMAN_STATEMENT', source_refs: ['evidence-1'] }], hypotheses: ['원인은 확인되지 않았음'], missing_information: ['실제 점검 범위'], source_refs: ['evidence-1'], reason: '범위 확인이 필요합니다.' },
    evidence: [{ id: 'evidence-1', source_type: 'log', source_id: 'source-1', source_version: '1', excerpt: '초기 점검 완료.' }], latest_job: { id: 'job-1', status: 'SUCCEEDED' }, recent_events: [], handover: null, allowed_commands: ['add_message', 'reply_request'], ...patch };
}
export const job: Job = { id: 'job-1', status: 'SUCCEEDED', attempt: 1, latest_run_id: 'run-1', latest_run_status: 'WAITING_INPUT', mode: 'fake', error_code: null, retryable: false };
export const response = (data: unknown, status = 200) => new Response(JSON.stringify({ data }), { status, headers: { 'Content-Type': 'application/json' } });
export const failure = (code: string, status = 409) => new Response(JSON.stringify({ error: { code, message: '새 정보가 있습니다.', current_version: 4 } }), { status, headers: { 'Content-Type': 'application/json' } });
