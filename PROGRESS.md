# ShiftLink 진행 기록

## 현재 상태

기준: v0.3 구현 문서 · 2026-10-09. 기능별 개발 문서 작성과 정적 검사를 마쳤으며 팀 검토를 기다린다. 앱 구현은 시작하지 않았다. 문서 준비와 기능 구현 완료를 구분한다.

| ID | 작업 | 초기 담당 | 상태 | 다음 확인 |
|---|---|---|---|---|
| DOC | 구현 문서·환경 예시·ignore 규칙 | Codex 작성, 팀 검토 대기 | DONE | 정적 검사 완료, 실제 담당 착수 확인 |
| F0 | 공통 실행 기반·계약 | 재곤 통합, 민재 검토 | NOT_STARTED | 실제 앱·DB·세션·seed 부팅 |
| F1 | 접수·AI 조사·질문과 답변 | 재곤 | NOT_STARTED | 원문 재조회와 실제 모델 질문 |
| F2 | 작업 제안 확정·승인·착수·결과 | 민재 | NOT_STARTED | F1 finalizer와 Action 생성 서비스 연결 |
| F3 | 교대 인계·인수 | 재곤 | NOT_STARTED | snapshot·ACK·owner 이전 |
| F4 | 최종 검증·해결 이력 | 민재 | NOT_STARTED | 최신 조건의 사람 검증과 case |
| F5 | 전주기 검증·제출 | 공동 | NOT_STARTED | T/L 실행·배포·접수 근거 |
| Phase 2/3 | 판단 강화·확장 | 미배정 | NOT_STARTED | Phase 1 통과 전 착수하지 않음 |

상태는 NOT_STARTED / IN_PROGRESS / BLOCKED / DONE을 사용한다. BLOCKED에는 구체적인 이유와 다음 행동을 기록한다. 시험 결과는 별도로 NOT_RUN / PASS / FAIL / BLOCKED를 사용한다.

## 다음 구현 작업

사용자가 구현을 요청하면 [기능별 개발 계획](docs/08_BUILD_PLAN.md)과 [작업 지시](docs/12_CODEX_TASKS.md)의 F0부터 시작한다. 담당 배정은 초기안이며 실제 착수 시 확인한다. 가장 먼저 화면의 제보와 DB 재조회를 연결하고, 같은 사건을 계속 사용한다.

## 시간순 기록

| 일자 KST | 유형 | 실제 수행 | 검증과 한계 |
|---|---|---|---|
| 2026-10-09 | 문서 분석 | v0.3 MD·DOCX 내용 대조와 계약 검토 | 본문 동등성 확인. 앱·실제 모델 시험 아님 |
| 2026-10-09 | 문서 작성 | ZIP v0.2 구성을 참고해 v0.3 기능별 구현 문서와 .env.example 작성 | 문서·환경 정적 검사 완료. 앱 코드 미작성 |
| 2026-10-09 | 계약 교차 검토 | F2 반환·run 상태 분기·마지막 lease 만료 복구 계약을 대조하고 정정 | 상세 결과 TEST_RESULTS. 런타임 시험 NOT_RUN |

후속 작업은 이 표에 추가하며 이전 사실을 지우지 않는다. 현재 요약은 최신 상태로 갱신하되 이력과 충돌하지 않게 한다.

## 제출 상태

배포 NOT_DEPLOYED · 리허설 NOT_RUN · 발표 PDF NOT_CREATED · 접수 NOT_SUBMITTED. 실제 링크·평가 SHA·접수 상태는 [SUBMISSION.md](SUBMISSION.md)에 기록한다.
