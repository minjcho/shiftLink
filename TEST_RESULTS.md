# ShiftLink 검증 결과

## 1. 현재 결과

아래 표는 문서 작성 시점의 결과다. 이후 F2 독립 기능 시험은 4~6절에 기록한다. 최신 PR 검증은 6절이다. 공통 실행 앱·실제 DB adapter·worker·OpenAI 호출은 여전히 미검증이다.

| ID | 검사·시험 | 결과 | 근거·제한 |
|---|---|---|---|
| DOC-01 | 문서 구성·상대 링크·JSON 예시 | PASS | ZIP의 25개 경로 모두 존재. Markdown 28개에서 상대 링크 128개·JSON 예시 14개 검사. 파일 존재와 JSON 문법 검사이며 API 실행 아님 |
| DOC-02 | F0~F5 담당·상태·계약 교차 확인 | PASS | D01~D07·03/04/05/07/08/12 대조. F2 반환·질문 대기 run·최종 lease 만료 정리 규칙 정정. Mermaid 원문 두 파일 일치, 렌더 미수행 |
| ENV-01 | .env·변형 파일 제외 / .env.example 포함 | PASS | git check-ignore로 제외 경로 6개·허용 example 경로 2개 확인. 환경변수 26개 문서화·비밀값 빈 값 검사, 실제 .env 미생성 |
| DOC-03 | diff·신규 파일 공백·fence | PASS | git diff --check 통과. 신규 Markdown 개행·충돌 마커·fence·의도하지 않은 줄끝 공백 확인 |
| T1~T12 | 서버 권한·멱등·경합·복구·전주기 | NOT_RUN | 앱·시험 코드 미구현 |
| L1a/L1b/L2/L3 | 필수 실제 모델 4개 run | NOT_RUN | worker·모델 설정·실호출 미구현 |
| L4 | 충분한 입력 대조 | NOT_RUN | 선택 검증, 필수 통과 후 우선 권장 |
| E2E | 실제 UI·API·DB 전주기 | NOT_RUN | 앱 미구현 |
| DEPLOY | 다른 기기/세션의 외부 접근 | NOT_RUN | 배포 미수행 |

## 2. 새 실행 기록

위 문서 검사는 2026-10-09 Codex 문서 작성 중 Python 표준 라이브러리의 경로·정규식·JSON 검사와 Git 읽기 명령으로 수행했다. 검사 당시 문서 변경은 미커밋 상태였으며 앱 구현 commit은 없었다. 검사 범위는 본 문서 묶음이며 기존 `scripts/export_codex_history.py` 동작은 이번 범위에 포함하지 않았다. 문서 게시 이력은 Git commit과 PR에서 확인한다.

[시험 양식](templates/TEST_RESULTS.md)을 사용해 시각·전체 앱 SHA·dirty 여부·모드·모델·자료·명령·run ID·기대/실제·근거 경로를 기록한다. T-ID의 하위 사례를 따로 기록해 일부 성공을 전체 성공으로 묶지 않는다. 이전 FAIL은 지우지 않고 수정 후 결과를 추가한다.

## 3. 판정 규칙

NOT_RUN은 실행하지 않음, PASS는 명시된 조건을 실제 만족, FAIL은 실제 실행 후 기대 미충족, BLOCKED는 외부 조건으로 실행/완료할 수 없음을 뜻한다. 문서 검사 PASS는 앱이나 모델 시험 PASS가 아니다.

## 4. F2 독립 구현 검증 — 2026-10-09 KST

- 기준 코드: `9de625e` 위의 미커밋 F2 변경, `working_tree_dirty=true`. 앱/배포 SHA 없음.
- 실행 환경: Python 3.13.11, FastAPI 0.143.0, Pydantic 2.14.0, SQLAlchemy 2.1.4, pytest 9.1.1. Web은 Node 24.21.0, Vue 3.5.43, Vitest 5.0.3, TypeScript 5.9.3, vue-tsc 3.3.12.
- 모드: 서버는 결정론적 메모리 transaction adapter + FastAPI TestClient, Web은 happy-dom component. OpenAI/fake Agent/replay를 실행하지 않았다.
- 합성 fixture: incident `00000000-0000-4000-8000-000000000401`, action `00000000-0000-4000-8000-000000000501`. 실제 사용자 세션/live 생성 ID 아님.

