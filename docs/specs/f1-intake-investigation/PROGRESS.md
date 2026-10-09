# F1 실행 진행

## 현재

- 확인 시각: 2026-10-09T12:45:34.461880+09:00
- 기록 head: seq 3 (18bd0a535250), 상태 blocked, 완료 기록 없음.
- 현재: F1 앱·검사·환경 구성의 WIP를 저장했다. 34개 AC의 ha baseline/current 검증은 아직 없다.
- 막힘: AC-33 native Chromium이 macOS MachPortRendezvous 권한 거부(1100)로 실행되지 않았다. Seal의 권한 오류 재시도 금지에 따라 중단했다.
- 미검증: 마지막 Agent timeout/fence/Approval/readiness 수정, 신규 경계 시험 21개, 실제 브라우저 재시작·답변 흐름.
- 외부 변경 보존: 별도 apps/api/app/features/handovers, apps/web/src/features/handovers, tests/handovers 파일이 나타났다. 이번 F1 변경에서 제외하고 미추적 상태로 보존한다.
- 재개: 사용자 재개 요청과 브라우저 실행 가능 환경이 필요하다. ha status로 상태를 재계산한 뒤 아래 재개 절차를 따른다.
- 직접 검사 통과는 참고이며 assurance local, 검사 작성자 executor다. 전체 F1 통합·live·배포 완료가 아니다.

## Task 상태

| Task | 상태 | 메모 |
| --- | --- | --- |
| T001 | doing | 접수/최소 공통 기반 구현, 직접 PostgreSQL 검증 통과; ha 기록 대기 |
| T002 | doing | 원문/정정/늦은 입력 구현, 직접 검증 통과; ha 기록 대기 |
| T003 | doing | 읽기 범위·인계 정보 투영 구현, 직접 검증 통과; ha 기록 대기 |
| T004 | doing | Job/lease/복구 구현, 최신 fence 수정 재검증 필요 |
| T005 | doing | 검색·근거·후보 구현, 최신 도구 deadline 수정 재검증 필요 |
| T006 | doing | Responses/DTO/실패 분류 구현, 커밋 기준 검증 대기 |
| T007 | doing | 전 질문 필수·중복 방지·WAITING_INPUT 구현, 최종 경계 검증 대기 |
| T008 | doing | 지정 답변·멱등·경합 직접 통과; 실제 브라우저 검증 대기 |
| T009 | doing | F2 caller transaction/반환 검사 구현, 마지막 Approval 보존 변경 미검증 |
| T010 | doing | F4 port/보류 구현, readiness 상세/신규 21개 경계 시험 미검증 |
| T011 | doing | 화면 단위 30개와 빌드 통과, 실제 브라우저 검증 대기 |
| T012 | blocked | AC-33 native 브라우저 권한 거부; baseline/current 전체 미기록 |

## 타임라인

### 2026-10-09T12:27:29.910759+09:00 · head none · 결정 [반영]

사용자 “@Seal F1부분만 진행해줘”에 따라 F1만 시작한다. SPEC151의 최소 실행 기반과 계약 대체를 사용하며 F2/F3/F4 제품 기능은 별도 책임으로 둔다. 기존 goal 문서와 대화 도구를 기준 커밋 b11945b로 보존했다.

### 2026-10-09T12:30:38.621197+09:00 · head seq 1 (245bf1e4723d) · 결정 [반영]

사용자 “100회로 증액 (권장)”에 따라 검증 예산을 50회에서 100회로 변경한다. 34개 change 조건의 baseline/current 최소 68회와 수정 후 검증 여유를 포함한다. 조건·범위·4시간 경과 예산은 유지한다.

### 2026-10-09T12:44:19.495319+09:00 · head seq 3 (18bd0a535250) · 막힘 [확정]

