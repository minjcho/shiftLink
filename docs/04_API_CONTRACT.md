# 04. HTTP API 계약

> v0.3 구현 문서 · 2026-10-09 · **설계 계약 / 구현·런타임 검증 NOT_RUN**
>
> [도메인 모델](03_DOMAIN_MODEL.md)이 enum·권한·버전의 기준이다. 아래 예시는 합성 ID와 시각이며 실행 응답이 아니다. Agent 도구는 [05_AGENT_DESIGN.md](05_AGENT_DESIGN.md)를 따른다.

## 1. 공통 규칙

Base path `/api/v1`. ID는 UUID 문자열, 시각은 UTC ISO 8601, unknown은 null이다. 불필요한 필드는 Pydantic `extra=forbid`에 해당하는 계약으로 거부한다. actor_id·role·site_id·owner_id·assignee_id를 명령 body에서 받지 않는다. API key와 SESSION_SECRET은 서버에만 둔다.

모든 **업무 변경 POST**는 `Idempotency-Key`를 요구한다. 유일 범위는 `(site, actor, key)`, 해시는 method·정규화 route·정규화 body를 포함한다. 인증·site 확인 후 완료 receipt를 상태·버전 검사보다 먼저 반환한다. 같은 키와 다른 입력은 `409 IDEMPOTENCY_CONFLICT`, 처리 중 동일 키는 `409 COMMAND_IN_PROGRESS`다. 동일 요청 재시도는 최초 HTTP 상태·body를 반환하고 `Idempotent-Replayed: true`를 붙인다. 인증 부트스트랩 `/demo/session`만 아래의 명시적 예외를 적용한다.

```json
{
  "data": {"id": "11111111-1111-4111-8111-111111111111"},
  "meta": {"request_id": "http-101", "dataset_id": "DEMO-A", "demo_mode": true}
}
```

```json
{
  "error": {
    "code": "VERSION_CONFLICT",
    "message": "내용이 변경됐습니다. 최신 내용을 다시 확인해 주세요.",
    "retryable": false,
    "current_version": 8,
    "details": {"target": "incident", "expected_version": 7}
  },
  "meta": {"request_id": "http-102"}
}
```

오류를 성공 data로 감싸지 않는다. `current_version`은 관련 버전을 알 수 없으면 null이다. 409가 발생한 입력은 화면에 남기고 최신 조회 후 사람이 다시 판단하도록 한다. 버전만 바꾸어 승인·ACK·해결을 자동 재전송하지 않는다.

| HTTP | code | 화면/호출자 처리 |
|---|---|---|
| 401 / 403 | UNAUTHENTICATED / FORBIDDEN | 세션 확인 또는 허용 범위 안내 |
| 404 | RESOURCE_NOT_FOUND | 다른 사업장 자원도 동일하게 처리 |
| 409 | VERSION_CONFLICT / INVALID_STATE / REQUEST_CLOSED | 입력 보존, 최신 사건 재조회 |
| 409 | IDEMPOTENCY_CONFLICT / COMMAND_IN_PROGRESS | 새 명령인지 구분. 진행 중 요청은 같은 키로 제한 재시도 |
| 409 | HANDOVER_STALE / INCIDENT_RESOLVED / REVIEW_REQUIRED | 최신 인계 확인, 새 제보 또는 후속 검토 안내 |
| 422 | VALIDATION_ERROR / EVIDENCE_INVALID / READINESS_NOT_MET / SHIFT_SCOPE_INVALID | details의 미충족 항목 표시 |
| 422 | SHIFT_ASSIGNMENT_MISSING | seed 교대·책임자 배정 수정 필요 |
| 429 / 503 | RETRY_LATER / SERVICE_UNAVAILABLE | 안내된 지연 후 같은 키 재시도 |

페이지형 조회는 `data.items`, `data.next_cursor|null`를 반환한다. 작은 데모에서도 site·교대 범위와 필터는 서버에서 적용한다. 권한이 없는 객체의 내용이나 현재 버전을 오류에 노출하지 않는다.

## 2. Endpoint와 기능 담당

