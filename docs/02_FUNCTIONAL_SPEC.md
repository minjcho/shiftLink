# 02. 상세 기능명세

> v0.3 구현 문서 · 2026-10-09. 구현 상태 `NOT_STARTED`, 실행 검증 `NOT_RUN`.
> ZIP v0.2의 기능명세 형식을 따르며 범위와 업무 계약은 v0.3 및 [D01~D07](11_DECISIONS_AND_SOURCES.md)을 적용한다. 아래 담당은 초기 배분 제안이다.

## 1. 공통 원칙과 완료 범위

Phase 1은 같은 Incident에서 **제보 → 실제 AI 조사 → 질문·답변 → 주 Action 하나의 제안·승인·착수 → 미해결 교대 인수 → 결과 → 사람 검증 → 해결 이력**을 연결한다. 제보·통합 상세·교대 인수의 세 화면을 사용한다. 모의 설비 자료와 실제 OpenAI 호출 여부를 구분한다.

업무 상태는 DB, 권한은 서버 세션, 인계 대상은 서버 조회가 결정한다. AI는 조회와 임시 후보를 만들며 승인·착수·결과 제출·해결 권한이 없다. 도구의 `ERROR`는 기록 없음 또는 정상으로 바꾸지 않는다. 업무 트랜잭션·업무 버전·멱등성·잠금 규칙은 [도메인](03_DOMAIN_MODEL.md)과 [API](04_API_CONTRACT.md)가 기준이다.

담당자는 자신의 기능에 필요한 **화면·API·데이터·권한·테스트 전체**를 맡는다. 공유 화면 셸과 DTO는 F0 통합 절차로 변경한다. 기능 완료는 구현 파일 생성만으로 판정하지 않으며 실제 API 연결과 해당 AC 증거가 필요하다.

## 2. 기능 목록과 책임

| 기능 | 담당 제안 | 기능명세 | Phase 1 산출물 |
|---|---|---|---|
| F0 공통 기반·계약 | 재곤 통합 / 민재 검토 | FR-01 | 세션·seed·공통 응답·트랜잭션 기반·부팅 경로 |
| F1 접수·AI 조사·질문과 답변 | 재곤 | FR-02~05 | 접수 화면부터 실제 질문·답변과 선택된 작업 후보까지 |
| F2 작업 제안 확정·승인·착수·결과 | 민재 | FR-06~08 | 정식 Action 확정 서비스와 역할별 작업 패널·API |
| F3 교대 인계·인수 | 재곤 | FR-09 | 범위가 검증된 인계 목록과 owner 이전 |
| F4 최종 검증·해결 이력 | 민재 | FR-10~11 | 종료 조건 검사·사람 검증·해결 snapshot |
| F5 전주기 검증·제출 | 공동 | FR-12 | 동일 사건 E2E·실제 run·시험·제출 근거 |

이 문서의 FR 번호는 v0.3에서 재구성했다. v0.2의 FR 번호와 같은 기능이라고 추정하지 않는다. 작업 추적에는 `F1 / FR-03 / AC-F1.4 / L1a`처럼 문서 내 번호와 테스트 ID를 함께 적는다.

## 3. FR-01 — F0 공통 기반·세션·실행 계약

**사용자:** 네 데모 계정(현장 작업자, 정비 담당자, 출발 책임자, 수신 책임자).

**입력·처리:** 서버 seed에 사업장 하나, 대표/비교 설비 두 대, 교대 발생 두 개, 사용자·설비·교대 매핑을 만든다. `/me`, `/equipment`, `/shifts`와 공통 API client를 연결한다. actor·role·site·초기 owner·assignee는 서버 데이터에서 결정한다. worker와 supervisor 권한에 담당 관계를 결합한다.

**화면·데이터:** 상단 세션 표시, 세 화면 셸, 공통 오류·근거 패널, Incident 상세 응답 경계를 제공한다. 이벤트·명령 영수증·Job·lease·공통 잠금은 기능마다 복사하지 않는 공통 기반이다. 환경값은 [ENVIRONMENT](ENVIRONMENT.md)를 따른다.

**예외:** 세션 없음 401, 권한 없음 403, 다른 사업장 자원은 일관된 404. 데모 계정 전환은 운영 인증이 아니며 비활성화 설정에서는 사용할 수 없다. 세션 전환 예외를 포함한 쓰기 인증·중복 계약은 API 문서에 고정한다.

**수용 기준:**

