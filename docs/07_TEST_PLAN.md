# 07. 테스트·평가 계획

> v0.3 구현 문서 · 2026-10-09. 아래 모든 시험은 **NOT_RUN**이다. 앱·DB·테스트 runner가 구현된 뒤 실제 결과와 근거를 기록한다. 문서 생성이나 schema 예시 검토를 기능 PASS로 기록하지 않는다.

## 1. 검증 층과 기능 책임

| 층 | 실행 수단 | 입증 범위 | 담당 기능 |
|---|---|---|---|
| 서비스/DB | 실제 PostgreSQL + 결정론적 서비스 호출 | 권한·상태·version·receipt·트랜잭션·고유키 | F0 공통 및 F1~F4 각 기능 |
| 도구/DTO | schema 검증 + 격리 fixture | 입력·출처·범위·최종 분기 검사 | F1, F2 생성 서비스 경계 |
| Worker fake | 통제된 모델 응답·오류·가상 시각 | budget·lease·재시작·stale 결과 차단 | F0/F1 |
| Live Agent | 실제 OpenAI 호출 + 합성 자료 | 조회·질문·기존 업무 유지·ERROR 해석 | F1; F2 최종 확정 연결 |
| UI E2E | 네 서버 세션 + 브라우저 + 저장 DB | 같은 사건의 실제 버튼·오류·전주기 연결 | F1~F4, F5 공동 |
| 제출 확인 | 실제 앱 SHA·실행/녹화·링크 재확인 | 주장과 증거·제출물 일치 | F5 공동 |

F1은 접수부터 질문/답변/Agent, F2는 Action·승인·착수·결과, F3는 인계/ACK, F4는 최종 검증/해결을 화면·API·DB·테스트까지 소유한다. F0는 공통 계약을 통합하고 F5는 각 기능의 증거를 묶는다. 상세 AC는 [02_FUNCTIONAL_SPEC.md](02_FUNCTIONAL_SPEC.md), 상태/권한은 [03_DOMAIN_MODEL.md](03_DOMAIN_MODEL.md), HTTP 계약은 [04_API_CONTRACT.md](04_API_CONTRACT.md)를 따른다.

fake PASS는 모델 판단 품질이 아니다. live 모델 판단이 적절해도 DB 경합 안전성이 입증되지 않는다. replay는 원래 실행의 재생이며 새로운 live run 수에 합산하지 않는다.

## 2. 공통 실행 전제와 판정

1. 격리 PostgreSQL에 [fixture v0.3](10_FIXTURES.md)를 적재하고 app commit·dirty 상태·dataset 버전·환경 fingerprint를 기록한다. `.env` 내용·키는 증거에서 제외한다.
2. 각 시험의 초기 Incident/Action/Request 상태, 버전, event 수, Job 수, receipt 수를 기록한다. 변형을 main 데모에 덮어쓰지 않는다.
3. HTTP 응답만 보지 말고 DB의 실제 효과와 이벤트·원문·근거를 함께 검증한다. 예상 거부의 경우 업무 변화 0개와 보존돼야 할 입력을 구분한다.
4. 경합 시험은 barrier와 통제 가능한 시각으로 실행 순서를 고정한다. sleep 우연에 의존하지 않는다. 잠금·부분 unique·트랜잭션 시험을 SQLite 결과로 대신하지 않는다.
5. 기대 결과와 실제 결과가 모두 있어야 PASS다. 런타임 미구현은 NOT_RUN, 실행 전제에 막힘은 BLOCKED, 실행 후 기대 불일치·오류는 FAIL이다. 오류·중단 이유는 별도 필드에 남긴다.

결과 양식은 [templates/TEST_RESULTS.md](../templates/TEST_RESULTS.md)를 복사한다. 시험마다 실행 시각, 전체 commit SHA, mode, 실제 run/command ID, 기대/실제, 증거 경로가 필요하다. 아래 상태는 실행할 때 결과 사본에서 갱신한다.

## 3. 서버·경합 시험 T1~T12

### T1. 권한과 승인 — F0/F2/F4 · D05/D06

