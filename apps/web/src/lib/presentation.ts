export const statusLabels: Record<string, string> = { OPEN: '접수 · 조사 대기', INVESTIGATING: '조사 중', ACTION_REQUIRED: '작업 제안 · 승인 대기', IN_PROGRESS: '업무 진행 중', PENDING_VERIFICATION: '최종 검증 대기', RESOLVED: '사건 해결', QUEUED: '조사 대기', RUNNING: 'AI 조사 중', SUCCEEDED: 'AI 실행 완료', FAILED: 'AI 조사 실패 · 제보는 저장됨', SUPERSEDED: '새 정보로 이전 조사 종료', WAITING_INPUT: '담당자 답변 대기' };
export function label(status: string) { return statusLabels[status] ?? status; }
export function time(value?: string | null) { return value ? new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', dateStyle: 'short', timeStyle: 'medium' }).format(new Date(value)) : '미수집'; }
export function person(id?: string | null) { const names: Record<string, string> = { '00000000-0000-4000-8000-000000000201': '제보 작업자', '00000000-0000-4000-8000-000000000202': '정비 담당자', '00000000-0000-4000-8000-000000000203': '출발 책임자', '00000000-0000-4000-8000-000000000204': '수신 책임자' }; return id ? names[id] ? `${names[id]} (${id})` : id : '미수집'; }

export function personName(id?: string | null) { return person(id).replace(/ \(.*\)$/, ""); }
