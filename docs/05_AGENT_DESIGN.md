# 05. Agent·도구·실행 설계

> v0.3 구현 문서 · 2026-10-09. 구현할 계약이며 현재 실행 결과가 아니다. F1 담당 제안: 재곤. 상태·데이터는 [03_DOMAIN_MODEL.md](03_DOMAIN_MODEL.md), 외부 API는 [04_API_CONTRACT.md](04_API_CONTRACT.md)가 기준이다.

## 1. 책임과 기능 연결

| 주체 | 책임 | 경계 |
|---|---|---|
| F1 접수·조사 | 원문·답변 화면/API/DB, Agent·검색·질문 최종 저장·실행 검사 | 모델에게 승인·ACK·해결 권한을 주지 않음 |
| F2 작업 | Action 후보의 정식 확정 서비스, 승인·착수·결과 화면/API/DB | Agent 코드와 후보 생성은 F1이 소유 |
| F3 인계 | 서버의 미해결 집합·snapshot·ACK | Phase 1 인계 목록에 추가 모델 호출 불필요 |
| F4 해결 | 준비 조건 검사·사람 검증·해결 snapshot | 모델 판단만으로 RESOLVED 불가 |
| F0 공통 기반 | 세션·버전·잠금·receipt·Job 계약 | 모델 호출 중 DB 잠금 유지 금지 |
| F5 검증 | 실제 실행과 저장된 효과의 연결 | fake·live·replay 결과 분리 |

예정 구현 위치는 `apps/api/app/agent/`와 F1의 `features/intake/`다. 이는 아직 존재하지 않는 예정 경로다. 같은 서비스 코드의 별도 단일 worker를 사용하고 서비스 요청마다 Codex 프로세스를 실행하지 않는다.

## 2. 한 번의 조사

1. API가 원문·이벤트·Job을 같은 트랜잭션에 저장한다. 접수 응답과 모델 성공 여부는 별개다.
2. Worker가 짧은 `FOR UPDATE SKIP LOCKED`로 Job을 claim한다. `attempt`를 증가시키고 새 `lease_token`과 만료 시각을 기록한다.
3. 최초 `OPEN → INVESTIGATING` 전이가 필요하면 커밋한 뒤 `input_version`을 고정한다. 최신 원문·유효 Request·Action·승인·배정표·현재 근거로 모델 입력을 만든다.
4. 모델이 네 도구 중 필요한 도구를 선택한다. 조회 결과와 후보는 run에 연결하며 아직 Request·정식 Action을 만들지 않는다.
5. 최종 DTO의 분기·출처·대상·후보·기존 ID를 검증한다. 업무 반영 직전에 현재 Incident 버전과 실행 lease를 다시 검사한다.
6. 최종 확정기는 F2의 Action 생성 서비스를 같은 트랜잭션에서 호출하거나 F1의 질문을 저장한다. analysis·업무 이벤트·버전·Job/Run 종료도 일관되게 반영한다.
7. 질문을 저장하면 run은 `WAITING_INPUT`으로 종료한다. 지정 담당자 답변은 별도 message와 새로운 Job/Run을 만든다. 답변을 기다리는 동안 호출을 반복하지 않는다.

F2 생성 서비스 계약은 `finalize_action_proposal(tx, *, incident_id, run_id, input_version, draft_id, trigger_event_id) → {action_id, created, action_version}`다. F1은 최종 DTO의 selected_draft_id를 draft_id로 전달한다. F2는 고유키 `(incident_id, action_slot, action_generation=1)`와 활성 작업 제약을 검사하고 caller-owned 트랜잭션에 참여하며 자체 commit·모델 호출을 하지 않는다. 부모 Incident.version은 F1 finalizer가 업무 효과 전체에 대해 한 번만 증가시킨다. 모델 인자를 도메인 객체로 바로 저장하지 않는다.

## 3. 모델 입력과 출처

초기 입력은 현재 사건·버전, 이번 trigger의 원문, 유효 질문/답변과 Action, 서버가 허용한 답변 대상, 근거 ID 목록이다. 새 업무 이벤트마다 DB에서 다시 구성한다. 이전 run의 문장만으로 현재 상태를 복원하지 않는다.