| 하위 ID | Given → When | Then | 상태 |
|---|---|---|---|
| T1a | PROPOSED Action → 지정 담당자가 착수 | 상태 오류 409, Action·Incident·이벤트 변경 없음 | NOT_RUN |
| T1b | 유효 Action → 작업자/정비 담당자가 승인 | 403, 승인 기록 없음 | NOT_RUN |
| T1c | PENDING_VERIFICATION → 작업자 또는 이전 owner가 검증 | 403, RESOLVED/case 생성 없음 | NOT_RUN |
| T1d | 다른 사업장/역할/actor를 body로 조작 | 세션 권한 적용, 허용되지 않은 필드는 422 또는 범위 요청 거부; 정보 노출 없음 | NOT_RUN |
| T1e | APPROVED payload → 범위·assignee·기한·기준 수정 시도 | Phase 1 수정 경로 없음; 승인 payload/hash 유지 | NOT_RUN |
| T1f | Request 지정 대상 외 사용자가 reply | 403, 답변/ANSWERED/후속 Job 없음 | NOT_RUN |
| T1g | Action 명령에서 오래된 Action version 또는 부모 Incident version 각각 전달 | 어느 하나만 오래돼도 409, 승인·착수·완료 효과 없음 | NOT_RUN |
| T1h | 다른 assignee가 착수/결과 제출 또는 PROPOSED에서 바로 완료 | 403 또는 상태 409, 결과·완료 기록 없음 | NOT_RUN |

### T2. 멱등성·업무 고유키 — F0/F1/F2/F3/F4 · D05

| 하위 ID | Given → When | Then | 상태 |
|---|---|---|---|
| T2a | 접수/답변/착수/완료 성공 후 응답 유실 → 동일 actor·키·payload 재전송 | 최초 응답 재사용, 원문·Action·이벤트·Job·버전 증가 중복 없음 | NOT_RUN |
| T2b | 승인/ACK/RESOLVE 성공 후 상태 변경 → 동일 요청 재전송 | 최신 상태 검사보다 완료 receipt 재사용; 이전 성공을 409로 바꾸지 않음 | NOT_RUN |
| T2c | 같은 actor·키, route 또는 body가 다름 | 409 멱등 충돌, 새 업무 효과 없음 | NOT_RUN |
| T2d | 같은 key를 다른 actor/site에서 사용 | 정해진 scope로 독립 처리, 타인의 응답 재사용/유출 없음 | NOT_RUN |
| T2e | 같은 trigger Job 등록 경쟁, 같은 slot/generation Action 확정 경쟁 | 각 고유키 단일 행; 생성 또는 기존 ID로 수렴 | NOT_RUN |
| T2f | 동일 목적·대상의 OPEN 질문 이미 존재 | 기존 Request ID 유지, 중복 OPEN 0개 | NOT_RUN |

### T3. AI 결과 최신성 — F0/F1/F2/F3 · D01/D03

모델 실행을 input_version=N에서 일시 정지한다. T3a는 지정 답변, T3b는 정상 ACK를 먼저 커밋한 뒤 모델 결과를 확정한다. 두 경우 모두 기존 결과는 SUPERSEDED이고 그 초안의 Request/정식 Action/analysis가 최신 상태를 덮어쓰지 않아야 한다. 새 업무 버전용 Job이 이미 있다면 하나를 유지하고, 필요한 Job이 없을 때만 하나를 등록한다. 해결/반려 차단 사건에는 재조사 루프를 만들지 않는다. **T3a/T3b: NOT_RUN.**

### T4. 인계와 ACK — F3 · D04/D05

| 하위 ID | Given → When | Then | 상태 |
|---|---|---|---|
| T4a | snapshot 뒤 새 원문/결과 → 이전 revision/token/version ACK | 409 stale, owner 이전 없음, 이전 snapshot 보존 | NOT_RUN |
| T4b | 유효 최신 snapshot → 지정 수신 책임자 ACK | owner만 수신자로 이전, assignee 유지, ACK와 버전 증가 원자적 | NOT_RUN |
| T4c | snapshot_version=N → 정상 ACK로 N+1 | ack_applied_version=N+1; 자신의 ACK 때문에 즉시 미인수 표시하지 않음 | NOT_RUN |
| T4d | ACK 후 새 내용 N+2 → 다시 조회/재ACK | 새 immutable revision 필요, 같은 수신자의 재확인; 이전 owner로 복귀 없음 | NOT_RUN |
| T4e | 미응답 필수 Request·진행 중 작업 포함 사건 | 인계 목록·snapshot에 대기와 남은 작업 모두 포함; ACK가 해결로 바뀌지 않음 | NOT_RUN |
| T4f | 유효 snapshot을 다른 사용자 또는 위조 token으로 ACK | 권한/내용 검증 거부, owner·ACK 기록 변경 없음 | NOT_RUN |