| 검사 | 실행 명령/근거 | 결과와 제한 |
|---|---|---|
| F2 서버 규칙·HTTP 계약 | `/tmp/shiftlink-f2-venv/bin/python -m pytest apps/api/tests/actions -q -rs` | **72 PASS, 13 SKIP**. 최종 실행 12:19 KST. 상태/권한/두 버전/receipt 재사용·범위/후보 최신성/승인 변조/결과/준비 조건/주입 실패 rollback 검증. 실제 DB 잠금·세션 보안 입증 아님 |
| F2 화면·HTTP client | feature 디렉터리에서 `npm exec --yes --package=node@24 --package=npm@11 -- npm run test` | **17 PASS**, 12:19 KST. 입력 보존·충돌 재검토·동일 키 재전송·조회 실패·세션 전환·결과 표시. 실제 브라우저 E2E 아님 |
| F2 Vue 타입 | 같은 디렉터리에서 `npm exec --yes --package=node@24 --package=npm@11 -- npm run typecheck` | **PASS** |
| F2 테이블 DDL 생성 | 공유 FK의 ID-only metadata fixture + PostgreSQL dialect `CreateTable/CreateIndex.compile` | **PASS**. 실제 SQL 실행 아님 |
| PostgreSQL 고유키·제약·생성 경합 | `test_postgres.py`, `F2_TEST_DATABASE_URL` 필요 | **BLOCKED / 13 SKIP**. Docker daemon은 접근 가능했으나 Docker Hub 및 ECR의 PostgreSQL 이미지 취득이 수 분간 진행되지 않아 해당 실행 프로세스를 종료. 테스트 DB 미생성. SQLite 대체 안 함 |
| F0/F1/F3 통합·T8 실제 전주기·L1b | F0 transaction/session/상세 화면, F1 finalizer, F3 revision hook 필요 | **NOT_RUN**. 공통 실행 앱·adapter 없음 |
| 실제 DB 재시작·DB 원자성/잠금·브라우저 E2E | F0 연결 후 실행 | **NOT_RUN**. 메모리 rollback 시험을 실제 DB 시험으로 계산하지 않음 |

Python 실행에는 Starlette의 httpx TestClient deprecation 경고 1개가 있다. 시험 실패는 아니며, F0가 공통 시험 의존성을 정할 때 검토한다. 전체 T1~T12 PASS로 승격하지 않는다. HTTP 입력 validation과 인증 오류의 공통 envelope·Origin·실제 세션은 F0에서 연결해야 한다.

초기 화면 시험에서 2건 실패(폴링으로 동일 사건 객체가 교체될 때 입력·retry가 초기화됨)를 재현해 수정했다. 초기 TypeScript 7과 vue-tsc의 도구 호환 오류는 TypeScript 5.9.3 고정으로 해결했고, 요청 키의 타입 추론 오류도 수정했다. 상세는 IMPROVEMENT_RECORD에 남긴다.

재현 절차 및 남은 연결은 [F2 인계](docs/16_F2_INTEGRATION.md), 로컬 서버 시험 원본은 Git 제외 경로 `docs/history/f2-verification/python-tests.txt`에 있다. 공개 기록에는 로컬 원본을 포함하지 않는다.

## 5. F2 실행·PostgreSQL 후속 검증 — 2026-10-09 KST

아래는 이후 제거된 임시 데모의 당시 검증 이력이다. 사용자가 브라우저 독립 데모를 선택해 시험용 메모리 서버와 Vue 실행 화면을 추가했다. 기준은 같은 `9de625e` 위 미커밋 변경이다. 실제 F0 앱·DB adapter와 구분한다.