- 사람의 진술, 기록에 적힌 사실, 시스템 상태, 가설을 구분한다.
- 과거 사례는 비교 자료다. 다른 설비에서 발생한 현상은 현재 설비의 사실로 변환하지 않는다.
- 질문의 예상 답, 시나리오 ID, 테스트 기대값, fixture 이름에 담긴 정답은 모델에게 주지 않는다.
- 자료의 명령문은 분석 대상이다. 자료가 도구·권한·런타임 지침을 바꿀 수 없다.
- `source_ref`는 서버가 발급한 근거 ID다. 이번 run의 초기 입력 또는 실제 도구 응답에 포함된 근거만 최종 인용할 수 있다. 승인된 SOP의 버전·절·범위와 사람 진술의 작성자·시각을 보존한다.

초기 입력의 부가 이력은 설정된 크기 안에서 선택한다. DB 원문과 Evidence는 그대로 보존하면서 현재 상태·trigger 원문·필요한 질문/답변·Action·승인·참조 근거를 우선하고 본문 중복을 제거한다. 선택에서 생략된 Evidence는 이번 run의 본 출처 집합에 넣지 않는다. 필수 정보를 온전히 담을 수 없으면 `CONTEXT_LIMIT`으로 종료하며 해당 입력의 모델 호출과 업무 후보 확정을 하지 않는다.

각 모델 호출 직전에 시스템 지침·입력·도구 정의·최종 출력 schema를 직렬화한 UTF-8 바이트 수에 출력 여유를 더해 `AGENT_MAX_INPUT_BYTES`와 비교한다. 도구 결과와 프로토콜 output이 누적된 후에도 같은 검사를 적용하며, 중간 JSON이나 protocol item을 임의 절단하지 않는다. 이 바이트 한도는 모델별 token 수나 context window 적합성의 보장이 아니므로 실제 모델의 한도와 live 결과에 맞춰 설정한다.

## 4. 네 가지 도구

아래는 애플리케이션 DTO 계약이다. 모든 object schema는 `additionalProperties:false`, 모든 필드는 `required`로 선언한다. 선택값도 필드를 생략하지 않고 `null`을 허용한다. actor·site·run·input_version은 서버에서 주입하고 모델 입력으로 받지 않는다.

| 도구 | 입력 shape | 결과 data | 서버 검사 |
|---|---|---|---|
| `get_equipment_context` | `{equipment_id: UUID}` | 설비·최근 로그·서버 배정표·출처 | 현재 Incident 설비와 ID 일치, 동일 사업장 |
| `search_documents` | `{query: string, equipment_id: UUID}` | 승인 SOP chunk·버전·절·발췌·출처 | 동일 사업장, approved, 현재 설비 적용 범위, 결과·길이 상한 |
| `search_similar_incidents` | `{query: string, equipment_id: UUID}` | 해결 case·설비·시각·결과·출처 | 동일 사업장, 해결된 case만; 다른 설비는 비교 자료라고 명시 |
| `propose_action` | `{scope: string, completion_criteria: string[], source_refs: UUID[]}` | `{draft_id: UUID, incident_id: UUID, input_version: int}` | 현재 run의 출처, 범위·기준 비어 있지 않음, 임시 후보만 저장 |

`propose_action`은 승인 여부·필수 제외·임의 assignee·기한·상태를 받지 않는다. 서버가 `is_required=true`, 허용 담당자, 기한 정책, `action_slot`과 generation을 정한다. 후보가 여러 개면 최종 DTO가 하나만 선택한다. draft 생성·검색·analysis 저장만으로 Incident.version을 올리지 않는다.

공통 도구 결과:

```json
{
  "outcome": "OK",
  "data": {"items": []},
  "source_refs": [],
  "partial": false,
  "error": null
}
```

`outcome`은 `OK | EMPTY | ERROR`다. 검색이 정상 완료됐으나 결과가 없을 때만 EMPTY다. ERROR에는 `{code, message, retryable}`가 있고 data는 null이다. 일부 자료만 반환한 경우 partial을 표시한다. 검색 장애·권한 오류를 빈 검색 결과로 바꾸지 않는다. 도구별 data는 위 표의 고정 schema로 검증하며, 모델이 넘긴 임의 JSON을 실행하지 않는다.

