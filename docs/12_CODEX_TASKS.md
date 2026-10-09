# 12. 기능별 Codex 구현 작업 지시

> v0.3 구현 문서 · 2026-10-09. 아래는 **향후 구현을 요청할 때 사용하는 지시 템플릿**이며 이번 문서 작성 중 실행한 작업이 아니다. 모든 구현 `NOT_STARTED`, 런타임 검증 `NOT_RUN`.
> 사용자는 이번에 구현용 문서와 환경 예시를 요청했다. 이 파일의 코드 블록만으로 앱 구현·실제 API 호출·배포·외부 제출을 시작하지 않는다.

## 1. 공통 시작 지시

사용할 기능 블록 앞에 다음 공통 지시를 붙인다. 기능 담당 배분은 [개발 계획](08_BUILD_PLAN.md)의 초기 제안이며 실제 수락·진척을 확인해 갱신한다.

```text
ShiftLink의 지정된 기능 하나를 구현한다.
AGENTS.md, README.md, PROGRESS.md, docs/01_PROJECT_PLAN.md,
docs/02_FUNCTIONAL_SPEC.md, docs/03_DOMAIN_MODEL.md,
docs/04_API_CONTRACT.md, docs/08_BUILD_PLAN.md,
docs/11_DECISIONS_AND_SOURCES.md를 먼저 읽어라.

작업 전 현재 branch/status, 실제 코드와 실행 환경을 확인하라.
문서의 예정 경로나 명령이 이미 구현됐다고 가정하지 마라.
v0.2는 문서 형식 참고이고 업무 기준은 v0.3 및 D01~D07이다.
배정된 기능의 UI·API·데이터·권한·테스트를 함께 구현하라.
동시에 작업하는 기능의 파일과 사용자 변경을 보존하라.
공유 DTO·enum·상세 화면 셸·migration head는 F0 통합 절차로 바꿔라.

해당 AC와 시험을 먼저 연결하고 구현 후 실제 API/화면으로 확인하라.
실제 실행 명령·commit·모드·ID·결과·남은 실패를 기록하라.
실행하지 못한 시험은 NOT_RUN 또는 이유가 있는 BLOCKED로 남겨라.
fake 계약 시험, live OpenAI run, replay, 브라우저 확인을 구분하라.
키는 서버 환경변수로만 읽고 .env 값이나 인증 정보를 출력·커밋하지 마라.
범위 밖 기능·범용 Agent 프레임워크·실제 설비 제어를 추가하지 마라.
문서만 작성하고 기능 완료로 보고하지 마라.
```

## 2. F0 — 공통 기반과 기능 경계

**담당 제안:** 재곤 통합, 민재 검토. **진입:** 구현 요청·실제 저장소 확인. **완료:** AC-F0.1~3.

```text
F0를 구현하라. 신규 기본값은 Vue 3 TypeScript, FastAPI/Pydantic,
PostgreSQL/SQLAlchemy/Alembic, 별도 단일 DB worker, Compose다.
동작하는 기반이 있으면 확인한 근거와 계약 차이를 적고 재사용하라.

네 데모 계정, 두 설비, 두 교대 발생과 서버 담당자 매핑을 seed로 만들고
/demo/session, /me, /equipment, /shifts를 공통 client와 연결하라.
Origin·세션 쿠키·서버 principal·오류 계약과 세 화면 셸을 구현하라.
/demo/session의 명시된 멱등 키 예외 외 도메인 쓰기는 키를 요구하라.
CommandReceipt, 공통 잠금/업무 버전 처리, Job attempt/lease 기반을 마련하라.
Agent 판단·업무별 서비스를 공통 core에 몰아넣지 마라.

F2 Action 확정 서비스와 F4 종료 준비 서비스의 입력·출력을 먼저 고정하라.
공유 Incident 상세 응답·패널 슬롯·migration 등록 순서를 기록하라.
.env.example의 소비 설정과 실제 부팅 명령을 코드에 맞춰 확인하라.
세션 위조/범위와 같은 키 재전송을 시험하고 실제 결과를 남겨라.
```

## 3. F1-a — 제보와 원문을 화면에서 DB까지

**담당 제안:** 재곤. **진입:** F0 계약/세션/DB. **완료:** AC-F1.1~3.

```text
FR-02와 S-01/S-02 원문 패널을 구현하라.
POST /incidents는 Incident·Message·이벤트·Job을 함께 저장하고 202를 반환한다.
별도 미연결 Report나 자동 병합 단계를 만들지 마라.
상태명이 그대로인 일반 추가 메시지도 Incident.version을 한 번 증가시켜라.
대상 질문 답변과 일반 추가 기록을 API·화면에서 구분하라.
검증 대기 중 새 정보는 재조사로, 해결 이후 입력은 보존된 거부 기록과
409 신규 제보 안내로 처리하라. 해결 snapshot은 변경하지 마라.

제보 입력 → 실제 API → DB → 상세 재조회까지 연결하라.
불확실한 접수 재전송은 같은 키를 쓰고 입력을 보존하라.
T2/T7/T9 관련 하위 시험으로 원문·Job·이벤트 수와 버전을 확인하라.
AI가 없어도 접수·재조회가 되는 실제 명령/브라우저 증거를 남겨라.
```