- **AC-F0.1:** 네 세션으로 `/me`를 읽어 역할·교대 매핑을 확인하고, 요청 본문의 actor/role로 승인 권한을 얻지 못한다.
- **AC-F0.2:** 같은 성공 명령 재전송은 최초 응답을 반환하고 업무 버전·이벤트가 추가되지 않는다. 같은 키의 다른 입력은 409다.
- **AC-F0.3:** UI·API가 동일 enum·필드·오류 계약을 쓰며 실제 부팅/DB 연결 결과를 기록한다. 작성한 Compose 파일 자체는 성공 근거가 아니다.

## 4. FR-02 — F1 제보·추가 원문 접수

**이야기:** 작업자는 AI 응답을 기다리지 않고 제보가 저장됐는지 확인한다.

**입력:** `equipment_id`, `text`, `Idempotency-Key`. 추가 메시지는 `text`, `expected_version`, `reply_to_request_id|null`을 사용한다. 상세 스키마·제한은 [API](04_API_CONTRACT.md)를 따른다.

**처리·출력:** 신규 접수는 Incident·최초 Message·이벤트·Job을 한 트랜잭션에 저장하고 202와 실제 ID를 반환한다. 별도 미연결 Report 단계나 자동 사건 병합은 없다. 추가 메시지는 기존 Incident에 저장한다. 같은 상태명이 유지돼도 새 메시지는 업무 버전을 한 번 증가시킨다(D01).

**화면·권한:** 제보/목록 화면과 상세 원문 패널을 함께 구현한다. 세션의 사업장·설비 접근을 검증한다. UI 입력은 네트워크 실패 후 남겨두며 같은 요청 재전송에 같은 키를 쓴다.

**예외:** 검증 대기 중 새 정보는 대기를 해제하고 재조사를 요청한다. 이미 해결됐다면 새 원문을 거부 입력 기록에 보존하고 409와 신규 제보 안내를 반환한다. 해결 snapshot은 수정하지 않는다.

**수용 기준:**

- **AC-F1.1:** AI를 사용하지 못해도 202 이후 원문과 사건을 재조회한다(T7).
- **AC-F1.2:** 접수/추가 메시지 재전송은 원문·Job·이벤트를 중복 생성하지 않는다(T2).
- **AC-F1.3:** 상태명이 같은 새 메시지라도 버전이 증가하고 진행 중 구버전 Agent 결과가 적용되지 않는다(T9, T3).

## 5. FR-03 — F1 실제 조사·근거·최종 판단

**입력:** 현재 Incident·Message·Request·Action·서버 근거 및 고정한 `input_version`.

**처리:** 별도 DB worker가 Job을 점유한다. 최초 `OPEN → INVESTIGATING` 트랜잭션 이후 버전을 고정한다. 실제 OpenAI가 `get_equipment_context`, `search_documents`, `search_similar_incidents`, `propose_action`을 선택한다. 마지막 도구는 run 내부 후보만 만든다. 키워드 검색은 실제 입력·자료·범위에 따라 결과가 바뀌며 fixture ID로 정답을 선택하지 않는다.

**최종 확정:** [Agent 계약](05_AGENT_DESIGN.md)의 DTO와 허용 근거·대상·후보를 검사한다. 원래 Incident 버전과 현재 Job attempt/lease가 유효한 경우에만 질문 또는 Action을 확정한다. F1 finalizer가 F2의 정식 Action 서비스를 호출하며 두 트랜잭션으로 나누지 않는다.

**화면:** 사실·사람 진술·가설·미확인 정보를 분리하고 인용 근거의 출처·버전·시각을 연다. `analysis.base_version`이 현재 업무 버전과 다르면 갱신 필요로 표시한다. 실행 진단은 실제 run·도구·오류·모드만 보여준다.

**예외:** 조회 `EMPTY`와 `ERROR`, 모델 실패·거절·incomplete를 구분한다. 오류 후 업무 성공을 만들지 않는다. 만료 lease의 worker가 늦게 끝나도 최신 Job/analysis를 덮어쓰지 못한다. `review_required=true`인 경우 analysis 참고 정보만 저장하고 업무 진행을 재개하지 않는다.

**수용 기준:**

- **AC-F1.4:** L1a에서 실제 도구 조회와 연결된 근거·Request ID를 확인한다.
- **AC-F1.5:** L3에서 실제 모델이 조회 ERROR를 받고 `BLOCKED`를 선택하며 원문이 유지된다. 모델 호출 실패는 이 통과로 계산하지 않는다.
- **AC-F1.6:** 새 정보 또는 만료 lease의 늦은 결과가 질문·Action·Job 최종 상태·analysis를 덮어쓰지 못한다(T3, T11).

