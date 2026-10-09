# ShiftLink 진행 기록

## 현재 상태

기준: v0.3 구현 문서 · 2026-10-09. 사용자 요청으로 main에서 F0 전용 브랜치를 만들고 민재가 공통 기반을 구현했다. F2/F4 준비 검사는 별도 PR #5에 있으며 아직 합치지 않았다. F0 실제 Compose·DB·HTTP와 독립 시험은 통과했고 사람의 브라우저 확인·기능 통합은 남아 있다.

| ID | 작업 | 초기 담당 | 상태 | 다음 확인 |
|---|---|---|---|---|
| DOC | 구현 문서·환경 예시·ignore 규칙 | Codex 작성, 팀 검토 대기 | DONE | 정적 검사 완료, 실제 담당 착수 확인 |
| F0 | 공통 실행 기반·계약 | 민재 구현 (이번 요청) | IN_PROGRESS | 실제 Compose·DB·세션 검증 완료. PR 검토·브라우저 확인 및 F1/F2 연결 |
| F1 | 접수·AI 조사·질문과 답변 | 재곤 | NOT_STARTED | 원문 재조회와 실제 모델 질문 |
| F2 | 작업 제안 확정·승인·착수·결과 | 민재 | IN_PROGRESS | 별도 PR #5. F0 병합 후 DB adapter·실제 화면·F1 연결 |
| F3 | 교대 인계·인수 | 재곤 | NOT_STARTED | snapshot·ACK·owner 이전 |
| F4 | 최종 검증·해결 이력 | 민재 | IN_PROGRESS | 준비 검사만 PR #5에 구현. 사람 검증·case는 후속 |
| F5 | 전주기 검증·제출 | 공동 | NOT_STARTED | T/L 실행·배포·접수 근거 |
| Phase 2/3 | 판단 강화·확장 | 미배정 | NOT_STARTED | Phase 1 통과 전 착수하지 않음 |

상태는 NOT_STARTED / IN_PROGRESS / BLOCKED / DONE을 사용한다. BLOCKED에는 구체적인 이유와 다음 행동을 기록한다. 시험 결과는 별도로 NOT_RUN / PASS / FAIL / BLOCKED를 사용한다.

## 다음 구현 작업

F0 PR을 검토·병합한 뒤 minjcho에 main을 반영하고 F2 DB adapter·세션·화면을 연결한다. 재곤의 F1/F3 업무는 유지한다. [F0 인계](docs/17_F0_FOUNDATION.md)의 migration 순서와 공통 상세 DTO를 사용한다.

## 시간순 기록

| 일자 KST | 유형 | 실제 수행 | 검증과 한계 |
|---|---|---|---|
| 2026-10-09 | 문서 분석 | v0.3 MD·DOCX 내용 대조와 계약 검토 | 본문 동등성 확인. 앱·실제 모델 시험 아님 |
| 2026-10-09 | 문서 작성 | ZIP v0.2 구성을 참고해 v0.3 기능별 구현 문서와 .env.example 작성 | 문서·환경 정적 검사 완료. 앱 코드 미작성 |
| 2026-10-09 | 계약 교차 검토 | F2 반환·run 상태 분기·마지막 lease 만료 복구 계약을 대조하고 정정 | 상세 결과 TEST_RESULTS. 런타임 시험 NOT_RUN |
| 2026-10-09 | F0 구현 | main에서 feature/f0-foundation 생성, 실제 DB·세션·명령/worker 기반·세 화면 셸·Compose 구현 | Python 35 PASS, Web 7 PASS, 빌드·migration 왕복·Compose·실제 HTTP·API 재시작 후 세션 유지 PASS. 기능 통합/실제 모델/브라우저 E2E NOT_RUN |
| 2026-10-09 | F0 P1 리뷰 수정 | 최초 OPEN 조사 상태 커밋 후 기준 버전 확정, lease·잠금·재시도 회귀 보강 | 수정 전 회귀 FAIL, 수정 후 PostgreSQL 서버 48 PASS. F1 live 통합 전 |

후속 작업은 이 표에 추가하며 이전 사실을 지우지 않는다. 현재 요약은 최신 상태로 갱신하되 이력과 충돌하지 않게 한다.

## 제출 상태

배포 NOT_DEPLOYED · 리허설 NOT_RUN · 발표 PDF NOT_CREATED · 접수 NOT_SUBMITTED. 실제 링크·평가 SHA·접수 상태는 [SUBMISSION.md](SUBMISSION.md)에 기록한다.