## 4. F1-b — 실제 AI 조사·질문·답변·최종 확정

**담당 제안:** 재곤. **진입:** F1-a와 F2 확정 인터페이스. **완료:** AC-F1.4~11, L1a/L1b/L2/L3.

```text
docs/05_AGENT_DESIGN.md대로 실제 Responses loop와 네 도구를 구현하라.
실제 모델/key의 지원을 smoke로 확인하고 모델 이름을 추정해 고정하지 마라.
조회는 OK/EMPTY/ERROR, 근거는 실제 서버 발급 ID·범위·출처로 관리하라.
propose_action은 이번 run의 후보만 만들고 업무 Action을 직접 만들지 마라.
초기 OPEN→INVESTIGATING 커밋 뒤 input_version을 고정하라.
최종 DTO·근거·대상·draft를 검증하고 동일 version과 유효 attempt/lease에서만
질문 또는 정식 Action을 한 트랜잭션으로 반영하라.
F2 finalize_action_proposal을 caller-owned transaction으로 호출하라.
업무 반영과 Job 성공/실패 갱신 모두 stale worker의 덮어쓰기를 차단하라.

질문은 지정 대상자·허용 purpose·유일키로 저장하고 대기 run을 종료하라.
사람 답변은 Request와 연결하고 새 Job/run이 최신 DB를 다시 읽게 하라.
기존 Action은 재사용하고 generation은 1로 유지하라.
review_required 상태에서는 분석만 갱신하고 업무 진행을 재개하지 마라.
원문·질문·답변·근거·이전 분석·오류 표시를 실제 화면에 연결하라.

L1a/L1b/L2/L3와 T3/T7/T9/T11을 실행하고 실제 도구·run ID를 남겨라.
모델 장애와 도구 ERROR를 받은 뒤 BLOCKED 선택 성공을 구분하라.
```

## 5. F2 — 작업 확정·승인·착수·결과

**담당 제안:** 민재. **진입:** F0 계약. F1 live 완료 전에는 계약 시험까지 병렬 진행. **완료:** AC-F2.1~8.

```text
FR-06~08의 Action 서비스·API·데이터·권한·S-02 작업 패널을 구현하라.
F1이 호출할 finalize_action_proposal 인터페이스부터 제공하라.
caller transaction에 참여하며 자체 commit 또는 모델 호출은 하지 마라.
이번 run/draft/input_version·근거·review_required를 확인하고
generation1 고유키와 활성 주 Action 최대 하나를 DB/서비스에서 강제하라.

현재 owner supervisor만 제안 승인/반려, 지정 assignee만 승인 후 착수와
진행 중 결과 제출을 하게 하라. Action과 Incident 버전을 모두 검사하라.
승인 payload와 해시를 저장하고 승인 후 내용·담당자 변경 API를 열지 마라.
반려 시 REJECTED·INVESTIGATING·review_required·사유를 함께 저장하라.
반려 후 새 Action 또는 검토 차단 해제는 Phase 1에 구현하지 마라.

결과 원문을 작성자·시각 있는 completion_report 근거로 저장하라.
기존 evidence_refs 추가는 선택사항이다. 같은 transaction에서 F4 준비 검사를
호출하고 충족 시에만 PENDING_VERIFICATION으로 바꿔라. 직접 해결하지 마라.
화면에서 승인할 전체 내용과 작업/사건 상태를 구분하라.
T1/T2/T5/T6/T10과 실제 F1 draft 연결을 검증하고 ID·개수·원자성 근거를 남겨라.
```

## 6. F3 — 교대 인계와 인수 책임 이전

**담당 제안:** 재곤. **진입:** shared 계약, 미해결 Incident와 Action. **완료:** AC-F3.1~4.

```text
FR-09와 S-03의 인계 생성/조회/ACK를 화면·API·DB·권한까지 구현하라.
출발 교대 지정 supervisor와 같은 사업장의 허용된 인접 교대 쌍을 검증하라.
교대 쌍 고유키로 중복을 막고 대상 집합은 서버가 결정하라.
재생성은 같은 인계의 이미 이전된 항목을 유지하되 다른 교대는 포함하지 마라.
질문·승인·작업·검증 대기 사건을 포함한 불변 revision/token을 만들고
DB 조회가 실패하면 ACK를 막아라. Phase 1 목록에 AI 설명은 필수가 아니다.

지정 수신 supervisor가 최신 version/revision/token으로 항목별 ACK할 때
owner만 이전하고 assignee는 유지하라.
snapshot7→ACK8 자체는 재인수를 만들지 않고 후속 정보9는 새 revision을 만든다.
재ACK는 수신 owner를 재확인하며 과거 revision을 덮어쓰지 마라.
해결 뒤 늦은 ACK는 입력 보존/거부, 같은 성공 ACK는 receipt 우선 반환하라.
cutoff 이후 새 사건·stale·추가 인수 필요를 화면에서 구분하라.
T4/T6/T12로 범위·중복·집합·책임·버전을 확인하고 실제 화면 증거를 남겨라.
```