### T5. 해결 준비·근거 — F1/F2/F4 · D06

별도 초기 상태에서 하나씩 빠뜨린다. **T5a** 주 Action 0개, **T5b** PROPOSED/APPROVED/IN_PROGRESS 필수 Action, **T5c** 유효 승인 없음, **T5d** OPEN 필수 Request, **T5e** 결과 원문·작성자·시각 없음, **T5f** 다른 사건/존재하지 않는/허용되지 않은 evidence, **T5g** 비어 있는 사람 검토 사유, **T5h** review_required=true. 각 경우 준비 전환 또는 최종 해결을 해당 gate에서 거부하고 RESOLVED·case를 만들지 않는다. 빈 Action 집합의 `all([])`가 통과하면 실패다. **T5a~T5h: NOT_RUN.**

**T5i:** 모든 준비 조건을 갖춘 IN_PROGRESS 사건은 완료 또는 검증된 REQUEST_VERIFICATION 처리로 PENDING_VERIFICATION에 들어갈 수 있다. 준비 조건이 현재 PENDING_VERIFICATION을 먼저 요구해서 막히면 실패다. 최종 RESOLVE에는 그 상태가 필수다. **NOT_RUN.**

### T6. 최종 검증과 동시 변경 — F0/F1/F2/F3/F4 · D01/D05/D06

| 하위 ID | 강제 실행 순서 | Then | 상태 |
|---|---|---|---|
| T6a | 새 원문이 먼저 커밋 → 이전 버전 RESOLVE | 원문 저장·버전 증가·INVESTIGATING, 이전 검증 409 | NOT_RUN |
| T6b | RESOLVE 먼저 커밋 → 늦은 원문 | 409와 새 제보 안내; 입력은 rejected_input 기록에 보존, 해결 snapshot 불변 | NOT_RUN |
| T6c | 완료/ACK 먼저 커밋 → 이전 화면 RESOLVE | 이전 expected_version 거부, 최신 owner·상태로 재조회 | NOT_RUN |
| T6d | RESOLVE 먼저 커밋 → 늦은 완료/ACK | 상태 오류, 인가된 입력은 rejected_input으로 보존, 해결 snapshot·책임 변경 없음; 같은 완료 receipt는 T2b대로 재사용 | NOT_RUN |
| T6e | 두 경합 경로를 양방향 barrier로 실행 | 정의된 잠금 순서, 부분 커밋 없음; 교착 오류를 성공으로 기록하지 않음 | NOT_RUN |

### T7. 실패·예산·재시작 — F0/F1 · D03/D07

| 하위 ID | 주입 조건 | Then | 상태 |
|---|---|---|---|
| T7a | 모델 API 오류/timeout/refusal/incomplete/파싱 오류 각각 | 유효 DTO 없으면 FAILED, 원문·승인·작업 보존, UI 재시도 안내 | NOT_RUN |
| T7b | 조회 ERROR + fake 유효 BLOCKED DTO | ERROR가 모델 입력에 전달됨; Job/Run SUCCEEDED, 보류 analysis만 저장 | NOT_RUN |
| T7c | 7회 모델/6회 도구/60초 상한 각각 도달 | 추가 실행 금지, 유효 결과 없으면 명확한 실패 코드; 상한 뒤 늦은 결과 적용 없음 | NOT_RUN |
| T7d | claim 후 worker 종료·lease 만료 | 같은 Job을 새 attempt/Run으로 회수, 과거 run 보존, 업무 효과 최대 1번 | NOT_RUN |
| T7e | WAITING_INPUT에서 worker/API 재시작 → 지정자 답변 | 질문 대기는 재시도하지 않음, 답변은 새 Job/Run, 실제 DB에서 재개 | NOT_RUN |
| T7f | 모델이 중단/실패한 사건의 인계 조회 | DB 미해결 목록·기본 snapshot은 계속 구성 가능 | NOT_RUN |
| T7g | 마지막 attempt 실행 중 worker 종료 → lease 만료 | 시스템 복구기가 Job 잠금·RUNNING/만료/attempt 상한을 재검사하여 Job·현재 미종료 Run을 FAILED/ATTEMPTS_EXHAUSTED로 종료, 토큰 폐기; 추가 claim·모델·업무 반영 없음, 원문 보존 | NOT_RUN |

