# ShiftLink 진행 기록

## 현재 상태

기준: v0.3 구현 문서 · 2026-10-09. F1의 Chromium 실행 차단이 해소됐고 실제 UI→HTTP→PostgreSQL, API·worker 재시작, 같은 질문에 대한 지정자 답변과 새 run 연결을 직접 확인했다. 원본 커밋의 Seal 완료 기록과 이번 F1 전용 PR 분리 소스의 직접 재검증은 [F1 실행 기록](docs/specs/f1-intake-investigation/PROGRESS.md) 및 [시험 결과](TEST_RESULTS.md)를 따른다. 실제 모델과 F2/F3/F4 전체 통합은 아직 확인하지 않았다.

| ID | 작업 | 초기 담당 | 상태 | 다음 확인 |
|---|---|---|---|---|
| DOC | 구현 문서·환경 예시·ignore 규칙 | Codex 작성, 팀 검토 대기 | DONE | 정적 검사 완료, 실제 담당 착수 확인 |
| F0 | 공통 실행 기반·계약 | 재곤 통합, 민재 검토 | IN_PROGRESS | F1 기준 Compose·세션·worker·타입·화면 slot 보강, PR #9 반영 |
| F1 | 접수·AI 조사·질문과 답변 | 재곤 | [Seal 판정](docs/specs/f1-intake-investigation/PROGRESS.md) | 후속 리뷰 보완 후 서버 133개·화면 70개·브라우저 기본3/변경 prefix3·빌드 PASS; F2 추가 Action은 이슈 #11로 추적하며 이 브랜치에서 수정·회귀 검증; live/타 기능 전체 통합은 별도 |
| F2 | 작업 제안 확정·승인·착수·결과 | 민재 | IN_PROGRESS | F1 기준 서버 연결·실제 HTTP/DB 검증 PASS. 작업 패널·F3/F4 전체 통합·live 후속 |
| F3 | 교대 인계·인수 | 재곤 | IN_PROGRESS | main/F2 서버 연결 및 P1 수정 검증 PASS; PR #7 병합 전, P2 #17/#18/#19 후속 |
| F4 | 최종 검증·해결 이력 | 민재 | IN_PROGRESS | 준비 검사만 PR #5, 사람 검증·case 후속 |
| F5 | 전주기 검증·제출 | 공동 | NOT_STARTED | T/L 실행·배포·접수 근거 |
| Phase 2/3 | 판단 강화·확장 | 미배정 | NOT_STARTED | Phase 1 통과 전 착수하지 않음 |

상태는 NOT_STARTED / IN_PROGRESS / BLOCKED / DONE을 사용한다. BLOCKED에는 구체적인 이유와 다음 행동을 기록한다. 시험 결과는 별도로 NOT_RUN / PASS / FAIL / BLOCKED를 사용한다.

## 다음 구현 작업

F1 PR #6에 F0 보강 PR #9가 병합됐다. #8의 독립 schema·worker·화면을 중복 병합하지 않는다. F2/F3/F4는 [새 F0 연결 계약](docs/17_F0_FOUNDATION.md)에 맞춰 ORM Session·FeaturePorts·상세 slot을 연결한다. 실제 모델 L1a/L1b/L2/L3는 별도다. F1 리뷰 수정은 아래 보완 명세와 최신 직접 검증 기록을 따른다. 기존 Seal 완료 기록을 이번 F0 검증으로 바꾸지 않는다.

리뷰 다섯 항목의 수정 범위는 [리뷰 수정 명세](docs/specs/f1-review-fixes/SPEC.md)에 정리했다. 불확실한 접수 복구·잠금 순서·인계 요약·모델 입력 예산·API prefix를 보완했으며 이번 직접 검증은 과거 Seal 완료 기록과 구분한다.

