# ShiftLink 검증 결과

## 1. 현재 결과

아래 표는 문서 작성 당시 결과다. 이후 F0 실행 결과는 후속 절에 기록한다. F2 독립 결과는 별도 PR #5의 기록을 따른다. 실제 OpenAI 호출과 업무 전주기는 아직 미실행이다.

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


## F0 공통 기반 검증 — 2026-10-09 KST

- 기준: main `9de625e`에서 분기한 F0 변경. 시험 시 미커밋 상태, 커밋 후 내용은 기능별 F0 이력 참조.
- 환경: 호스트 Python 3.13.11, PostgreSQL 17, Node 24. Compose Python 3.12 / Node 24 이미지. 실제 모델 호출 없음.
- 데이터: 명세의 네 계정·두 설비·두 고정 교대. 초기 Incident 0개. 서버 시험은 별도 작업 DB 내 매회 고유 schema를 생성/삭제한다.

| 검사 | 실행·근거 | 결과·제한 |
|---|---|---|
| 서버·DB | `F0_TEST_DATABASE_URL` 지정 후 `/tmp/shiftlink-f0-venv/bin/python -m pytest apps/api/tests/core -q` | **35 PASS, 0 SKIP**. 세션 매핑·위조·Origin·만료·교대/사업장, receipt·경합·rollback·버전, lease 재claim/최종 검사/만료 복구, 설정·migration 시험 |
| migration | 실제 PostgreSQL에서 upgrade→downgrade→upgrade와 `alembic check` | **PASS**, metadata drift 없음 |
| Web | apps/web에서 Node 24로 `npm test` | **7 PASS**, happy-dom. 명령 재시도/충돌·계정 변경 상태·화면 슬롯/경로 |
| Web 타입·빌드 | `npm run build` | **PASS**, vue-tsc + Vite production bundle |
| 공유 DTO | `python scripts/export_contracts.py --check` | **PASS**, Python DTO와 생성 TS 일치 |
| Compose 첫 부팅 | 컨테이너에서 설정 파일 경로가 호스트와 달라 IndexError | **FAIL → 수정 후 PASS**, 상세 IMPROVEMENT_RECORD |
| Compose 수정 후 | `docker compose --env-file docs/history/f0-runtime.env -p shiftlink-f0 up --build -d` | **PASS**, db/api healthy, migrate/seed exit 0, worker/web running |
| 실제 HTTP | Web proxy를 통해 네 계정 로그인·/me·설비 2·교대 2 확인; 세 화면 경로 HTML 200 | **PASS**, 실제 렌더·클릭을 의미하지 않음 |
| worker 단일 실행 | 실행 중 두 번째 worker 기동 | **PASS**, singleton 잠금으로 두 번째 프로세스가 명시적으로 종료됨 |
| API 프로세스 재시작 | 실행 API 컨테이너 restart 후 기존 쿠키로 /me 재조회 | **PASS**, PostgreSQL 세션 보존 |
| 실제 브라우저·F1/F2/F3/F4 통합 | 후속 기능 연결 필요 | **NOT_RUN**. 이전 Chrome 자동 조작 권한 거부를 우회하지 않았음 |
| OpenAI live·업무 전주기·배포 | 범위 외 | **NOT_RUN** |

httpx TestClient deprecation 경고 1개가 남아 있다. 시험 원본·Compose 로그·HTTP 결과는 Git 제외 경로 docs/history/f0-*에 보존하고 비밀값이나 세션 쿠키는 결과에 포함하지 않는다. 실제 실행 DB는 Compose volume에 유지하며 초기 자료를 업무 성공으로 계산하지 않는다. 전체 T1~T12 또는 F5 완료를 주장하지 않는다.


## F0 리뷰 P1 수정 — 최초 조사 기준 버전

- 리뷰: PR #8 discussion_r4226641125, 최초 OPEN 사건에서 INVESTIGATING 전이 이전 version을 run에 고정하는 결함.
- 수정 전: OPEN에서 시작해 질문을 저장하는 새 회귀 시험 **1 FAIL**. claim 후에도 사건이 OPEN인 것을 확인했다. 기존 fixture는 INVESTIGATING에서 시작해 누락됐다.
- 수정: Job 예약 → 최초 조사 상태·버전·이벤트 커밋 → 현재 lease 아래 버전 확정/AgentRun 생성으로 분리. Incident→Job 잠금 순서를 유지하고 준비 변경과 F3 hook을 같은 transaction에서 처리한다.
- 수정 후: 실제 PostgreSQL 17 전용 DB에서 `python -m pytest apps/api/tests/core -q` → **48 PASS, 0 SKIP**. 기존 35 + 새 회귀 13.
- 추가 검증: 최초 OPEN에서 질문 저장·WAITING_INPUT 성공, 진행 상태 보존(5종), 재claim 시 최초 전이 한 번, 준비 전 만료/재할당 rollback, 준비 커밋 후 만료와 재확보, 준비 이후 최신 version 반영, hook 실패 rollback, Incident 대기 중 Job 선점 없음.
- 로그: Git 제외 `docs/history/f0-review-before.txt`, `docs/history/f0-review-after.txt`. 기존 실패 기록은 보존한다.
- Web 변경 없음으로 기존 Web 7 PASS·빌드 기록을 유지하며 이번에 다시 실행하지 않았다. F1 live와 실제 전주기 통합은 여전히 NOT_RUN. httpx TestClient deprecation 경고 1개 잔존.