### T8. 같은 Incident 전주기 — F1/F2/F3/F4/F5 · D07

[fixture 진행문](10_FIXTURES.md)의 제보 → 실제 조회·질문 → 지정자 답변 → Action 1개 → 출발 책임자 승인 → 담당자 착수 → 미해결 인계/ACK → 담당자 결과 → 수신 책임자 최종 검증을 수행한다. 같은 Incident ID와 Action ID를 추적한다. 승인된 payload, ACK 전후 owner, 유지된 assignee, completion_report, 최신 검토자, RESOLVED와 단일 case·이벤트가 DB/UI에 일치해야 한다. 재시작 뒤에도 재조회된다. 이는 합성 시나리오의 업무 추적 시험이며 현장 안전 검증이 아니다. **T8: NOT_RUN.**

### T9. 상태가 같은 추가 원문의 버전 — F0/F1/F3 · D01

Given: IN_PROGRESS/version=N 사건을 Agent가 조사하고 snapshot도 N을 참조한다. When: 단순 보충 message를 저장하되 상태명은 그대로다. Then: Incident.version=N+1, message·event·필요 Job은 한 트랜잭션, 이전 Agent 결과와 ACK는 거부한다. 동일 요청 receipt 재전송은 N+2를 만들지 않는다. analysis·draft·검색만 저장하면 버전을 올리지 않는다. 검증 대기 중 원문이면 INVESTIGATING으로 바꾸지만 REJECT/RETURN이 없는데 review_required를 영구 설정하지 않는다. **T9a 메시지/T9b receipt/T9c 무업무 저장/T9d 검증 대기: NOT_RUN.**

### T10. 반려와 후속 검토 — F1/F2/F4 · D02/D06

| 하위 ID | Given → When | Then | 상태 |
|---|---|---|---|
| T10a | PROPOSED Action → 승인 REJECT | Action REJECTED, Incident INVESTIGATING, review_required와 반려 사유/event 저장 | NOT_RUN |
| T10b | PENDING_VERIFICATION → 검증 RETURN | Action COMPLETED 보존, Incident INVESTIGATING, review_required와 검토 사유/event 저장 | NOT_RUN |
| T10c | 위 상태 → 모델 PROPOSE_ACTION/REQUEST_VERIFICATION | 신규 정식 작업·generation2·재준비·해결 차단; 필요 시 BLOCKED analysis만 | NOT_RUN |
| T10d | 위 상태 → 읽기/새 원문/인계 | 기록과 미해결 인계 가능; 플래그는 유지, 성공 해결로 표시하지 않음 | NOT_RUN |

Phase 1에는 review_required 해제 명령이 없다. 사람의 후속 조치를 설계하지 않고 자동 해제했다면 실패다.

### T11. 오래된 worker의 늦은 종료 — F0/F1 · D03

worker A가 attempt=1/token=A로 실행한다. lease를 만료시키고 worker B가 attempt=2/token=B를 claim하여 성공한다. 그 뒤 A의 **성공 finalizer, 실패 handler, SUPERSEDED handler, analysis 저장**을 각각 실행한다. 네 경로 모두 현재 Job 상태/attempt/token/만료 검사를 통과하지 못해야 한다. B의 Job SUCCEEDED·analysis·업무 ID를 덮어쓰지 않고 부작용도 추가하지 않는다. 과거 run 기록을 현재 run으로 바꾸지 않는다. 외부 API 재호출 횟수는 실제대로 남긴다. **T11a~T11d: NOT_RUN.**

### T12. 인계 생성 범위·중복 — F0/F3 · D04