키워드 검색은 query의 정규화 토큰·설비 별칭·문서 텍스트와 승인 메타데이터로 수행한다. SOP의 사업장·승인·설비 적용 범위를 먼저 제한한 뒤 실제 제목과 chunk 본문으로 점수를 계산한다. 조회한 설비 코드나 별칭을 후보 문서 텍스트에 덧붙여 일치를 만들지 않는다. 실제 제목·본문에 코드나 별칭이 있는 경우의 일치와 기존 토큰 OR 검색은 유지한다. 최대 chunk 5개, chunk당 최대 2,000자를 반환한다. 동점 정렬을 문서 ID와 chunk 순서로 고정하고 조회 시각·검색 모드·query를 남긴다. 시나리오 이름으로 정답 문서를 선택하지 않는다.

## 5. 최종 DTO

| 필드 | 타입·제약 |
|---|---|
| `facts` | `{text, kind, source_refs: UUID[]}[]`; kind는 `HUMAN_STATEMENT | RECORD | SYSTEM_STATE` |
| `hypotheses` | 확정하지 않은 가능성 `string[]` |
| `missing_information` | 부족한 정보 `string[]` |
| `decision` | `ASK_USER | PROPOSE_ACTION | WAIT_EXISTING | REQUEST_VERIFICATION | BLOCKED` |
| `questions` | `{question, purpose_code, target_user_id, source_refs: UUID[]}[]`; 최대 2개 |
| `selected_draft_id` | UUID 또는 null |
| `existing_request_ids` | 실제 같은 사건의 유효 Request UUID 배열 |
| `existing_action_ids` | 실제 같은 사건의 Action UUID 배열 |
| `source_refs` | 전체 판단에 사용한 근거 UUID 배열 |
| `reason` | 사용자에게 표시할 짧은 판단 이유 |

question의 purpose_code는 서버 허용 목록 `VERIFY_SCOPE | VERIFY_RESULT`를 쓴다. 답변 target은 현재 서버 배정표의 지정 정비 담당자에서 선택한다. 빈 배열은 `[]`, 선택하지 않은 draft는 `null`이다. 문자열의 길이와 배열 상한도 애플리케이션에서 검사한다.

| decision | 필요한 조건 | 실제 반영·금지 |
|---|---|---|
| ASK_USER | 질문 1~2개, 적법한 대상·출처; draft=null | 중복 키가 같은 OPEN Request는 재사용하고 그 외 질문을 저장. 저장된 유효 OPEN Request가 있어야 WAITING_INPUT |
| PROPOSE_ACTION | 질문=[]; 선택 draft가 이번 run·Incident·input_version에 속함 | F2 서비스를 통해 PROPOSED Action 최대 1개. 기존 generation1이 있으면 새 generation 발급 금지 |
| WAIT_EXISTING | 질문=[]; draft=null; 검증된 기존 Request/Action ID 최소 1개 | 실제 ID만 연결. 원문이 추가되지 않는 동일 맥락 재조사는 버전 증가 없음. waiting_for_input은 DB로 계속 계산 |
| REQUEST_VERIFICATION | 질문=[]; draft=null; D06의 준비 조건 통과 | 현재 버전 기준 PENDING_VERIFICATION까지. 사람의 최종 해결 검증을 대신하지 않음 |
| BLOCKED | 질문=[]; draft=null; 구체적 사유 | analysis만 저장. ERROR를 확인했으면 실패 출처를 설명하고 정상·해결로 해석하지 않음 |

어느 분기든 알려지지 않은 ID·다른 사건 ID·보지 않은 근거를 포함하면 검증 실패다. 선택되지 않은 후보나 다른 분기의 질문을 묵시적으로 반영하지 않는다. `REQUEST_VERIFICATION`의 준비 조건에 이미 PENDING_VERIFICATION이어야 한다는 순환 조건을 넣지 않는다. Action 완료 서비스도 같은 준비 조건을 호출하므로 정상 완료 뒤 추가 모델 호출은 필수가 아니다.