독립 PostgreSQL에서 접수·경합 16개, Agent 변경 전 50개, 화면 단위 30개와 빌드는 직접 통과했다. 이후 Agent의 timeout/fence/Approval/readiness 수정과 새 boundary_integration 21개 시험은 실행하지 않았다. 실제 browser harness는 Chromium 미설치 오류 후 설치를 마쳤지만 native 프로세스의 MachPortRendezvous 권한 거부로 사용자 흐름을 시작하지 못했다. 권한 오류는 재시도하지 않았으며 하위 작업도 중단했다. API·worker·Vue 시험 프로세스와 임의 schema는 정리했고 시험 DB 컨테이너는 재개용으로 보존했다.

## 계획 변경

| 시각 | 변경 | 이유 | 영향 | 다시 검토한 것 |
| --- | --- | --- | --- | --- |
| 2026-10-09T12:44:19.495319+09:00 | 검사 파일 경로 명시·실행 중단 | 같은 시각 타임라인 참조 | AC/Task 축소 없음 | 구현/검사/실제 브라우저의 증거 구분 |

## 막힘

| 시각 | 원인 종류 | 내용 | 해소 조건 |
| --- | --- | --- | --- |
| 2026-10-09T12:44:19.495319+09:00 | permission | 같은 시각 타임라인, ha block seq 3 | 사용자 재개 요청 및 실제 Chromium 실행이 허용된 검증 환경 |

## 개선 메모

설치된 ha run-rules/1은 start의 창별 50회 한도를 고정한다. 사용자가 승인한 총 100회 이내에서 baseline 34회 뒤 같은 승인 답변을 인용한 reopen으로 구현 검증 창을 열 계획이다. 지금은 baseline/current 실행 0회다. 기록이나 도구를 수정해 한도를 우회하지 않는다.

## 재개 절차

1. `ha status docs/specs/f1-intake-investigation`을 먼저 읽고 체크 시각/head와 현재 요약을 갱신한다. SPEC.md/TASKS.md는 수정하지 않는다.
2. 별도 F3 변경을 덮어쓰지 말고 격리된 F1 checkout으로 검증 범위를 확보한다. Chromium이 실행 가능한 승인된 환경을 확인한다. 기존 native 권한 실패 명령을 이 세션에서 재시도하지 않는다. 환경 문제가 해소되고 사용자가 재개를 요청한 후 ha unblock과 input을 기록한다.
3. PLAN 조건표의 검사 경로·배정과 새 tests/backend/test_boundary_integration.py를 검토하고 ha lint를 실행한다. 현재 21개 신규 경계 사례와 마지막 Agent 수정은 NOT_RUN이다.
4. 최소 접수·Agent·경계·웹 전체를 다시 실행하고 실제 migration/UI/HTTP/PostgreSQL·API/worker 재시작을 확인한다. 테스트 대체는 fake/contract로 유지한다.
5. 소스를 커밋해 깨끗한 트리에서 34개 baseline과 current 결과를 ha check로 기록한다. 사용자 승인 누적 검증 예산은 100회다. 부족 조건을 고치되 goal 문서를 낮추지 않는다.
6. 모든 Task/조건이 충족되어 ha done이 완료 기록을 출력할 때만 독립 F1 완료를 보고한다. L1a/L1b/L2/L3와 실제 F2/F3/F4 통합은 별도 평가로 남긴다.

## 완료 보고

**중단 보고이며 목표는 미완료다.** 최종 커밋 후 계산한 ha status 원문을 아래에 기록한다.

### 변경 파일과 조건 대응 — executor의 구현 주장

- `apps/api/app/core/`, `features/intake/`, `main.py`, migration: AC-1~10/21/22/29, 최소 공통 기반과 site·receipt·원문 계약.
- `apps/api/app/agent/`: AC-10~28/32/34, 검색·Responses·질문·finalizer·lease·실행 근거.
- `apps/web/`: AC-30/31 및 AC-33의 실제 UI 경로.
- `tests/`, `scripts/check_f1.py`, `scripts/f1_browser.py`: 각 AC에 연결한 검사와 독립 PostgreSQL/실제 HTTP/browser 환경.
- `pyproject.toml`, `requirements.lock`, `compose.f1.yaml`, `.gitignore`, 실행 안내·저장소 상태 문서: 재현 환경과 한계 기록.