| 하위 ID | Given → When | Then | 상태 |
|---|---|---|---|
| T12a | 출발 교대 책임자 → 허용된 인접 교대 쌍 생성 2회 | 고유키로 같은 Handover, 사건 중복 없음 | NOT_RUN |
| T12b | 잘못된 사업장/교대 순서/비인접 교대/무권한 생성자 | 각각 거부, 인계 생성 없음 | NOT_RUN |
| T12c | 새 미해결 사건이 cutoff 이후 접수 | “추가됨” 표시, 다음 snapshot 포함; 보지 않은 내용을 ACK한 것으로 처리하지 않음 | NOT_RUN |
| T12d | 일부 항목 ACK 후 owner 이전 → 같은 인계 재구성 | 이미 전달한 항목 유지, 새 버전만 새 revision; 타 교대 사건 끌어오지 않음 | NOT_RUN |
| T12e | snapshot 후 사건 해결 → 늦은 최초 ACK | 거부·해결 snapshot 보존; 이미 완료한 동일 ACK receipt는 최초 응답 재사용 | NOT_RUN |
| T12f | 질문/승인/작업/최종 검증 대기 사건을 혼합 | 서버 범위 내 미해결 집합과 항목 집합 일치, 누락·잘못된 추가 각각 0개 | NOT_RUN |

## 4. 도구·schema 부정 시험

F1/F2 통합에서 다음을 별도 table-driven 테스트로 작성한다. 전체 **NOT_RUN**이다.

- 추가 필드, required 필드 생략, null 불허 위치, 잘못된 enum, 과도한 배열/길이를 거부한다.
- ASK_USER인데 질문 0개, PROPOSE_ACTION인데 다른 run/version의 draft, WAIT_EXISTING인데 ID 0개, 다른 분기에 신규 질문/draft 포함을 거부한다.
- 존재하지 않거나 이번 run에서 보지 않은 source_ref, 다른 사건의 Request/Action, 잘못된 답변 target을 거부한다.
- 승인되지 않은 SOP·다른 사업장 자료 제외, CV-02 case가 CV-03 현재 사실로 둔갑하지 않는지 확인한다.
- 자료 속 지시가 허용 도구 집합·권한·최종 상태를 바꾸지 못하는지 확인한다.
- ERROR와 EMPTY가 구분되고 실제 `call_id`의 도구 결과가 다음 모델 요청에 연결되는지 확인한다.
- `propose_action`만 호출하고 유효 최종 DTO가 없으면 정식 Action/승인/버전 변경이 없는지 확인한다.

## 5. 실제 OpenAI 최소 실행

최소 조건은 **3개 대표 시나리오, 4개 실제 업무 run**이다. L1a와 L1b는 같은 사건의 다른 run이다. model call 수와 run 수를 분리한다. 실패도 실제 시도 수에 포함하며 뒤의 성공으로 삭제하지 않는다.

| ID·기능 | 입력/절차 | PASS 기준 | 상태 |
|---|---|---|---|
| L1a F1 | 모호한 초기 점검 기록 + 새 제보 | 실제 도구 조회와 근거 → 지정자에게 범위 질문이 DB 저장; 해결 확정 설명 없음 | NOT_RUN |
| L1b F1/F2 | L1a Request에 지정 정비 담당자가 답변 | 답변을 입력으로 새 live run; 유효 draft 선택 → F2 서비스가 정식 Action 1개 확정 | NOT_RUN |
| L2 F1/F2 | 활성 주 Action이 있는 같은 사건 재조사 | WAIT_EXISTING으로 실제 기존 ID 유지, 신규 Action 0개 | NOT_RUN |
| L3 F1 | 조회 도구 ERROR 주입 + 실제 모델 호출 | ERROR를 받은 다음 모델 응답이 BLOCKED; 원문 보존. 모델 자체 실패면 별도 FAIL | NOT_RUN |

모든 live 기록에 실제 model ID·SDK 버전·prompt/schema 버전·도구와 source ID·결정·DB 효과·API usage·시간을 연결한다. 정확한 문장 일치보다 질문 목적·근거·도메인 결과로 판정한다. 대본을 모델에게 알려주지 않는다. live를 실행하기 전 키/모델 권한과 구조화 출력 지원을 실제 계정으로 확인한다.

선택 L4(Phase 2): 충분한 최초 범위·결과 입력에서는 불필요한 반복 질문을 생략하는 대조. 최소 요건 이후 새 기능을 추가하기 전에 권장한다. 표현 변형 holdout·3회 반복·별도 무응답 교대 live는 Phase 2다. **L4와 Phase 2 평가: NOT_RUN.**

## 6. D01~D07 추적과 기능 완료 gate