`review_required=true`인 반려 사건은 Phase 1에서 신규 질문·Action 생성, 자동 준비 전환, 해결을 차단한다. 새 원문은 기록할 수 있고 조사 Job은 `BLOCKED` analysis만 갱신한다. 기존 완료 Action이나 모델 판단으로 플래그를 해제하지 않는다. 상세 의미는 [D02·D06](11_DECISIONS_AND_SOURCES.md)을 따른다.

## 6. Responses API 연결

- 함수 도구에 `strict:true`, `parallel_tool_calls:false`를 사용한다. 최종 결과는 `text.format`의 `json_schema`로 받는다.
- 모델 output의 필요한 항목을 같은 run의 후속 입력에 보존한다. 각 function call의 정확한 `call_id`에 대응하는 `function_call_output`을 추가한다. 텍스트만 복사하거나 필요한 output 항목을 누락하지 않는다.
- 정상 구조화 응답, `incomplete`, 명시적 refusal, schema 파싱 오류, API 오류를 분리한다. 유효한 최종 DTO가 없으면 업무 상태를 바꾸지 않는다.
- 명시적 거절은 강제 재질문으로 우회하지 않는다. 형식 보정·일시 오류 재시도도 동일 호출 수와 deadline 안에서만 허용한다.
- `store:false`를 지정한다. 이는 모든 보관 정책이 사라진다는 의미가 아니다. 키는 서버/worker에서만 읽는다.
- `OPENAI_AGENT_MODEL`은 실제 계정의 함수 호출·구조화 출력·한국어·지연 검증 후 채운다. 이 문서는 특정 모델 또는 SDK 조합의 실행 성공을 보장하지 않는다.

