# F1 실행 계획

## 조건표

| ID | 종류 | 검증 명령 | 검사 경로 | Task |
| --- | --- | --- | --- | --- |
| AC-1 | change | `python3 scripts/check_f1.py AC-1` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T001, T012 |
| AC-2 | change | `python3 scripts/check_f1.py AC-2` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T001, T012 |
| AC-3 | change | `python3 scripts/check_f1.py AC-3` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T001, T002, T008, T012 |
| AC-4 | change | `python3 scripts/check_f1.py AC-4` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T002, T012 |
| AC-5 | change | `python3 scripts/check_f1.py AC-5` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T002, T007, T008, T012 |
| AC-6 | change | `python3 scripts/check_f1.py AC-6` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T002, T012 |
| AC-7 | change | `python3 scripts/check_f1.py AC-7` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T002, T012 |
| AC-8 | change | `python3 scripts/check_f1.py AC-8` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T003, T012 |
| AC-9 | change | `python3 scripts/check_f1.py AC-9` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T003, T011, T012 |
| AC-10 | change | `python3 scripts/check_f1.py AC-10` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T004, T012 |
| AC-11 | change | `python3 scripts/check_f1.py AC-11` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T005, T012 |
| AC-12 | change | `python3 scripts/check_f1.py AC-12` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T005, T012 |
| AC-13 | change | `python3 scripts/check_f1.py AC-13` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T005, T012 |
| AC-14 | change | `python3 scripts/check_f1.py AC-14` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T005, T012 |
| AC-15 | change | `python3 scripts/check_f1.py AC-15` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T005, T012 |
| AC-16 | change | `python3 scripts/check_f1.py AC-16` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T006, T012 |
| AC-17 | change | `python3 scripts/check_f1.py AC-17` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T006, T012 |
| AC-18 | change | `python3 scripts/check_f1.py AC-18` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T006, T012 |
| AC-19 | change | `python3 scripts/check_f1.py AC-19` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T007, T012 |
| AC-20 | change | `python3 scripts/check_f1.py AC-20` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T007, T012 |
| AC-21 | change | `python3 scripts/check_f1.py AC-21` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T008, T012 |
| AC-22 | change | `python3 scripts/check_f1.py AC-22` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T008, T012 |
| AC-23 | change | `python3 scripts/check_f1.py AC-23` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T009, T012 |
| AC-24 | change | `python3 scripts/check_f1.py AC-24` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T009, T012 |
| AC-25 | change | `python3 scripts/check_f1.py AC-25` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T010, T012 |
| AC-26 | change | `python3 scripts/check_f1.py AC-26` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T006, T009, T012 |
| AC-27 | change | `python3 scripts/check_f1.py AC-27` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T004, T012 |
| AC-28 | change | `python3 scripts/check_f1.py AC-28` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T004, T012 |
| AC-29 | change | `python3 scripts/check_f1.py AC-29` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T004, T012 |
| AC-30 | change | `python3 scripts/check_f1.py AC-30` | `scripts/check_f1.py`, `apps/web/package.json`, `apps/web/scripts/check-ac.mjs`, `apps/web/vitest.config.ts`, `apps/web/tests/api.test.ts`, `apps/web/tests/fixtures.ts`, `apps/web/tests/interaction.test.ts`, `apps/web/tests/polling.test.ts`, `apps/web/tests/state.test.ts` | T011, T012 |
| AC-31 | change | `python3 scripts/check_f1.py AC-31` | `scripts/check_f1.py`, `apps/web/package.json`, `apps/web/scripts/check-ac.mjs`, `apps/web/vitest.config.ts`, `apps/web/tests/api.test.ts`, `apps/web/tests/fixtures.ts`, `apps/web/tests/interaction.test.ts`, `apps/web/tests/polling.test.ts`, `apps/web/tests/state.test.ts` | T011, T012 |
| AC-32 | change | `python3 scripts/check_f1.py AC-32` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T011, T012 |
| AC-33 | change | `python3 scripts/check_f1.py AC-33` | `scripts/check_f1.py`, `scripts/f1_browser.py`, `tests/browser_worker.py`, `apps/web/package.json`, `apps/web/playwright.config.ts`, `apps/web/tests/real-api.spec.ts` | T012 |
| AC-34 | change | `python3 scripts/check_f1.py AC-34` | `scripts/check_f1.py`, `pyproject.toml`, `tests/backend/conftest.py`, `tests/backend/test_agent.py`, `tests/backend/test_boundary_integration.py`, `tests/backend/test_concurrency.py`, `tests/backend/test_intake.py` | T010, T012 |

## 범위