## 6. FR-04 — F1 확인 질문·사람 답변·재실행

**처리:** `ASK_USER`의 질문을 최대 두 개까지 유효한 대상·목적·근거와 함께 저장한다. 같은 Incident·target·purpose의 OPEN Request는 재사용한다. 질문 대기는 영속 Request로 남기고 해당 run은 `WAITING_INPUT`, Job은 `SUCCEEDED`로 끝낸다. 모델 연결을 유지하지 않는다.

**답변:** 같은 사건의 OPEN Request 지정 대상자만 답한다. Message·Request ANSWERED·이벤트·새 Job·Incident 버전을 함께 저장한다. 새 run은 최신 DB를 읽는다. 작업자·정비 담당자는 자신의 질문만 답하며 owner라는 이유만으로 타인의 답변을 대신하지 않는다.

**화면:** 상세 질문 패널에 목적·대상·원문·답변 상태를 표시한다. 현재 사용자의 답변 입력과 일반 추가 메시지 입력을 구분한다. 미응답 질문은 인계에 포함된다.

**수용 기준:**

- **AC-F1.7:** 질문과 답변이 같은 Request ID로 연결되고 답변 뒤 새 run ID가 생긴다(L1a, L1b).
- **AC-F1.8:** 비대상자 답변은 거부하고 재전송은 답변/Job을 중복 저장하지 않는다(T1, T2).
- **AC-F1.9:** worker 재시작 이후에도 기존 질문에 답해 진행할 수 있다(T7).

## 7. FR-05 — F1 기존 업무 재사용·후속 검토 표시

기존 주 Action이 있는 재조사에서는 유효한 기존 ID를 `WAIT_EXISTING`으로 참조한다. 새로운 문장이나 임의 generation으로 추가 Action을 만들 수 없다. Phase 1의 generation은 1이다. `review_required=true`이면 일반 추가 기록과 인계는 허용하지만 신규 정식 Action·자동 검증 대기·해결은 금지한다.

**수용 기준:** **AC-F1.10:** L2에서 기존 Action ID와 개수가 유지된다. **AC-F1.11:** 반려 사건을 재조사해도 검토 차단이 해제되지 않는다(T10). 충분한 최초 입력의 질문 생략 대조 L4는 필수 네 live run 이후 권장 확장이다.

## 8. FR-06 — F2 정식 Action 확정·승인·반려

**입력:** F1이 검증한 선택 draft·run·Incident·input_version·trigger event. Agent에는 정식 Action 생성 권한을 별도로 주지 않는다.

**서비스·데이터:** F2는 `incident_id + action_slot + generation=1` 고유키 및 활성 주 Action 최대 하나 제약을 책임진다. 범위·서버 매핑 assignee·기한·완료 기준·근거가 있는 `PROPOSED` Action을 caller의 트랜잭션 안에서 생성하거나 검증된 기존 ID를 반환한다. 후보 확정 인터페이스는 [개발 계획](08_BUILD_PLAN.md)에 정의한다.

**승인:** 현재 owner인 supervisor만 `approval-decisions`를 제출한다. Action과 부모 Incident의 expected version을 모두 검사한다. 승인 대상 payload·해시·승인자·시각을 기록하고 승인 이후 내용·담당자·기한·완료 기준의 변경 API는 제공하지 않는다.

**반려:** `PROPOSED → REJECTED`, Incident `INVESTIGATING`, `review_required=true`와 사유를 한 번에 저장한다. Phase 1에서는 해제·재작업 버튼이 없다. 기존 기록 조회·추가 메시지·교대 인계는 유지한다.

**수용 기준:**

- **AC-F2.1:** L1b에서 후보가 정식 Action 하나로 확정되고 화면에 실제 ID·승인할 내용이 보인다.
- **AC-F2.2:** 동시/반복 finalizer에서 추가 주 Action이 생기지 않고 F1 질문/Action 반영과 원자성을 유지한다(T2, T3).
- **AC-F2.3:** 비owner 승인과 구버전 승인은 거부하고 승인 payload를 사후 변경하지 못한다(T1, T6).
- **AC-F2.4:** 반려 사유와 미해결 상태가 남으며 추가 Action·자동 검증 대기가 차단된다(T10).

## 9. FR-07 — F2 승인 작업 착수

