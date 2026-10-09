# F3 실행 계획

## 조건표

| ID | 종류 | 검증 명령 | 검사 경로 | Task |
| --- | --- | --- | --- | --- |
| AC-1 | change | `python3 scripts/check_f3.py AC-1` | `scripts/check_f3.py`, `tests/handovers/__init__.py`, `tests/handovers/conftest.py`, `tests/handovers/helpers.py`, `tests/handovers/test_handovers.py`, `tests/handovers/test_concurrency.py`, `scripts/f3_browser.py`, `apps/web/tests/handovers.spec.ts` | T008, T009 |
| AC-2 | change | `python3 scripts/check_f3.py AC-2` | `scripts/check_f3.py`, `tests/handovers/__init__.py`, `tests/handovers/conftest.py`, `tests/handovers/helpers.py`, `tests/handovers/test_handovers.py`, `tests/handovers/test_concurrency.py` | T001, T009 |
| AC-3 | change | `python3 scripts/check_f3.py AC-3` | `scripts/check_f3.py`, `tests/handovers/__init__.py`, `tests/handovers/conftest.py`, `tests/handovers/helpers.py`, `tests/handovers/test_handovers.py`, `tests/handovers/test_concurrency.py` | T001, T004, T009 |
| AC-4 | change | `python3 scripts/check_f3.py AC-4` | `scripts/check_f3.py`, `tests/handovers/__init__.py`, `tests/handovers/conftest.py`, `tests/handovers/helpers.py`, `tests/handovers/test_handovers.py`, `tests/handovers/test_concurrency.py` | T001, T005, T009 |
| AC-5 | change | `python3 scripts/check_f3.py AC-5` | `scripts/check_f3.py`, `tests/handovers/__init__.py`, `tests/handovers/conftest.py`, `tests/handovers/helpers.py`, `tests/handovers/test_handovers.py`, `tests/handovers/test_concurrency.py` | T002, T009 |
| AC-6 | change | `python3 scripts/check_f3.py AC-6` | `scripts/check_f3.py`, `tests/handovers/__init__.py`, `tests/handovers/conftest.py`, `tests/handovers/helpers.py`, `tests/handovers/test_handovers.py`, `tests/handovers/test_concurrency.py` | T002, T009 |
| AC-7 | change | `python3 scripts/check_f3.py AC-7` | `scripts/check_f3.py`, `tests/handovers/__init__.py`, `tests/handovers/conftest.py`, `tests/handovers/helpers.py`, `tests/handovers/test_handovers.py`, `tests/handovers/test_concurrency.py` | T003, T009 |
| AC-8 | change | `python3 scripts/check_f3.py AC-8` | `scripts/check_f3.py`, `tests/handovers/__init__.py`, `tests/handovers/conftest.py`, `tests/handovers/helpers.py`, `tests/handovers/test_handovers.py`, `tests/handovers/test_concurrency.py` | T003, T009 |
| AC-9 | change | `python3 scripts/check_f3.py AC-9` | `scripts/check_f3.py`, `tests/handovers/__init__.py`, `tests/handovers/conftest.py`, `tests/handovers/helpers.py`, `tests/handovers/test_handovers.py`, `tests/handovers/test_concurrency.py` | T004, T009 |
| AC-10 | change | `python3 scripts/check_f3.py AC-10` | `scripts/check_f3.py`, `tests/handovers/__init__.py`, `tests/handovers/conftest.py`, `tests/handovers/helpers.py`, `tests/handovers/test_handovers.py`, `tests/handovers/test_concurrency.py` | T004, T009 |
| AC-11 | change | `python3 scripts/check_f3.py AC-11` | `scripts/check_f3.py`, `tests/handovers/__init__.py`, `tests/handovers/conftest.py`, `tests/handovers/helpers.py`, `tests/handovers/test_handovers.py`, `tests/handovers/test_concurrency.py` | T005, T009 |
| AC-12 | change | `python3 scripts/check_f3.py AC-12` | `scripts/check_f3.py`, `tests/handovers/__init__.py`, `tests/handovers/conftest.py`, `tests/handovers/helpers.py`, `tests/handovers/test_handovers.py`, `tests/handovers/test_concurrency.py` | T005, T009 |
| AC-13 | change | `python3 scripts/check_f3.py AC-13` | `scripts/check_f3.py`, `tests/handovers/__init__.py`, `tests/handovers/conftest.py`, `tests/handovers/helpers.py`, `tests/handovers/test_handovers.py`, `tests/handovers/test_concurrency.py` | T005, T006, T009 |
| AC-14 | change | `python3 scripts/check_f3.py AC-14` | `scripts/check_f3.py`, `tests/handovers/__init__.py`, `tests/handovers/conftest.py`, `tests/handovers/helpers.py`, `tests/handovers/test_handovers.py`, `tests/handovers/test_concurrency.py` | T006, T009 |
| AC-15 | change | `python3 scripts/check_f3.py AC-15` | `scripts/check_f3.py`, `tests/handovers/__init__.py`, `tests/handovers/conftest.py`, `tests/handovers/helpers.py`, `tests/handovers/test_handovers.py`, `tests/handovers/test_concurrency.py` | T006, T009 |
| AC-16 | change | `python3 scripts/check_f3.py AC-16` | `scripts/check_f3.py`, `tests/handovers/__init__.py`, `tests/handovers/conftest.py`, `tests/handovers/helpers.py`, `tests/handovers/test_handovers.py`, `tests/handovers/test_concurrency.py`, `scripts/f3_browser.py`, `apps/web/tests/handovers.spec.ts` | T007, T009 |
| AC-17 | change | `python3 scripts/check_f3.py AC-17` | `scripts/check_f3.py`, `tests/handovers/__init__.py`, `tests/handovers/conftest.py`, `tests/handovers/helpers.py`, `tests/handovers/test_handovers.py`, `tests/handovers/test_concurrency.py`, `scripts/f3_browser.py`, `apps/web/tests/handovers.spec.ts` | T007, T009 |
| AC-18 | change | `python3 scripts/check_f3.py AC-18` | `scripts/check_f3.py`, `tests/handovers/__init__.py`, `tests/handovers/conftest.py`, `tests/handovers/helpers.py`, `tests/handovers/test_handovers.py`, `tests/handovers/test_concurrency.py` | T006, T009 |
| EX-1 | maintain | `npm --prefix apps/web run build` | — | T007 |