후속 네 리뷰는 [입력·목록·검색 보완 명세](docs/specs/f1-review-followups/SPEC.md)를 따른다. 답변·정정 혼합 입력 거부, 읽은 목록 페이지의 폴링 유지, 실제 문서 내용에 기반한 검색을 수정했다. 기본 실행에 아직 연결되지 않은 F2 어댑터의 반환 외 Action 생성은 [이슈 #11](https://github.com/minjcho/shiftLink/issues/11)로 남겼으며, F2 통합 전에 해결해야 한다.

## 시간순 기록

| 일자 KST | 유형 | 실제 수행 | 검증과 한계 |
|---|---|---|---|
| 2026-10-09 | 문서 분석 | v0.3 MD·DOCX 내용 대조와 계약 검토 | 본문 동등성 확인. 앱·실제 모델 시험 아님 |
| 2026-10-09 | 문서 작성 | ZIP v0.2 구성을 참고해 v0.3 기능별 구현 문서와 .env.example 작성 | 문서·환경 정적 검사 완료. 앱 코드 미작성 |
| 2026-10-09 | 계약 교차 검토 | F2 반환·run 상태 분기·마지막 lease 만료 복구 계약을 대조하고 정정 | 상세 결과 TEST_RESULTS. 런타임 시험 NOT_RUN |
| 2026-10-09 | F1 구현 | Vue·FastAPI·PostgreSQL·별도 worker와 최소 공통 기반, 필수 질문/답변·멱등·버전·lease·외부 port 경계 | 실제 실행과 Seal 최종 판정은 F1 실행 번들에 기록. live/타 기능 전체 통합 NOT_RUN |

| 2026-10-09 | F0→F1 통합 | 사용자 결정으로 F1 기반 별도 브랜치에서 Compose·세션 교대·단일 worker·타입 생성·상세 slot 이식 | 실제 시험 결과는 TEST_RESULTS의 F0/F1 절. 실제 모델/타 기능 통합 NOT_RUN |

| 2026-10-09 | F2 구현 | 후보 확정·승인·반려·착수·완료, 주입형 API, 작업 패널, F4 준비 검사, F2 테이블 정의와 독립 시험 | F0 공통 기반 중복 구현 없음. 실제 앱/DB adapter·F1 live 연결 전; 결과는 TEST_RESULTS 후속 기록 |
| 2026-10-09 | F2 독립 실행 | 시험용 메모리 API·Vue 데모 실행. 실제 PostgreSQL 제약 13개 및 preview 시험 5개 추가 실행 | 서버 총 90 PASS, Web 17 PASS, 타입·실제 HTTP 흐름 PASS. 브라우저 자동 조작 및 F0/F1/F3 통합 미실행 |

| 2026-10-09 | F2 PR 정리 | 사용자 요청으로 임시 데모 화면·서버·전용 시험을 제거하고 실제 F2 기능을 기능별 커밋으로 정리 | 데모 서버 종료. 최신 검증 결과는 TEST_RESULTS 6절 |

후속 작업은 이 표에 추가하며 이전 사실을 지우지 않는다. 현재 요약은 최신 상태로 갱신하되 이력과 충돌하지 않게 한다.

## 제출 상태

배포 NOT_DEPLOYED · 리허설 NOT_RUN · 발표 PDF NOT_CREATED · 접수 NOT_SUBMITTED. 실제 링크·평가 SHA·접수 상태는 [SUBMISSION.md](SUBMISSION.md)에 기록한다.

### 2026-10-09T12:53:10+09:00 F3 구현·직접 검증

F3 생성/조회/ACK, 불변 revision, 고정 cutoff와 추가 항목, owner 이전·재ACK, 실제 F1 갱신 port, Vue 생성/인수/상세 요약을 연결했다. PostgreSQL·HTTP 52개와 웹 빌드가 직접 통과했다. 화면 시나리오 3개는 정적 등록만 확인했고 런타임은 NOT_RUN이다. F1의 동일 Chromium 실행 권한 거부를 재시도하지 않는다. Seal 완료·live T8·배포 완료는 주장하지 않는다.

### 2026-10-09T13:07:51+09:00 F3 브라우저 환경 재확인

사용자 “다시 확인해줘 현재 세션에서” 요청으로 바뀐 권한 환경을 확인했다. Chromium156.0.8078.4가 정상 실행됐고 실제 F3 화면의 생성·인수·API 재시작, 새 원문 재인수·과거 revision·고정 cutoff, DB 조회 실패·409 수동 재확인·응답 유실 재시도·세션 전환 시험이 통과했다. 입력 fixture만 합성이며 F3 API·DB 성공 응답은 실제 구현이다. 사용자 “총 100회로 늘려 진행”으로 후속 검증 예산을 확정했다. F3 완료 여부는 중복된 정적 상태 대신 위 행의 Seal 실행 기록을 기준으로 확인한다.

### F3 PR 최초 제출 당시의 선행 의존성

F3 소스 브랜치는 `codex/f3-handover-pr`이며 최초 대상은 `jgoneit`이었다. 공통 실행 기반을 제공하는 F1 PR #6 위에 F3만 추가했다. #6이 병합되기 전에는 jgoneit 대비 diff에 F1 기반도 보이며, F3 자체 변경은 F1 PR head 대비33개 파일이다. 원본 완료 기록과 PR branch 직접 재검증은 TEST_RESULTS와 F3 실행 기록을 구분해 확인한다.

## F2 서버 연결 — 2026-10-09

`codex/f2-on-f1`에서 F1 #6 `c46d490`을 기준으로 #5의 서버 업무 로직·시험을 통합했다. Action-only 후보 staging, ORM adapter, 공유 receipt·세션·Origin, 공통 준비 검사와 API/worker 조립을 연결했다. 작업 중 새 F1 HEAD 7072e63을 발견해 통합하고 재검증했다. F2 화면 전체 완료를 선행 조건으로 두지 않고 승인·착수·결과·검증 대기 서버 경로를 먼저 검증했다.

최신 통합 서버 243 PASS(실제 DB와 독립 계약 시험 구분은 TEST_RESULTS), 기존 Web 70 PASS·타입/빌드·생성 계약 검사 PASS. 별도 uvicorn 프로세스의 실제 HTTP와 재시작 후 세션·결과·receipt 보존을 확인했다. F2 전체 DONE은 아니며 F4 사람 검증·F3 인수·live·브라우저 작업 패널은 후속이다.

## F2 리뷰 보완·병합 준비 — 2026-10-09

PR #5의 OpenAPI 필수 헤더 누락과 완료 입력 상한을 보완했다. 서버 249 PASS(기존243+회귀6), 생성 계약 검사 PASS. 사용자 요청에 따라 시간 제약으로 작업 패널 실제 연결·전체 전주기/live 검증은 [이슈 #16](https://github.com/minjcho/shiftLink/issues/16)으로 남긴다. Worker Lock #10 및 F1 #13/#14/#15는 기존 이슈를 유지한다. F2 전체 완료나 해당 결함 해결을 뜻하지 않는다.

## F3 main 통합·리뷰 보완 — 2026-10-09

병합된 F2 #5를 포함한 main `c726425`를 F3 브랜치에 통합했다. API와 worker의 공통 `production_ports()`에 F2 작업 확정·검증 준비·F3 인계 갱신을 함께 연결하고 main의 인증·입력 상한·worker 제어·상세 슬롯을 보존했다. 후보 확정 경계의 Approval ID 집합·DB 값 보존을 강화해 기존 Action 재사용 중 승인 추가와 SQL 우회 변경을 차단했다.

[별도 후속 명세](docs/specs/f3-main-integration-review/SPEC.md)는 기존 F3 목표와 완료 기록을 보존한다. 직접 서버 315 PASS, Web 70 PASS·타입/빌드·생성 계약 PASS, 실제 F3 브라우저 3개 PASS다. 인수→새 owner 승인→기존 assignee 수행·결과→재인수는 실제 API/DB로 확인했다. 모델 입력은 합성이며 전체 F2 화면·F4 해결·live·배포·제출 완료가 아니다.

리뷰 8건 중 P1 1건을 수정하고 main에서 해결된 4건을 보존·회귀 확인했다. 남은 P2는 [#17](https://github.com/minjcho/shiftLink/issues/17), [#18](https://github.com/minjcho/shiftLink/issues/18), [#19](https://github.com/minjcho/shiftLink/issues/19)로 추적한다. F2 패널과 전체 전주기는 기존 [#16](https://github.com/minjcho/shiftLink/issues/16)을 유지한다.