**명령:** `/actions/{id}/start`. 승인된 `APPROVED` Action의 지정 assignee만 착수한다. Action·부모 Incident 버전을 모두 전달한다. `IN_PROGRESS` 상태와 시작자·시각·이벤트를 저장하고 Incident도 진행 중으로 전이한다. 승인 직후 Incident는 아직 `ACTION_REQUIRED`다.

**화면:** 같은 Action 패널에서 현재 세션이 담당자인 경우 착수 버튼을 제공한다. 미승인·다른 담당자는 상태와 이유만 볼 수 있다.

**수용 기준:** **AC-F2.5:** 승인 전 또는 다른 assignee의 착수가 거부된다(T1). **AC-F2.6:** 같은 착수 재전송은 최초 결과와 한 번의 버전 증가만 가진다(T2). PROPOSED에서 완료로 건너뛰는 경로는 없다.

## 10. FR-08 — F2 결과 제출·F4 검증 준비 연계

**입력:** 진행 중인 Action의 `result`, 선택적 기존 `evidence_refs`, Action과 Incident 버전, 중복 키.

**처리:** assignee가 제출한 결과 원문을 작성자·시각이 있는 `completion_report` 근거로 저장하고 Action을 `COMPLETED`로 변경한다. 결과 자체가 근거를 만들므로 추가 evidence 배열은 비어 있어도 된다. F4의 종료 준비 검사를 같은 트랜잭션에서 호출한다. 조건을 충족할 때만 Incident가 `PENDING_VERIFICATION`이 된다. 필수 질문이 남으면 완료된 Action과 미해결 상태를 유지한다.

**화면:** 결과 입력을 보존하며 제출 후 ‘작업 결과 제출 완료’와 사건 상태를 나란히 표시한다. 사람 진술의 저장을 실측 또는 독립된 안전 증명으로 표시하지 않는다.

**수용 기준:** **AC-F2.7:** 내용 없는 결과·타인 결과·다른 사건 근거는 거부한다(T1, T5). **AC-F2.8:** 완료로 Incident가 직접 RESOLVED가 되지 않으며 결과와 근거가 새로고침 후 남는다(T8).

## 11. FR-09 — F3 교대 인계 생성·항목별 인수

**생성:** 출발 교대의 지정 supervisor가 같은 사업장의 허용된 인접 교대 쌍을 선택한다. 교대 쌍 고유키로 중복 Handover를 방지한다. 해당 출발 교대 범위의 미해결 사건 전체를 서버가 수집한다. 재생성 시 같은 인계에서 이미 이전된 항목도 보존하고 무관한 사업장·교대는 포함하지 않는다.

**snapshot:** 원문·사건 버전·미응답 질문·남은 Action·owner·assignee·근거를 불변 revision에 저장하고 token에 묶는다. Phase 1의 기본 목록은 LLM을 기다리지 않는다. DB 조회 실패라면 완료 목록이라고 표시하거나 ACK를 허용하지 않는다.

**ACK:** 서버가 매핑한 수신 supervisor만 최신 revision·snapshot token·Incident version으로 항목별 확인한다. owner만 이전하고 assignee는 유지한다. snapshot version 7의 ACK가 Incident 8을 만들면 `ack_applied_version=8`을 기록하고 자신의 ACK 때문에 즉시 재인수를 요구하지 않는다. 이후 새 정보 9는 새 revision과 재확인이 필요하다. 재ACK는 현재 수신 owner의 재확인이며 출발 owner로 되돌리지 않는다.

**예외:** 오래된 ACK는 409 후 최신 내용 확인. 해결된 항목에 늦은 ACK는 입력을 보존하고 거부한다. 이미 성공한 동일 ACK 재전송은 영수증을 먼저 반환한다. cutoff 이후 새 사건은 ‘추가됨’으로 보이고 다음 revision에 포함된다.

**수용 기준:**

- **AC-F3.1:** 질문·승인·작업·검증 대기 모두 서버 대상 집합과 snapshot 집합이 일치한다(T12).
- **AC-F3.2:** 정상 ACK로 owner만 이전되고 Incident는 미해결이며 바로 재인수 상태가 되지 않는다(T4, T8).
- **AC-F3.3:** stale·다른 수신자·다른 교대·중복 생성·새 사건 추가를 명시적으로 검증한다(T4, T12).
- **AC-F3.4:** 새 업무 변경 뒤 재ACK가 최신 내용만 확인하고 작업 담당자·과거 revision을 바꾸지 않는다(T4, T6).