## 범위

- 바꿀 수 있는 경로: `apps/api/app/features/handovers/**`, `apps/web/src/features/handovers/**`, `tests/handovers/**`, `apps/web/tests/handovers.spec.ts`, `scripts/check_f3.py`, `scripts/f3_browser.py`, `apps/api/app/main.py`, `apps/api/app/agent/worker.py`, `apps/api/app/features/intake/service.py`, `apps/web/src/App.vue`, `apps/web/src/lib/types.ts`, `apps/web/src/features/intake/IncidentDetail.vue`, `docs/F3_IMPLEMENTATION.md`, `README.md`, `PROGRESS.md`, `TEST_RESULTS.md`, `CODEX_WORKLOG.md`, `docs/F1_IMPLEMENTATION.md`, `docs/specs/f1-intake-investigation/PROGRESS.md`, `docs/specs/f1-intake-investigation/REVIEW.md`, `docs/specs/f1-intake-investigation/runs.jsonl`. SPEC의 범위와 제외 범위·API와 화면 연결·F1과 공유하는 연결 계약에 근거한다. 공유 파일은 기존 기능을 보존하는 router/port 등록·화면 슬롯 연결만 루트 통합 담당자가 변경한다.
- 통합 시 보존할 외부 변경: 위 F1 문서4개는 사용자 지정 jgoneit에서 별도 F1 작업이 이미 커밋한 내용을 그대로 포함하는 범위다. F3 실행자는 해당 문서를 편집하거나 F1 성과로 주장하지 않는다. 이전에 고정한 검증 checkout과의 앱·시험·의존성 diff가 없음을 확인했다. 동시 작업 기록까지 포함하는 run-rules/1의 범위 계산을 명시적으로 처리하며 목표/검증 기준은 바꾸지 않는다.
- 테스트 경로: `tests/handovers/**`, `apps/web/tests/handovers.spec.ts`, `scripts/check_f3.py`, `scripts/f3_browser.py`.
- 유지할 동작: SPEC의 AC-5/6/7/8/11/12/14/15/18, F1 접수·질문·원문·Agent의 기존 권한/버전/lease 경계. 다른 기능의 SPEC·실행 bundle·시험 정의·모델/마이그레이션은 수정하지 않는다.