## 7. F4 — 최종 검증과 해결 이력

**담당 제안:** 민재. **진입:** F2 승인/완료 자료, F3 owner 계약. **완료:** AC-F4.1~5.

```text
FR-10~11과 S-02 검증/해결 패널을 구현하라.
F1/F2가 사용하는 공통 종료 준비 서비스와 verification API를 분리하라.
review_required=false, 실제 필수 Action 존재·유효 승인·완료,
모든 필수 질문 답변, 같은 사건 결과 원문·근거를 검사하라.
빈 Action 집합을 완료로 처리하지 마라.
현재 owner supervisor만 최신 PENDING_VERIFICATION에 필수 notes로
RESOLVE 또는 RETURN을 제출하게 하고 잠금 안에서 조건을 다시 확인하라.

RETURN은 기존 COMPLETED Action을 유지한 채 INVESTIGATING과
review_required·사유를 저장한다. Phase 1 차단 해제 경로는 만들지 마라.
RESOLVE는 사건·사람 검토·해결 snapshot·이벤트를 원자 저장하라.
늦은 메시지/완료/ACK가 해결 snapshot을 바꾸지 못하게 하라.
화면에 준비 부족 사유·RETURN 차단·최종 확인자·해결 이력을 보여라.
T1/T5/T6/T8/T10으로 권한·경합·불완전 종료·반려를 검증하라.
```

## 8. F5 — 한 사건의 통합 검증

**담당:** 공동, 각자 F1/F3 또는 F2/F4 근거 책임. **진입:** G3 전주기 연결. **완료:** AC-F5.1~2.

```text
docs/07_TEST_PLAN.md와 docs/09_DEMO_RUNBOOK.md를 기준으로 통합 검증하라.
하나의 실제 Incident ID에서 네 서버 세션으로 제보→질문/답변→Action→승인→
착수→미해결 ACK→결과→수신 owner 검증→해결 이력을 수행하라.
새로고침·프로세스 재시작 이후 DB 기록/Job도 확인하라.
T1~T12의 필수 하위 시험을 각각 기록하고 대표 성공 하나로 대체하지 마라.
L1a/L1b/L2/L3의 최소 네 live 업무 run과 모델 호출 횟수를 구분하라.
단일 성공으로 판단 품질/운영 안전성을 주장하지 마라.

결함을 발견하면 재현 입력·원인·변경·영향받는 재검증을 기록하라.
앱/모델/프롬프트/자료/도구 변경 후 관련 시험을 다시 실행하라.
필수 통과 후 시간 여유가 있으면 새 기능보다 충분한 입력 대조 L4를 우선하라.
미통과 항목을 숨기거나 FAKE/REPLAY를 LIVE로 바꾸지 마라.
```

## 9. F5 — 제출 자료와 실제 제출 확인

**진입:** 제출 준비 시점, 기능 완성과 별도로 시간 확보. **완료:** AC-F5.3.

```text
제품 기능을 추가하지 말고 docs/13_JUDGING_EVIDENCE_MAP.md,
docs/15_SUBMISSION_RUNBOOK.md와 SUBMISSION.md를 사용해 제출 준비를 확인하라.
실제 앱·시험·배포·영상·PDF·저장소 SHA의 버전을 대조하라.
각자 맡은 기능의 구현과 시험 증거, Codex 작업·사람 검토·수정 근거를 연결하라.
가설·모의 자료·미구현 Phase·실행하지 못한 시험은 구분해서 작성하라.
허용된 범위에서 앱·PDF·저장소 접근과 실제 접수 완료를 확인하라.
작성한 링크나 SUBMISSION 체크박스만으로 제출됐다고 보고하지 마라.
docs/history 원문과 .env·키·개인정보를 공개 제출물에 포함하지 마라.
```

## 10. 공통 완료 보고 형식

`기능·AC / 실제 지시·세션 참조 / 변경 파일·commit / 실제 명령·모드·run 또는 사건 ID / 기대와 실제 / 근거 경로 / 사람의 채택·수정·거부 판단 / 남은 실패 / 다음 인계`

시험이 불가능했다면 이유와 필요한 다음 조건을 적는다. 계획한 명령과 실행한 명령을 구분한다. 필요한 기록은 [PROGRESS](../PROGRESS.md), [CODEX_WORKLOG](../templates/CODEX_WORKLOG.md), [TEST_RESULTS](../templates/TEST_RESULTS.md), [IMPROVEMENT_RECORD](../templates/IMPROVEMENT_RECORD.md)에 연결한다.

기능별 작은 변경 단위로 통합하고 공유 파일 변경은 상대 담당자에게 알려 확인한다. 제출·배포·외부 권한 변경은 해당 시점 사용자가 허용한 범위에서 수행한다. 이 문서가 별도 외부 작업 승인을 대신하지 않는다.