공식 근거는 [Function calling](https://developers.openai.com/api/docs/guides/function-calling), [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [Conversation state](https://developers.openai.com/api/docs/guides/conversation-state), [자료 목록](11_DECISIONS_AND_SOURCES.md)을 따른다. 현재 문서 작성에서는 외부 API를 호출하지 않았다.

## 7. 실행 상한·실패·복구

| 설정 | 초기값 | 의미 |
|---|---:|---|
| AGENT_RUN_DEADLINE_SECONDS | 60 | claim 이후 이번 run의 실행 시간 상한 |
| AGENT_MAX_MODEL_CALLS | 7 | 실패·재시도·형식 보정 포함 호출 상한 |
| AGENT_MAX_TOOL_CALLS | 6 | 실제 실행한 읽기·후보 도구 합계 |
| AGENT_MAX_INPUT_BYTES | 262144 | 초기·후속 호출 전체 직렬화 입력과 출력 여유의 바이트 예산. 허용 범위 32768~1048576 |
| AGENT_MAX_OUTPUT_TOKENS | 2000 | 개별 모델 응답 출력 상한 |
| SEARCH_MAX_CHUNKS / SEARCH_MAX_CHUNK_CHARS | 5 / 2000 | 개별 검색 결과 상한 |
| WORKER_POLL_INTERVAL_SECONDS | 2 | DB Job 확인 간격 |
| JOB_LEASE_SECONDS / JOB_MAX_ATTEMPTS | 90 / 3 | 점유 유효기간 / 동일 Job 전체 claim 상한 |

호출 전 남은 시간·횟수를 검사하고 개별 timeout은 남은 deadline 이내로 둔다. 이미 유효한 최종 결과가 있다면 검증 후 확정할 수 있지만, 상한 때문에 정상 결과를 얻지 못하면 `FAILED/BUDGET_EXCEEDED` 또는 `FAILED/TIMEOUT`으로 종료한다. BLOCKED는 검증된 모델 판단이고 상한 초과 실패를 숨기는 상태가 아니다. 늦은 응답은 폐기한다.

| 상황 | Job | AgentRun | 업무 효과 |
|---|---|---|---|
| ASK_USER의 질문 저장/유효 질문 재사용 | SUCCEEDED | WAITING_INPUT | 실제 OPEN Request에 연결 |
| WAIT_EXISTING의 기존 질문·작업 유지 | SUCCEEDED | SUCCEEDED | 실제 ID 유지, waiting_for_input은 DB의 OPEN 필수 Request로 계산 |
| Action 확정·준비 전환 | SUCCEEDED | SUCCEEDED | 서버가 검증한 변경만 반영 |
| 도구 ERROR 후 정상 BLOCKED 판단 | SUCCEEDED | SUCCEEDED | analysis·보류 사유만 저장 |
| 모델/API/파싱/실행 한도 실패 | FAILED | FAILED | 원문·승인·작업 보존 |
| 입력 버전 변경 | SUPERSEDED | SUPERSEDED | 오래된 초안 업무 반영 없음 |

재시도는 같은 Job ID·trigger·dedupe_key를 유지하되 새로운 attempt와 새 AgentRun을 만든다. 과거 run은 수정하지 않는다. 사람 답변은 재시도가 아니라 새 trigger다. `WAITING_INPUT`을 재시도 큐에 넣지 않는다.

최종 업무 반영뿐 아니라 Job의 성공·실패·SUPERSEDED 종료 갱신에도 `RUNNING + attempt 일치 + lease_token 일치 + lease 미만료`를 요구한다. 이전 worker의 늦은 오류가 새 worker의 성공을 덮어쓸 수 없다. lease 상실 시 이전 실행 결과는 적용하지 않고 기존 실행 기록을 보존한다. 복구 담당 worker가 만료 attempt를 종료 기록하고 새 attempt를 생성한다. Incident → Action/Request → Handover item → Job 순서와 각 집합의 ID 정렬을 지킨다.

마지막 attempt 도중 worker가 사라진 경우에는 새 claim 없이 종료하는 시스템 복구 예외가 필요하다. 복구기는 Job 행 잠금 안에서 `RUNNING + lease 만료 + attempt >= JOB_MAX_ATTEMPTS`를 다시 확인하고 Job과 현재 미종료 Run을 `FAILED / ATTEMPTS_EXHAUSTED`로 종료한다. 기존 lease_token은 폐기하며 업무 상태·analysis를 적용하지 않고 새 attempt·모델 호출도 만들지 않는다. 이 경로는 만료 worker에게 종료 권한을 되돌리는 것이 아니다. 오래된 worker의 늦은 성공/실패는 계속 차단한다.

SUPERSEDED 이후 아직 조사할 일이 있고 최신 업무를 처리할 Job이 없을 때만 중복 없이 큐에 넣는다. 해결됐거나 `review_required`로 막힌 사건에 재조사 루프를 만들지 않는다. 한 업무 효과는 한 번이지만 worker 중단 뒤 재호출로 API 비용이 다시 발생할 수 있다. 이를 exactly-once API 호출이라고 표현하지 않는다.

## 8. 실행 근거와 완료 조건

run마다 `run_id, job_id, attempt, trigger_event_id, input_version, mode, model_id, prompt_version, tool_schema_version`, 실제 tool 인자·결과·반환 source ID, draft/Request/Action ID, 최종 DTO, 검증 거부, 오류·시간·API usage를 연결한다. 비공개 추론과 인증 정보는 기록하지 않는다. usage가 없으면 0 대신 미수집으로 표시한다.

`fake`는 자동 테스트, `live`는 실제 OpenAI, `replay`는 저장된 실행 재생이다. replay는 원본 run·원본 commit·녹화 시각을 표시하고 새 모델 실행으로 집계하지 않는다. live 실패 뒤 fake 성공으로 자동 전환하지 않는다. 모델 설명 오류, 서버가 거부한 시도, 실제 잘못 커밋된 상태를 별도로 기록한다.

F1 완료는 [L1a·L1b·L2·L3 및 T3·T7·T9·T10·T11](07_TEST_PLAN.md)의 실제 증거로 확인한다. 지금은 모두 NOT_RUN이다. D01~D07의 버전·반려·lease·인계·멱등성·해결·증거 규칙을 [결정 기록](11_DECISIONS_AND_SOURCES.md)과 함께 구현한다.
