# ShiftLink 진행 기록

## 현재 상태

기준: v0.3 구현 문서 · 2026-10-09. F1의 Chromium 실행 차단이 해소됐고 실제 UI→HTTP→PostgreSQL, API·worker 재시작, 같은 질문에 대한 지정자 답변과 새 run 연결을 직접 확인했다. 원본 커밋의 Seal 완료 기록과 이번 F1 전용 PR 분리 소스의 직접 재검증은 [F1 실행 기록](docs/specs/f1-intake-investigation/PROGRESS.md) 및 [시험 결과](TEST_RESULTS.md)를 따른다. 실제 모델과 F2/F3/F4 전체 통합은 아직 확인하지 않았다.

| ID | 작업 | 초기 담당 | 상태 | 다음 확인 |
|---|---|---|---|---|
| DOC | 구현 문서·환경 예시·ignore 규칙 | Codex 작성, 팀 검토 대기 | DONE | 정적 검사 완료, 실제 담당 착수 확인 |
| F0 | 공통 실행 기반·계약 | 재곤 통합, 민재 검토 | IN_PROGRESS | F1용 최소 DB·세션·seed·receipt 제공; 전체 F0 완료 별도 |
| F1 | 접수·AI 조사·질문과 답변 | 재곤 | [Seal 판정](docs/specs/f1-intake-investigation/PROGRESS.md) | 직접 서버 88개·화면 30개·실제 브라우저 및 빌드 PASS; live/타 기능 전체 통합은 별도 |
| F2 | 작업 제안 확정·승인·착수·결과 | 민재 | NOT_STARTED | F1 finalizer와 Action 생성 서비스 연결 |
| F3 | 교대 인계·인수 | 재곤 | [실행 기록의 현재 판정](docs/specs/f3-handover/PROGRESS.md) | 생성·ACK·재ACK·실제 UI/HTTP/DB 및 API 재시작 시험 통과 |
| F4 | 최종 검증·해결 이력 | 민재 | NOT_STARTED | 최신 조건의 사람 검증과 case |
| F5 | 전주기 검증·제출 | 공동 | NOT_STARTED | T/L 실행·배포·접수 근거 |
| Phase 2/3 | 판단 강화·확장 | 미배정 | NOT_STARTED | Phase 1 통과 전 착수하지 않음 |

상태는 NOT_STARTED / IN_PROGRESS / BLOCKED / DONE을 사용한다. BLOCKED에는 구체적인 이유와 다음 행동을 기록한다. 시험 결과는 별도로 NOT_RUN / PASS / FAIL / BLOCKED를 사용한다.

## 다음 구현 작업

사용자 “@Seal F1부분만 진행해줘”에 따라 F1과 그 최소 실행 기반을 구현한다. 다음 통합은 F2/F4 서비스 주입과 실제 모델 L1a/L1b/L2/L3이며 F3 생성·조회·ACK·화면 구현은 후속 요청으로 진행했으며 [F3 실행 기록](docs/specs/f3-handover/PROGRESS.md)을 따른다. 독립 F1 완료와 기존 기능 전체 완료를 구별한다.

## 시간순 기록

| 일자 KST | 유형 | 실제 수행 | 검증과 한계 |
|---|---|---|---|
| 2026-10-09 | 문서 분석 | v0.3 MD·DOCX 내용 대조와 계약 검토 | 본문 동등성 확인. 앱·실제 모델 시험 아님 |
| 2026-10-09 | 문서 작성 | ZIP v0.2 구성을 참고해 v0.3 기능별 구현 문서와 .env.example 작성 | 문서·환경 정적 검사 완료. 앱 코드 미작성 |
| 2026-10-09 | 계약 교차 검토 | F2 반환·run 상태 분기·마지막 lease 만료 복구 계약을 대조하고 정정 | 상세 결과 TEST_RESULTS. 런타임 시험 NOT_RUN |
| 2026-10-09 | F1 구현 | Vue·FastAPI·PostgreSQL·별도 worker와 최소 공통 기반, 필수 질문/답변·멱등·버전·lease·외부 port 경계 | 실제 실행과 Seal 최종 판정은 F1 실행 번들에 기록. live/타 기능 전체 통합 NOT_RUN |

후속 작업은 이 표에 추가하며 이전 사실을 지우지 않는다. 현재 요약은 최신 상태로 갱신하되 이력과 충돌하지 않게 한다.

## 제출 상태

배포 NOT_DEPLOYED · 리허설 NOT_RUN · 발표 PDF NOT_CREATED · 접수 NOT_SUBMITTED. 실제 링크·평가 SHA·접수 상태는 [SUBMISSION.md](SUBMISSION.md)에 기록한다.

### 2026-10-09T12:53:10+09:00 F3 구현·직접 검증

F3 생성/조회/ACK, 불변 revision, 고정 cutoff와 추가 항목, owner 이전·재ACK, 실제 F1 갱신 port, Vue 생성/인수/상세 요약을 연결했다. PostgreSQL·HTTP 52개와 웹 빌드가 직접 통과했다. 화면 시나리오 3개는 정적 등록만 확인했고 런타임은 NOT_RUN이다. F1의 동일 Chromium 실행 권한 거부를 재시도하지 않는다. Seal 완료·live T8·배포 완료는 주장하지 않는다.

### 2026-10-09T13:07:51+09:00 F3 브라우저 환경 재확인

사용자 “다시 확인해줘 현재 세션에서” 요청으로 바뀐 권한 환경을 확인했다. Chromium156.0.8078.4가 정상 실행됐고 실제 F3 화면의 생성·인수·API 재시작, 새 원문 재인수·과거 revision·고정 cutoff, DB 조회 실패·409 수동 재확인·응답 유실 재시도·세션 전환 시험이 통과했다. 입력 fixture만 합성이며 F3 API·DB 성공 응답은 실제 구현이다. 사용자 “총 100회로 늘려 진행”으로 후속 검증 예산을 확정했다. F3 완료 여부는 중복된 정적 상태 대신 위 행의 Seal 실행 기록을 기준으로 확인한다.