| 방법·경로 | 목적 | 서버 권한 | 담당 |
|---|---|---|---|
| POST `/demo/session` | 허용된 데모 계정 세션 시작·전환 | 데모 전환 활성 환경만 | F0 |
| GET `/me`, `/equipment`, `/shifts` | 세션·기초 자료 | 로그인한 동일 site | F0 |
| POST `/incidents` | 사건·최초 원문·Job 접수 | worker 또는 supervisor | F1 재곤 |
| GET `/incidents`, `/incidents/{id}` | 목록·통합 상세 | 동일 site | F1, 각 기능이 자기 필드 기여 |
| POST `/incidents/{id}/messages` | 추가 원문·지정 질문 답변 | 동일 site, 답변은 지정자 | F1 재곤 |
| POST `/actions/{id}/approval-decisions` | 승인·반려 | 현재 owner인 supervisor | F2 민재 |
| POST `/actions/{id}/start` | 승인 작업 착수 | 서버 지정 assignee | F2 민재 |
| POST `/actions/{id}/completion` | 작업 결과 제출 | 서버 지정 assignee | F2 민재 |
| POST `/handovers` | 교대 쌍의 기본 인계 생성·갱신 | 출발 교대 지정 supervisor | F3 재곤 |
| GET `/handovers/{id}` | 현재 또는 과거 항목 revision | 지정 출발·수신 책임자 | F3 재곤 |
| POST `/handovers/{id}/items/{item_id}/ack` | 사건별 인수·owner 이전 | 지정 수신 supervisor | F3 재곤 |
| POST `/incidents/{id}/verification` | 해결 확인·반려 | 현재 owner인 supervisor | F4 민재 |
| GET `/cases` | 해결 사례와 snapshot | 동일 site | F4 민재 |
| GET `/jobs/{id}` | 비동기 상태·run 요약 | 관련 사건을 읽을 수 있는 사용자 | F1 재곤 |
| POST `/jobs/{id}/retry` | 실패 Job 재시도 | 현재 사건 owner인 supervisor | F1 재곤 |
| GET `/evidence/{id}` | 근거 원문·출처 | 동일 site, 관련 사건 접근 가능 | F0/F1 |

`update_status`, 임의 tool 실행, owner 수동 지정, 승인 후 편집, 작업 취소·재배정, 별도 Report 연결 API는 Phase 1에 없다. F2의 Action 생성은 F1 최종 확정기가 호출하는 내부 도메인 서비스이며 브라우저 생성 endpoint가 아니다.

### F1 → F2 내부 확정 인터페이스

```text
finalize_action_proposal(
  tx, *, incident_id, run_id, input_version, draft_id, trigger_event_id
) -> {action_id, created, action_version}
```

F2 서비스는 caller-owned 최종 트랜잭션에 참여한다. 현재 run·Incident·input_version에 속한 draft, 허용 근거, 서버 담당표, review_required=false, generation=1 유일키를 검사한다. 자체 commit·모델 호출은 하지 않는다. 기존 generation 작업이 있으면 새 작업을 만들지 않고 해당 ID를 반환하며 완료·반려 작업을 다시 활성화하지 않는다. F1 최종 확정기는 현재 lease 검증과 부모 버전의 한 번 증가, 최종 decision·Job·Run 기록을 책임진다. F2는 생성 여부와 같은 트랜잭션에 저장할 Action 이벤트를 제공한다.

## 3. 데모 세션과 읽기 경계

**POST `/demo/session` → 200**

```json
{"account_key":"maintainer"}
```

허용 값은 seed에 등록된 `reporter / maintainer / outgoing_supervisor / incoming_supervisor`다. 서버가 account_key를 실제 user·site·role·교대 배정에 매핑한다. 이는 제한된 데모 계정 전환이며 임의 role이나 user ID 입력이 아니다.

이 endpoint는 최초 인증 이전 명령이므로 **Idempotency-Key 예외**다. 반복 호출은 선택 계정의 세션을 새로 발급·회전할 뿐 업무 상태를 바꾸지 않는다. `DEMO_ACCOUNT_SWITCH_ENABLED=false`이면 404로 비활성화한다. 요청 Origin을 `ALLOWED_ORIGINS`와 정확하게 비교하고, 브라우저 이외 호출도 승인된 Origin을 요구한다. 나머지 쓰기에도 같은 Origin 검증을 적용한다. CORS credentials는 명시 허용 origin에만 제공한다.