## Task

| ID | 목표 | 근거 | 제안 | 선행 | 필수 | 문서 |
| --- | --- | --- | --- | --- | --- | --- |
| T001 | 교대 범위의 서버 대상 집합·생성·재사용 | AC-2, AC-3, AC-4 | W1 | — | 예 | — |
| T002 | 불변 snapshot/token·현재와 과거 조회 | AC-5, AC-6 | W2 | T001 | 예 | — |
| T003 | 책임 이전과 자기 ACK 최신성 | AC-7, AC-8 | W3 | T002 | 예 | — |
| T004 | 새 내용 revision·재ACK·고정 cutoff·추가 사건 | AC-3, AC-9, AC-10 | W4 | T002, T003 | 예 | — |
| T005 | 권한·receipt·고유키·원자적 실패 | AC-11, AC-12, AC-13 | W5 | T001, T003 | 예 | — |
| T006 | 해결 경합·반려·다른 기능 기록 보존 | AC-14, AC-15, AC-18 | W6 | T003, T004, T005 | 예 | — |
| T007 | 실제 API로 연결한 생성/인수/요약과 오류·재확인 화면 | AC-16, AC-17 | W7 | T001, T002, T003, T004, T005 | 예 | — |
| T008 | 같은 사건의 UI/API/PostgreSQL과 재시작 재조회 | AC-1 | W8 | T006, T007 | 예 | — |
| T009 | 전체 조건의 DB/HTTP/브라우저 결과와 Seal 기록 | AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-15, AC-16, AC-17, AC-18 | — | T008 | 예 | — |

## 예산

- 검증 실행: 100
- 경과 시간: 4시간
- 비용: 미관측

## 읽을 자료

### 필수 맥락

- SPEC.md 전체, docs/11_DECISIONS_AND_SOURCES.md D01~D07 → docs/03_DOMAIN_MODEL.md → docs/04_API_CONTRACT.md.
- docs/02_FUNCTIONAL_SPEC.md FR-09, docs/06_UI_SPEC.md S-03, docs/07_TEST_PLAN.md T4/T6/T12, docs/08_BUILD_PLAN.md.
- 공유 core/models.py·auth.py·transactions.py·ports.py, F1 intake/service.py의 상세 요약, main.py, web lib/api.ts·types.ts·App.vue.

### 필요할 때 참고

- docs/10_FIXTURES.md 합성 자료, F1 SPEC의 교차 계약, docs/ENVIRONMENT.md.

### 판단 근거

- 구현 요청 “@Seal”, 후속 작업 위치 지정 “jgoneit 브랜치에서 진행해줘”.
- 이 브랜치의 SPEC은 18개 AC이며 전체 live T8은 완료 후 공동 평가로 분리되어 있다. 이전 작업트리의 4-AC 목표를 이 브랜치에 덮어쓰지 않는다.
- F0/F1 기반 코드에 Handover 모델과 refresh hook·receipt·실제 세션이 제공되어 F3 전용 기능으로 연결할 수 있다.

### 충돌·미확인

- F1/공통 기반은 별도 작업이 b0bcb54c41ee까지 커밋했다. ha start seq 1은 이를 baseline으로 고정했다. 해당 기반의 변경은 F3 결과로 취급하지 않는다.
- PostgreSQL·HTTP 직접 시험 53개와 웹 빌드·브라우저 시험 정적 등록은 통과했다. 이전 Chromium 권한 block은 사용자 재확인 요청 후 변경된 환경에서 해소됐으며 실제 browser AC-1/16/17이 통과했다. 최종 commit의 조건별 freshness는 다시 기록한다. ha 기록 결과는 PROGRESS에서 확인한다.
- F2/F4의 실제 명령 및 전체 live T8은 제공되지 않아 공동 평가 NOT_RUN이다. F3 입력의 합성 fixture와 실제 F3 HTTP/DB/UI 검증을 구분한다.