| 결정 | 핵심 위험 | 시험 |
|---|---|---|
| D01 | 상태가 같다는 이유로 새 정보를 버전에서 누락 | T3, T6, T9 |
| D02 | 반려 후 기존 완료 조건으로 자동 해결 재진입 | T10, T5h |
| D03 | lease를 잃은 worker의 업무/종료 덮어쓰기 | T7c~g, T11 |
| D04 | 인계 범위 누락·오인수·중복·자체 ACK 무효화 | T4, T12 |
| D05 | 권한·멱등성·부모/Action 버전·잠금 경합 | T1, T2, T6 |
| D06 | 빈 작업/누락 근거/오래된 검토로 해결 | T5, T6, T8 |
| D07 | fake·계획·재생을 live 성과로 혼합 | L1a~L3, T8, 결과 양식·제출 검토 |

| 기능 | 최소 완료 gate | 현재 |
|---|---|---|
| F0 공통 기반 | T1 권한·T2 receipt·T6 잠금·T7/T11 worker 경계와 계약 문서 일치 | NOT_RUN |
| F1 접수·조사 | 도구 부정 시험, T3/T7/T9/T10, L1a/L1b/L2/L3 | NOT_RUN |
| F2 작업 | T1/T2/T5/T10, L1b 통합, T8의 승인·착수·결과 | NOT_RUN |
| F3 교대 인계 | T4/T12, T6 ACK 경합, T8의 미해결 ACK | NOT_RUN |
| F4 해결 | T1c/T2b/T5/T6/T10, T8의 단일 case | NOT_RUN |
| F5 전주기·제출 | T8 live E2E, 실제 결과·남은 실패 공개, 제출 앱과 증거 SHA 확인 | NOT_RUN |

세부 AC 연결:

| 수용 기준 | 시험·증거 |
|---|---|
| AC-F0.1 / F0.2 / F0.3 | T1 / T2 / 실제 Compose 부팅·DB 연결·네 세션 `/me`와 UI enum 검토(별도 환경 기록, NOT_RUN) |
| AC-F1.1~1.3 | T7 / T2 / T3·T9 |
| AC-F1.4~1.6 | L1a / L3 / T3·T11 |
| AC-F1.7~1.9 | L1a·L1b / T1f·T2a / T7e |
| AC-F1.10~1.11 | L2 / T10 |
| AC-F2.1~2.4 | L1b / T2e·T3 / T1b·T1e·T1g / T10a |
| AC-F2.5~2.8 | T1a·T1h / T2a / T1h·T5 / T8 |
| AC-F3.1~3.4 | T12f / T4b·T4c·T8 / T4a·T4f·T12 / T4d·T6 |
| AC-F4.1~4.5 | T5 / T1c·T6·T9 / T10b·T10c / T8 / T6b·T6d |
| AC-F5.1~5.3 | 모든 필수 하위 시험 결과 / live·fake·replay 구분과 실제 run 모수 / 제출 runbook의 최종 접근·접수 근거 |

## 7. 실행 순서·회귀·증거 보관

F0 기반 → F1 접수와 F2 계약 시험 병렬 → live 질문/답변과 Action 통합 → F3/F4 검증 → 같은 Incident T8 → 제출 버전 고정 순으로 실행한다. fake F2 계약 시험만으로 live F1→F2 통합 완료라고 표시하지 않는다.

예정 테스트 경로는 `apps/api/tests/{services,agent,integration}/`와 `apps/web/tests/e2e/`다. 아직 실행 명령·runner가 없으므로 명령 성공을 기록하지 않는다. 구현 후 실제 명령을 결과표에 남긴다. 기본 단위/DB 시험이 통과하면 관련 경합과 live만 이어서 실행하고, 변경·실패·미해결 위험 없이 같은 시험을 반복하지 않는다.

모델·프롬프트·검색 자료·schema 변경은 영향받는 live 사례를 다시 확인한다. 권한·잠금·버전·receipt 변경은 관련 T 하위 시험을 재실행한다. 개선 전 실패 증거와 개선 commit, 개선 후 결과를 연결하고 미실행 항목은 그대로 남긴다.

예정 증거 위치는 `docs/evidence/<trial_id>/`다. 결과 Markdown에는 원문/DB snapshot/tool trace/녹화의 실제 경로를 연결한다. 인증 정보·비공개 추론·실제 개인정보는 넣지 않는다. 대화 원문 `docs/history/`는 Git 제외 기록이며 제출 테스트 증거와 구분한다. 공개 주장은 실행 표본과 합성 환경의 범위를 넘지 않는다.