세션은 HttpOnly·SameSite=Lax 쿠키를 사용하고 HTTPS 환경에서는 Secure를 켠다. `SESSION_COOKIE_SECURE=false`는 로컬 HTTP 개발에 한한다. session secret은 `.env.example`에서 빈 값으로 두고 실제 로컬 환경에서 주입한다. 공개 데모는 제한된 접근으로 운영하며 이 전환 방식이 실제 운영 인증을 대신한다고 주장하지 않는다.

세션은 로그인 시 서버가 선택한 같은 사업장의 교대 배정에 고정된다. 매 요청 enabled·site·배정을 재검사한다. 배정이 삭제되면 403, 유효 세션이 없거나 교대/site가 맞지 않으면 401이다. 교대가 없는 새 로그인은 422 SHIFT_ASSIGNMENT_MISSING이며 이전 세션을 보존한다. `0002_session_shift` 이전 token은 재로그인이 필요하다. POST `/demo/session`도 아래 `/me`와 같은 data 필드를 반환한다.

GET `/me`의 data는 `user_id, display_name, role, site_id, shift_occurrence_id, duties`다. meta.build는 `app_commit_sha, working_tree_dirty, agent_mode, search_mode`만 제공하고 불명은 null로 남긴다. 전체 환경 값은 반환하지 않는다.

GET `/equipment`는 id·code·label·aliases, GET `/shifts`는 허용 교대 발생 ID·시작/종료·supervisor와 허용 인계 쌍을 반환한다. 상세·목록에서 계산한 `allowed_commands`는 UI 표시 보조이며 서버 명령 검사를 대체하지 않는다.

Incident 상세의 단일 `handover` 요약은 같은 사업장이고 현재 사용자가 생성자 또는 수신자인 인계만 대상으로 한다. 여러 인계가 같은 사건을 포함하면 `created_at DESC, id DESC`의 첫 인계를 선택한다. 최신 인계의 비참여자에게는 그 인계의 존재나 내용 대신 자신이 읽을 수 있는 과거 인계의 요약만 반환한다. snapshot·token은 이 요약에 포함하지 않는다.

## 4. 제보 접수와 메시지·답변

**POST `/incidents` → 202 Accepted**

```json
{
  "equipment_id": "00000000-0000-4000-8000-000000000103",
  "text": "CV-03에서 소음과 진동이 있습니다. 초기 점검은 완료했다고 들었습니다.",
  "observed_at": null
}
```

```json
{
  "data": {
    "incident_id": "11111111-1111-4111-8111-111111111111",
    "display_id": "INC-0001",
    "status": "OPEN",
    "version": 1,
    "message_id": "33333333-3333-4333-8333-333333333333",
    "job_id": "44444444-4444-4444-8444-444444444444",
    "received_at": "2026-10-09T02:10:00Z"
  },
  "meta": {"request_id": "http-101", "dataset_id": "DEMO-A", "demo_mode": true}
}
```

사건·원문·이벤트·Job·receipt를 한 번에 저장한다. title은 서버가 원문에서 짧게 만들거나 기본 제목을 사용한다. owner는 현재 교대 지정 책임자다. 202는 접수 완료이며 AI 성공이나 Action 생성 완료가 아니다. 이후 모델 실패는 Job 상태로 전달한다.

**POST `/incidents/{id}/messages` → 202**

```json
{
  "text": "외관만 확인했고 추가 점검 결과는 없습니다.",
  "expected_version": 3,
  "reply_to_request_id": "55555555-5555-4555-8555-555555555555",
  "observed_at": null,
  "correction_of": null
}
```

`reply_to_request_id`와 `correction_of`를 모두 non-null로 보내면 `422 VALIDATION_ERROR`다. Message·Request·Incident 버전·이벤트·Job·receipt를 생성하거나 바꾸지 않는다. reply_to_request_id=null이면 추가 메시지다. 값이 있으면 같은 사건의 OPEN Request·지정 응답자·부모 버전을 확인하고 Message 저장과 Request ANSWERED를 한 트랜잭션으로 수행한다. response data는 `message_id, request_id|null, request_version|null, incident_id, incident_status, incident_version, job_id|null`다. 사건은 한 번만 +1이다.