직접 실행 결과는 TEST_RESULTS.md에 요약했다. ha check 기록은 0개이며 검사 결과 출력을 이 번들에 복사하지 않았다. 실행 환경 중단 전·후 변경의 신선도를 구분한다. 이 executor가 구현과 검사 모두 작성했으므로 보증 수준은 local이다.

### ha status

## ha status: docs/specs/f1-intake-investigation

- status: **blocked** (exit 3)
- completion record: none
- assurance: local (an agent with the same user permissions can change checks and records)
- check author: executor
- record head: seq 3 (18bd0a535250)
- rules: run-rules/1; skill: seal 0.1.6 (claimed); ha: 0.1.0-dev
- code: 0fbdbac19361, tree clean: no; goal digest: bee32e2097fc

### Criteria

| ID | kind | required | satisfied | reason | records | attempts |
| --- | --- | --- | --- | --- | --- | --- |
| AC-1 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-2 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-3 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-4 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-5 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-6 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-7 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-8 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-9 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-10 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-11 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-12 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-13 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-14 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-15 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-16 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-17 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-18 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-19 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-20 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-21 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-22 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-23 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-24 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-25 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-26 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-27 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-28 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-29 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-30 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-31 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-32 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-33 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |
| AC-34 | change | yes | no | criterion_missing | — | checks 0 (fail 0, error 0), baselines 0 (unexpected pass 0, error 0), stale 0 |

### Reasons

- `criterion_missing` (executor) AC-1
- `criterion_missing` (executor) AC-2
- `criterion_missing` (executor) AC-3
- `criterion_missing` (executor) AC-4
- `criterion_missing` (executor) AC-5
- `criterion_missing` (executor) AC-6
- `criterion_missing` (executor) AC-7
- `criterion_missing` (executor) AC-8
- `criterion_missing` (executor) AC-9
- `criterion_missing` (executor) AC-10
- `criterion_missing` (executor) AC-11
- `criterion_missing` (executor) AC-12
- `criterion_missing` (executor) AC-13
- `criterion_missing` (executor) AC-14
- `criterion_missing` (executor) AC-15
- `criterion_missing` (executor) AC-16
- `criterion_missing` (executor) AC-17
- `criterion_missing` (executor) AC-18
- `criterion_missing` (executor) AC-19
- `criterion_missing` (executor) AC-20
- `criterion_missing` (executor) AC-21
- `criterion_missing` (executor) AC-22
- `criterion_missing` (executor) AC-23
- `criterion_missing` (executor) AC-24
- `criterion_missing` (executor) AC-25
- `criterion_missing` (executor) AC-26
- `criterion_missing` (executor) AC-27
- `criterion_missing` (executor) AC-28
- `criterion_missing` (executor) AC-29
- `criterion_missing` (executor) AC-30
- `criterion_missing` (executor) AC-31
- `criterion_missing` (executor) AC-32
- `criterion_missing` (executor) AC-33
- `criterion_missing` (executor) AC-34
- `worktree_dirty` (executor): uncommitted changes outside the bundle documents; commit or revert them
- `task_open` (executor): required tasks not done or dropped in PROGRESS.md: T001, T002, T003, T004, T005, T006, T007, T008, T009, T010, T011, T012
- `blocked` (blocked): blocked since seq 3 (cause: permission)

### Budget

- window from seq 2: 0/50 runs, 655/14400 seconds

위 상태는 F1 구현 커밋 `0fbdbac`에서 확인했다. 별도 F3 미추적 파일 때문에 tree clean은 no이며, 해당 파일은 이번 커밋에 포함하지 않았다. 이 중단 보고를 저장하는 후속 커밋은 실행 번들만 변경한다.