- 바꿀 수 있는 경로: `apps/api/**`, `apps/web/**`, `tests/**`, `scripts/check_f1.py`, `scripts/f1_*.py`, `pyproject.toml`, `requirements.lock`, `compose.f1.yaml`, `.gitignore`, `README.md`, `PROGRESS.md`, `TEST_RESULTS.md`, `CODEX_WORKLOG.md`, `docs/F1_IMPLEMENTATION.md`. SPEC의 현재 상태·적용 범위와 AC-33의 최소 검증 구성에 근거한다.
- 테스트 경로: `tests/**`, `apps/web/tests/**`, `apps/web/**/*.test.*`, `apps/web/**/*.spec.*`, `scripts/check_f1.py`, `scripts/f1_verify.py`.
- 유지할 동작: SPEC/TASKS와 F3 goal 문서 불변, v0.3 공통 계약·역할·불변 원문·generation 1·사람 해결 권한. F2/F3/F4 명령과 제품 구현은 추가하지 않는다. 기존 대화 내보내기 도구와 history ignore를 보존한다.

## Task

| ID | 목표 | 근거 | 제안 | 선행 | 필수 | 문서 |
| --- | --- | --- | --- | --- | --- | --- |
| T001 | 제보와 최소 공통 실행 기반 | AC-1, AC-2, AC-3 | W1 | — | 예 | — |
| T002 | 원문 추가·정정·해결 후 보존 | AC-3, AC-4, AC-5, AC-6, AC-7 | W2 | T001 | 예 | — |
| T003 | 범위가 제한된 목록·상세·근거 조회 | AC-8, AC-9 | W3 | T001 | 예 | — |
| T004 | 영속 Job·재시도·lease 복구 | AC-10, AC-27, AC-28, AC-29 | W4 | T001 | 예 | — |
| T005 | 실제 검색·근거·run 내부 후보 | AC-11, AC-12, AC-13, AC-14, AC-15 | W5 | T001 | 예 | — |
| T006 | Responses 루프·최종 판단·오래된 결과 거부 | AC-16, AC-17, AC-18, AC-26 | W6 | T004, T005 | 예 | — |
| T007 | 필수 질문 저장·중복 방지·대기 종료 | AC-5, AC-19, AC-20 | W7 | T006 | 예 | — |
| T008 | 지정 답변·새 조사·지속성 | AC-3, AC-5, AC-21, AC-22 | W8 | T002, T007 | 예 | — |
| T009 | F2 확정 호출·기존 작업 보존 | AC-23, AC-24, AC-26 | W9 | T006 | 예 | — |
| T010 | F4 준비 호출·반려 보류 | AC-25, AC-34 | W10 | T006 | 예 | — |
| T011 | 실제 상태·오류·근거를 보여주는 화면 | AC-9, AC-30, AC-31, AC-32 | W11 | T002, T003, T004, T007, T008, T009, T010 | 예 | — |
| T012 | 실제 UI·HTTP·PostgreSQL과 경계 검증 | AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-15, AC-16, AC-17, AC-18, AC-19, AC-20, AC-21, AC-22, AC-23, AC-24, AC-25, AC-26, AC-27, AC-28, AC-29, AC-30, AC-31, AC-32, AC-33, AC-34 | W12 | T001, T002, T003, T004, T005, T006, T007, T008, T009, T010, T011 | 예 | — |

## 예산

- 검증 실행: 100
- 경과 시간: 4시간
- 비용: 미관측

## 읽을 자료

### 필수 맥락

- SPEC.md와 TASKS.md 전체, docs/11_DECISIONS_AND_SOURCES.md D01–D07, docs/03_DOMAIN_MODEL.md, docs/04_API_CONTRACT.md.
- docs/05_AGENT_DESIGN.md, docs/06_UI_SPEC.md, docs/07_TEST_PLAN.md, docs/08_BUILD_PLAN.md.

### 필요할 때 참고

- docs/10_FIXTURES.md의 런타임 자료와 시험 oracle 분리, docs/ENVIRONMENT.md.
- F3 SPEC의 F1 공유 계약은 읽기 참조이며 구현 대상이 아니다.

### 판단 근거

- 사용자 요청: “@Seal F1부분만 진행해줘”.
- SPEC의 AC-33과 관련 맥락: 최소 공통 기반과 실제 PostgreSQL/HTTP/UI 검증, 명시된 외부 서비스 계약 대체 허용.
- OpenAI function calling strict mode 공식 문서: https://developers.openai.com/api/docs/guides/function-calling#strict-mode .

### 충돌·미확인

- 현재 실서비스 F2/F3/F4와 live 계정은 제공되지 않았다. 미연결 port는 업무를 부분 반영하지 않고 실패한다. 검증용 대체는 fake/contract로 표시한다.
- 검사 위임 파일은 구현과 함께 조건표 검사 경로에 모두 열거한 뒤 baseline/current 검증한다.
- 신규 조건 34개의 baseline/current 기록에 필요한 실행 예산은 ha의 실제 산정과 대조한다. 기본값을 임의로 늘리지 않는다.