새 일반 메시지도 상태명이 같아도 반드시 버전이 증가한다. PENDING_VERIFICATION에서는 INVESTIGATING으로 옮기고 새 조사 Job을 만든다. review_required 상태에서는 원문 기록은 허용하되 신규 작업·검증 준비가 차단됨을 표시한다. RESOLVED에 늦게 온 입력은 거부 입력 이벤트와 receipt로 보존하고 `409 INCIDENT_RESOLVED`와 새 제보 안내를 반환한다.

## 5. 목록과 통합 상세

GET `/incidents?status=IN_PROGRESS&equipment_id=...&scope=mine&cursor=...`를 지원한다. scope는 `all / mine`이고 mine은 현재 owner·Action assignee·OPEN Request 대상 중 하나인 사건이다. all도 동일 site 범위다. 페이지 크기 기본 20, 최대 100, 정렬은 `updated_at DESC, id DESC`다.

**GET `/incidents/{id}` → 200**의 최소 data 구조:

```json
{
  "id": "11111111-1111-4111-8111-111111111111",
  "display_id": "INC-0001",
  "equipment_id": "00000000-0000-4000-8000-000000000103",
  "status": "IN_PROGRESS",
  "version": 7,
  "owner_id": "00000000-0000-4000-8000-000000000203",
  "review_required": false,
  "review_reason": null,
  "waiting_for_input": false,
  "messages": [{"id":"33333333-3333-4333-8333-333333333333","kind":"REPORT","text":"초기 점검 완료 기록이 있습니다."}],
  "requests": [],
  "actions": [{"id":"77777777-7777-4777-8777-777777777777","status":"IN_PROGRESS","version":3,"revision":1,"assignee_id":"00000000-0000-4000-8000-000000000202","is_required":true}],
  "approvals": [{"id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","action_id":"77777777-7777-4777-8777-777777777777","action_revision":1,"decision":"APPROVE","payload_hash":"sha256-example-only"}],
  "analysis": {"run_id":"99999999-9999-4999-8999-999999999999","base_version":4,"is_stale":true,"decision":"PROPOSE_ACTION","source_refs":["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"]},
  "handover": null,
  "evidence": [{"id":"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb","source_type":"sop","source_id":"00000000-0000-4000-8000-000000000701","source_version":"1","excerpt":"후속 확인 작업은 실제 수행 전 책임자의 승인을 받는다."}],
  "recent_events": [],
  "latest_job": {"id":"44444444-4444-4444-8444-444444444444","status":"SUCCEEDED"},
  "allowed_commands": ["complete_action"]
}
```

예시는 응답 형태만 보여준다. 실제 상세에는 저장된 질문·답변·승인·결과·근거·이벤트를 모두 조회해 표시한다. Action 패널에 scope·assignee·due_at·completion_criteria·승인 내용 해시를 제공한다. recent_events는 최신 50개, Phase 1 데모 전체 이력은 그 안에 들어오도록 하며 장기 페이지네이션은 후속 범위다. model analysis와 authoritative status를 다른 필드로 유지한다.

## 6. 작업 승인·착수·결과

모든 Action 명령은 `expected_version`으로 Action, `expected_incident_version`으로 부모 Incident를 검사한다. 잠금은 Incident를 먼저 잡는다. 동일 receipt는 이후 버전과 상태가 바뀌었어도 최초 응답을 반환한다.

**POST `/actions/{id}/approval-decisions` → 200**

```json
{"decision":"APPROVE","reason":"제시된 데모 SOP 범위와 완료 기준을 확인했습니다.","expected_version":1,"expected_incident_version":5}
```

PROPOSED 상태와 현재 owner supervisor를 확인한다. APPROVE는 승인 snapshot·payload_hash를 저장하고 APPROVED로, REJECT는 비어 있지 않은 사유와 함께 REJECTED·INVESTIGATING·review_required=true로 바꾼다. 두 경우 모두 Action +1, Incident +1이다. 응답은 `action_id, action_status, action_version, approval_id, payload_hash, incident_status, incident_version, review_required`다.

**POST `/actions/{id}/start` → 200**

```json
{"expected_version":2,"expected_incident_version":6}
```

