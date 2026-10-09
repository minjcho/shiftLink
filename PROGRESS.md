# ShiftLink 진행 기록

## 현재 상태

기준: v0.3 구현 문서 · 2026-10-09. 민재 담당 F2와 F4 종료 조건 검사 구현을 시작했다. F2 독립 기능·시험은 추가됐으며 F0 앱·DB·세션과 F1 실제 후보 연결을 기다린다. 실행 앱의 전주기 완료와 독립 기능 구현을 구분한다.

| ID | 작업 | 초기 담당 | 상태 | 다음 확인 |
|---|---|---|---|---|
| DOC | 구현 문서·환경 예시·ignore 규칙 | Codex 작성, 팀 검토 대기 | DONE | 정적 검사 완료, 실제 담당 착수 확인 |
| F0 | 공통 실행 기반·계약 | 재곤 통합, 민재 검토 | NOT_STARTED | 실제 앱·DB·세션·seed 부팅 |
| F1 | 접수·AI 조사·질문과 답변 | 재곤 | NOT_STARTED | 원문 재조회와 실제 모델 질문 |
| F2 | 작업 제안 확정·승인·착수·결과 | 민재 | IN_PROGRESS | 독립 서비스·라우터·패널·시험 구현, F0 실제 adapter/화면·F1 finalizer 연결 필요 |
| F3 | 교대 인계·인수 | 재곤 | NOT_STARTED | snapshot·ACK·owner 이전 |
| F4 | 최종 검증·해결 이력 | 민재 | IN_PROGRESS | 종료 조건 검사만 구현·시험. 사람 verification API·case·화면 미구현 |
| F5 | 전주기 검증·제출 | 공동 | NOT_STARTED | T/L 실행·배포·접수 근거 |
| Phase 2/3 | 판단 강화·확장 | 미배정 | NOT_STARTED | Phase 1 통과 전 착수하지 않음 |

상태는 NOT_STARTED / IN_PROGRESS / BLOCKED / DONE을 사용한다. BLOCKED에는 구체적인 이유와 다음 행동을 기록한다. 시험 결과는 별도로 NOT_RUN / PASS / FAIL / BLOCKED를 사용한다.

## 다음 구현 작업

사용자와 F0는 재곤 담당, F2 및 F4 준비 검사 함수는 민재 담당으로 합의했다. 다음 작업은 F0의 실제 transaction/receipt·session·공통 화면을 [F2 연결 계약](docs/16_F2_INTEGRATION.md)에 맞게 연결하고 PostgreSQL·실제 화면·F1 통합을 검증하는 것이다. 동일 Incident를 유지한다.

## 시간순 기록

| 일자 KST | 유형 | 실제 수행 | 검증과 한계 |
|---|---|---|---|
| 2026-10-09 | 문서 분석 | v0.3 MD·DOCX 내용 대조와 계약 검토 | 본문 동등성 확인. 앱·실제 모델 시험 아님 |
| 2026-10-09 | 문서 작성 | ZIP v0.2 구성을 참고해 v0.3 기능별 구현 문서와 .env.example 작성 | 문서·환경 정적 검사 완료. 앱 코드 미작성 |
| 2026-10-09 | 계약 교차 검토 | F2 반환·run 상태 분기·마지막 lease 만료 복구 계약을 대조하고 정정 | 상세 결과 TEST_RESULTS. 런타임 시험 NOT_RUN |
| 2026-10-09 | F2 구현 | 후보 확정·승인·반려·착수·완료, 주입형 API, 작업 패널, F4 준비 검사, F2 테이블 정의와 독립 시험 | F0 공통 기반 중복 구현 없음. 실제 앱/DB adapter·F1 live 연결 전; 결과는 TEST_RESULTS 후속 기록 |
| 2026-10-09 | F2 독립 실행 | 시험용 메모리 API·Vue 데모 실행. 실제 PostgreSQL 제약 13개 및 preview 시험 5개 추가 실행 | 서버 총 90 PASS, Web 17 PASS, 타입·실제 HTTP 흐름 PASS. 브라우저 자동 조작 및 F0/F1/F3 통합 미실행 |

| 2026-10-09 | F2 PR 정리 | 사용자 요청으로 임시 데모 화면·서버·전용 시험을 제거하고 실제 F2 기능을 기능별 커밋으로 정리 | 데모 서버 종료. 최신 검증 결과는 TEST_RESULTS 6절 |

후속 작업은 이 표에 추가하며 이전 사실을 지우지 않는다. 현재 요약은 최신 상태로 갱신하되 이력과 충돌하지 않게 한다.

## 제출 상태

배포 NOT_DEPLOYED · 리허설 NOT_RUN · 발표 PDF NOT_CREATED · 접수 NOT_SUBMITTED. 실제 링크·평가 SHA·접수 상태는 [SUBMISSION.md](SUBMISSION.md)에 기록한다.