## 12. FR-10 — F4 종료 준비·사람 최종 검증

**준비 조건:** `review_required=false`, generation 1의 유효하게 승인된 필수 Action이 실제 존재하고 완료됨, 모든 필수 Request 답변됨, 같은 사건의 작성자·시각 있는 결과 근거, 참조 근거 범위 충족. 빈 Action 집합을 완료로 계산하지 않는다. 이 조건은 F2 완료 처리와 F1의 검증 요청에서 같은 서버 서비스를 사용한다.

**검증:** 현재 owner인 supervisor가 최신 `PENDING_VERIFICATION`의 내용을 보고 `RESOLVE|RETURN`, 필수 notes, 허용 근거와 expected version을 제출한다. 해결 직전에 종료 조건·권한·버전을 다시 검사한다. 추가 AI 호출은 종료의 필수 조건이 아니다.

**RETURN:** Incident를 `INVESTIGATING`으로 돌리고 `review_required=true`·사유를 기록한다. 기존 COMPLETED Action은 보존한다. Phase 1에는 차단 해제 경로가 없다. 반려 뒤 성공처럼 보이거나 같은 완료 Action으로 자동 재검증 대기를 만들면 안 된다.

**수용 기준:**

- **AC-F4.1:** 빈 Action, 필수 질문 미응답, 미승인/미완료 Action, 누락 결과로 해결할 수 없다(T5).
- **AC-F4.2:** 현재 owner 이외의 검증과 새 정보가 들어온 후 이전 버전 검증은 거부한다(T1, T6, T9).
- **AC-F4.3:** RETURN 이후 완료 Action은 남지만 자동 대기·RESOLVE가 금지된다(T10).

## 13. FR-11 — F4 해결 snapshot·조회

RESOLVE는 Incident 종료, 사람 검토 기록, resolved case snapshot, 이벤트를 동일 트랜잭션에 저장한다. snapshot은 원문·질문/답변·승인 내용·인수 이력·결과·최종 검증과 출처를 추적할 수 있어야 한다. 과거 사례 검색은 해결된 당시 기록을 참고 자료로 반환하며 현재 사건의 직접 사실로 바꾸지 않는다.

상세 화면은 해결 이후 조회 전용으로 사건 흐름을 보여준다. `/cases`에서 동일 사건의 해결 이력을 확인한다. Phase 1은 재개·수정·기존 사건 병합을 제공하지 않는다.

**수용 기준:** **AC-F4.4:** 새로고침/재시작 후 같은 ID로 최종 검토와 snapshot을 재조회한다(T8). **AC-F4.5:** 해결 뒤 늦은 메시지·완료·ACK가 snapshot을 바꾸지 않으며 거부 입력을 추적한다(T6).

## 14. FR-12 — F5 기능별 증거·전주기·제출

재곤은 F1/F3, 민재는 F2/F4의 실제 시험·변경·검토 근거를 남기고 서로 확인한다. 최종 통합은 별도 샘플 화면을 조합하지 않고 하나의 Incident ID로 수행한다.

- **AC-F5.1:** L1a/L1b/L2/L3와 T1~T12의 필수 하위 항목을 [시험 계획](07_TEST_PLAN.md)에 따라 실행하고 실패·미실행을 그대로 기록한다.
- **AC-F5.2:** 최소 네 live 업무 run과 API 호출 횟수, fake/live/replay를 구분한다. 권장 대조 평가를 안 했다면 했다고 주장하지 않는다.
- **AC-F5.3:** [제출 절차](15_SUBMISSION_RUNBOOK.md)에 따라 앱·시험·시연·PDF의 버전과 실제 접근·접수 상태를 확인한다. 개발 완료와 제출 접수 완료는 별도 상태다.

## 15. 범위 밖과 추적 문서

Phase 2는 충분한 입력 대조, 미응답 교대 시연 강화, 반려 후 다음 Action generation, 기한 알림 등이다. Phase 3는 음성·관리형 검색·작은 편의다. 실제 설비 제어·재가동 승인·복수 병렬 Action·운영 인증 체계는 Phase 1에 추가하지 않는다.

구현 순서·편집 경계는 [08](08_BUILD_PLAN.md), 화면은 [06](06_UI_SPEC.md), 실행 지시는 [12](12_CODEX_TASKS.md), 현재 구현 상태는 [PROGRESS](../PROGRESS.md), 실제 검증은 [시험 결과 양식](../templates/TEST_RESULTS.md)을 따른다.