| 검사 | 실제 결과 | 제한 |
|---|---|---|
| 기존 서버·PostgreSQL | **85 PASS** | 이번에는 로컬 postgres:17-alpine 이미지를 사용해 4절의 미실행 13개를 실제 실행. 기존 SKIP 기록은 보존 |
| 데모 harness 추가 후 서버 전체 | **90 PASS, 0 SKIP** | 기존 72 + 실제 PostgreSQL 13 + preview 5. 메모리 서비스 시험·DB 테이블 제약 시험·preview 시험을 구분 |
| 기존 Web | **17 PASS** | happy-dom 컴포넌트/통신 시험 |
| preview 포함 Vue 타입 | **PASS** | 신규 preview Vue/TS도 vue-tsc 검사에 포함 |
| 실제 데모 HTTP | **PASS** | localhost:5173의 HTML·Vue 모듈 200 및 Vite proxy를 통한 실제 승인→착수→완료→PENDING_VERIFICATION, 상태 재조회 결과·이벤트 3개 확인 |
| 브라우저 자동 클릭·렌더 확인 | **NOT_RUN** | CUA 브라우저 연결 없음, Google Chrome 자동 조작 사용 권한 거부. HTTP 확인을 실제 브라우저 조작으로 보고하지 않음 |
| F0 전체 DB adapter·세션·F1 live·F3 인수 통합 | **NOT_RUN** | 이번 독립 데모는 해당 기능을 대체하지 않음 |

실제 DB 시험은 `F2_TEST_DATABASE_URL`을 이번 작업 전용 PostgreSQL 17 컨테이너의 DB로 설정하고 `python -m pytest apps/api/tests/actions -q`로 실행했다. 각 시험은 고유한 f2_test_* schema만 사용했고 실행 후 삭제했다. 완료 후 테스트 컨테이너를 종료했다. 기존 사용자의 DB·볼륨은 사용하지 않았다.

데모 HTTP 검증 후 데이터는 사용자가 승인부터 시작하도록 초기화했다. API 8772와 Web 5173 서버는 실행 상태로 남겼다. 실제 HTTP 결과 원본은 Git 제외 경로 `docs/history/f2-verification/preview-http.json`에 저장했다. 메모리 데모의 결과 보존은 서버 프로세스 수명 안에서만 보장되며 DB 재시작 검증이 아니다.


## 6. 임시 데모 제거 후 F2 PR 검증 — 2026-10-09 13:03 KST

사용자 요청으로 preview 서버·진입 화면·전용 시험 5개와 실행 설정을 제거했다. 실제 F2 패널·서비스·라우터·DB 제약·독립 시험은 유지한다. 5절은 제거 전 실행 이력이며 현재 실행 안내가 아니다.

| 검사 | 명령·조건 | 결과 |
|---|---|---|
| 서버 전체 | `F2_TEST_DATABASE_URL`을 작업 전용 PostgreSQL 17 컨테이너로 설정하고 `/tmp/shiftlink-f2-venv/bin/python -m pytest apps/api/tests/actions -q` | **85 PASS, 0 SKIP** (기능/HTTP 72 + PostgreSQL 13) |
| Web 컴포넌트·client | feature 디렉터리에서 `npm exec --yes --package=node@24 --package=npm@11 -- npm run test` | **17 PASS** |
| Vue 타입 | 같은 환경에서 `npm run typecheck` | **PASS** |
| 패치·기록 제외 | `git diff --check`, `git check-ignore docs/history/2026-10-09_10-43-03-codex.md` | **PASS** |
| 데모 제거 | preview 파일·참조 제거, 포트 5173/8772의 LISTEN 없음 확인 | **PASS** |
| 실제 F0 DB adapter·세션·F1/F3·브라우저 E2E | F0 연결 전 | **NOT_RUN** |

시험 후 이번 작업의 PostgreSQL 컨테이너를 종료했다. httpx TestClient deprecation 경고 1개는 남아 있다. 서버 로그는 Git 제외 경로 `docs/history/f2-verification/pr-python-tests.txt`에 보존한다. 최종 코드 검증 후 기능별 커밋과 문서 커밋으로 정리하며, 공개 PR에는 대화 원문을 포함하지 않는다.