승인 해시·APPROVED·세션 사용자의 assignee 일치·review_required=false를 확인한다. 응답은 `action_id, action_status=IN_PROGRESS, action_version, incident_status=IN_PROGRESS, incident_version, started_at`다. supervisor라는 이유만으로 타인의 작업을 대신 시작하지 않는다.

**POST `/actions/{id}/completion` → 200**

```json
{
  "result":"합성 데모 SOP에 따른 점검 범위를 수행했고 모의 재확인 결과를 기록했습니다.",
  "evidence_refs":[],
  "expected_version":3,
  "expected_incident_version":8
}
```

IN_PROGRESS·assignee·승인 내용과 현재 상태를 확인한다. result는 필수이며 서버가 작성자·시각이 있는 Message와 completion_report Evidence를 만든다. evidence_refs는 추가 기존 근거이며 없어도 결과 원문 근거는 생성된다. Action COMPLETED 이후 종료 준비 서비스를 호출한다.

응답은 `action_id, action_status=COMPLETED, action_version, result_message_id, completion_evidence_id, incident_status, incident_version, verification_ready, unmet_requirements[]`다. 조건 충족 시 PENDING_VERIFICATION, 아니면 아직 해결 전임을 표시한다. 정상 완료의 검증 준비에 추가 모델 호출은 필요하지 않다. 결과 제출은 실제 현장의 작업 수행을 독립적으로 검증한 증거가 아니다.

## 7. 교대 인계와 항목 ACK

**POST `/handovers` → 신규 201 / 기존 200**

```json
{
  "from_shift_occurrence_id":"00000000-0000-4000-8000-000000000301",
  "to_shift_occurrence_id":"00000000-0000-4000-8000-000000000302"
}
```

출발 책임자·동일 site·허용된 시간상 인접 교대 쌍을 서버가 확인한다. 수신 책임자를 서버 담당표로 고정한다. 고유키가 같은 기존 Handover는 재사용하고 내용 변경 항목에만 새 revision을 만든다. 다른 멱등 키로 재전송해도 Handover가 추가 생성되지 않는다. 동시 생성은 UNIQUE 충돌 뒤 같은 객체를 조회한다.

data는 `handover_id, cutoff_at, receiver_id, items[]`이며 item에는 `id, incident_id, revision, snapshot_version, snapshot_token, snapshot, ack_status, ack_applied_version|null, is_stale`를 담는다. AI 설명 없이 사용할 수 있다. 범위와 이미 이전된 항목의 재확인 규칙은 도메인 D04를 따른다.

GET `/handovers/{id}`는 최신 항목 revision과 cutoff 이후 추가 대상의 `added_since_cutoff`를 제공한다. `?item_id=...&revision=1`로 이미 표시한 불변 revision을 읽을 수 있다. 과거 조회도 현재 최신 revision·stale·해결 여부를 별도 표시한다.

**POST `/handovers/{id}/items/{item_id}/ack` → 200**

```json
{"revision":1,"snapshot_token":"server-issued-content-token","expected_version":7}
```

expected_version은 snapshot이 담은 Incident 버전이다. 최신 revision·token·현재 Incident 버전·지정 수신자를 검사한다. 성공 예시는 `snapshot_version=7, incident_version=8, ack_applied_version=8`이며 owner를 수신 책임자로 옮기고 assignee는 유지한다. ACK 자체는 인계 revision을 새로 만들지 않는다.

응답 data는 `item_id, revision, ack_status=ACKNOWLEDGED, snapshot_version, ack_applied_version, incident_version, owner_id, assignee_id, acknowledged_by, acknowledged_at`다. 이후 v9 내용 변경은 새 revision으로 재확인하며 이미 이전된 owner를 되돌리지 않는다. 오래된 ACK는 `409 HANDOVER_STALE`과 최신 revision을 반환한다. 해결 후 새 ACK는 409지만 이전 성공 ACK의 같은 receipt 재전송은 먼저 성공 응답을 재사용한다.

## 8. 최종 검증과 해결 사례

**POST `/incidents/{id}/verification` → 200**

```json
{
  "decision":"RESOLVE",
  "notes":"승인된 범위의 결과와 남은 필수 질문이 모두 확인된 것을 검토했습니다.",
  "evidence_refs":[],
  "expected_version":9
}
```

RESOLVE는 현재 owner supervisor·PENDING_VERIFICATION·최신 버전·비어 있지 않은 notes와 도메인 D06의 모든 조건을 검사한다. server-generated completion_report를 기본 종료 근거로 사용하며 evidence_refs는 추가 근거다. 빈 Action 집합이나 review_required는 거부한다. 성공 data는 `incident_id, incident_status=RESOLVED, incident_version, verification_id, case_id, resolved_at`다.

RETURN 역시 현재 owner·최신 버전·PENDING_VERIFICATION·사유를 요구한다. Incident를 INVESTIGATING·review_required=true로 옮기며 완료 Action과 결과를 보존한다. data의 case_id와 resolved_at은 null이다. Phase 1은 후속 검토 필요 상태에서 멈추며 새 Action을 생성하지 않는다.

GET `/cases?incident_id=...&cursor=...`는 해결 snapshot·검토자·시각·근거를 반환한다. 별도의 수정 API는 없다. 현재 사례가 과거 자료로 검색될 때 source_type=case를 유지한다.

## 9. Job 재시도·근거·진단

GET `/jobs/{id}`는 `id, incident_id, status, attempt, latest_run_id, latest_run_status, mode, started_at, finished_at, error_code, retryable`을 반환한다. 관련 사용자는 업무 상태·간단한 실패 안내만 읽는다. 현재 owner supervisor에게는 정제한 run 요약·도구명·결과 ID·버전·usage를 추가할 수 있다. 비밀·내부 추론·무관한 원문은 제공하지 않는다. 별도 관리 endpoint는 Phase 1 필수가 아니다.

**POST `/jobs/{id}/retry` → 202** body `{}`. Idempotency-Key 필수다. 재시도 가능한 FAILED, 최대 시도 미초과, 미해결·review_required=false를 확인한다. 같은 Job ID·trigger·dedupe_key를 유지하고 QUEUED로 되돌린다. claim 시 새 attempt·AgentRun을 만든다. RUNNING은 409, SUCCEEDED는 현재 상태 200, SUPERSEDED는 새 최신 Job을 조회하도록 409를 반환한다. Job 상태만 바꾸므로 Incident 버전은 증가하지 않는다. 거절·보안 차단을 자동 재시도로 우회하지 않는다.

GET `/evidence/{id}`는 source_type·source_id·source_version·위치·excerpt·적용 범위·관측/조회 시각을 반환한다. 존재하지 않거나 범위 밖이면 404다. 외부 검색·모델 오류는 Job/run에서 ERROR와 코드로 보존하고 EMPTY로 바꾸지 않는다.

## 10. 화면 갱신·변경 규칙·검증

초기 폴링은 `VITE_POLL_INTERVAL_MS=2000`이다. 숨겨진 탭에서 중지하고 현재 상세·최근 Job을 읽는다. 입력 성공 후 응답의 최신 version을 반영한다. 202 다음의 FAILED는 접수 실패로 되돌리지 않는다. 조회 실패·조사 중·질문 대기·검증 대기를 구분한다.

F0가 공유 DTO·enum·OpenAPI 통합을 조정하고 각 기능 담당자가 요청·응답·화면·시험을 함께 완성한다. 변경 시 [도메인](03_DOMAIN_MODEL.md)·[Agent](05_AGENT_DESIGN.md)·[UI](06_UI_SPEC.md)·[시험](07_TEST_PLAN.md)을 동기화한다. 구현 이후 실제 OpenAPI와 이 문서의 endpoint·상태·버전·오류 계약을 대조한다. 현재 OpenAPI 생성·HTTP 호출·권한·동시성 시험은 모두 NOT_RUN이다.

## F2 실연결 보완 — 2026-10-09

승인·착수·결과 API는 F1 세션·Origin·execute_command를 사용하며 성공 응답 DTO는 기존 계약을 유지한다. 같은 완료 receipt는 권한을 위한 인증·사업장 범위 확인 후 최신 업무 상태보다 먼저 재사용한다. 신규 명령은 잠금 안에서 현재 owner/assignee와 두 버전을 검사한다. 내부 readiness port의 키 `ready`는 완료 HTTP의 `verification_ready`로 임의 변경하지 않는다. 전체 상세의 준비/최종 검증 필드와 F2 패널 연결은 후속 작업이다.
