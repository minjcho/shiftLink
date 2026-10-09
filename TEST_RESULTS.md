# ShiftLink 검증 결과

## 1. 현재 결과

아래 초기 문서 검사와 이후 앱 시험을 분리한다. 초기 문서 작업은 앱을 실행하지 않았으며, 최신 F1/F3 실행과 한계는 하단 기록을 따른다.

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


## F1 구현 중 직접 확인과 중단 — 2026-10-09T12:43:14.951726+09:00

다음은 구현 중 직접 실행 결과이며 Seal의 커밋 기준 완료 증거가 아니다. 이후의 미검증 변경을 포함한 최종 WIP 전체 통과를 의미하지 않는다.

| 경계 | 명령/방식 | 마지막 관측 | 한계 |
| --- | --- | --- | --- |
| 접수 API·DB | pytest tests/backend/test_intake.py | 12 PASS | real PostgreSQL, 모델 미실행 |
| 실제 다중 연결 경합·F3 계약 rollback | pytest tests/backend/test_concurrency.py | 4 PASS | F3는 시험용 port 대체 |
| Agent·도구·lease·finalizer | pytest tests/backend/test_agent.py | 변경 전 50 PASS | 마지막 timeout/fence/Approval/readiness 변경은 NOT_RUN |
| 화면 상태 | npm run unit:ac -- 30 | 13 PASS | 컴포넌트/계약 검증 |
| 입력·세션·폴링 | npm run unit:ac -- 31 | 17 PASS | 네트워크/화면 대체를 사용하는 단위 검증 |
| 웹 빌드 | npm run build | PASS | 실제 사용자 흐름과 구별 |
| 실제 migration | Alembic upgrade head + seed | PASS | 독립 schema, PostgreSQL 17 |
| 실제 UI→HTTP→DB·프로세스 재시작 | scripts/f1_browser.py | BLOCKED | macOS Chromium MachPortRendezvous Permission denied 1100, 사용자 흐름 시작 전 중단 |
| Seal AC-1~34 | ha baseline/check | NOT_RUN | 완료 기록 없음, start/input/block만 기록 |
| L1a/L1b/L2/L3·타 기능 전체 통합 | 실제 모델/제품 서비스 | NOT_RUN | 독립 F1 완료와 별도 조건 |

Chromium 설치 전 첫 시도는 실행 파일 부재로 실패했고 설치 후 native 실행은 권한 오류로 중단됐다. 이 권한 오류는 재시도하지 않았다. 실제 API·worker·Vue 검증용 프로세스는 harness의 finally에서 정리했고 시험 schema도 삭제했다. 시험용 PostgreSQL 컨테이너는 재개를 위해 보존했다.

상세한 미완료 항목과 최종 상태는 docs/specs/f1-intake-investigation/PROGRESS.md를 따른다. 비밀값·원본 모델 추론은 기록하지 않았다.

추가 중단 상태: 신규 tests/backend/test_boundary_integration.py 21개 사례는 NOT_RUN이다. F3 별도 구현 디렉터리는 이번 F1 검증과 커밋에서 제외했다.

## F1 재개 직접 검증 — 2026-10-09T13:09:06.465724+09:00

제품 소스 기준 e97962cce31d6a76a715b4584feab904a2d3a064, 직접 실행 시 변경은 F1 실행 기록뿐이었다. PostgreSQL 시험 전용 컨테이너와 임의 schema를 재사용했고 .env를 읽지 않았다. 다음 직접 결과와 후속 Seal 커밋 기준 결과를 구별한다.

| 검사 | 결과 | 관측한 경계 |
| --- | --- | --- |
| Playwright Chromium 최소 기동 | PASS | headless 기동·페이지 생성·title 읽기·정상 종료, 과거 권한 오류 재현 없음 |
| `.venv/bin/python -m pytest -q` | 88 PASS | F1 서버 전체. 최신 timeout/fence/Approval/readiness 및 경계 21개 포함 |
| `npm --prefix apps/web run test` | 30 PASS | 화면 상태 13, API·입력·세션·폴링 17 |
| `npm --prefix apps/web run build` | PASS | Vue 타입 검사와 Vite 빌드 |
| `python3 scripts/check_f1.py AC-33` | 1 PASS | 실제 migration·Vue·HTTP·PostgreSQL, API/worker 재시작, 동일 원문/질문·지정 답변·새 Job/run |
| L1a/L1b/L2/L3·F2/F4 제품 서비스·전체 통합 | NOT_RUN | 브라우저 모델 fake, F2/F4 contract adapter; 별도 통합 평가 |

브라우저 모바일 화면도 확인했다. local artifact는 `apps/web/test-results/real-api-AC33-real-UI---HT-eaa44-estart-and-designated-reply/f1-mobile-persistent-reply.png`다. harness는 시험 API/worker/Vue와 생성 schema를 정리했다. 시험 컨테이너는 보존했다. 서버 검사에서 Starlette TestClient의 httpx 사용 deprecated 경고 1개가 있었으나 실패는 없었다.

34개 AC의 최신 커밋별 baseline/current seq와 완료 여부는 [F1 Seal 기록](docs/specs/f1-intake-investigation/PROGRESS.md)을 따른다. 검사 작성자는 executor, assurance local이다. 과거 실패는 위 이력에 그대로 남긴다.

## F1 전용 PR 분리 검증 — 2026-10-09T13:15:25.775226+09:00

사용자가 PR 대상을 jgoneit으로 지정했다. 원격 대상은 구현 전 공통 명세 b11945b, 소스는 F1 전용 codex/f1-intake-investigation-pr이다. 원본 로컬 jgoneit의 F3는 유지하며 PR diff에 포함하지 않는다.

| 검사 | 결과 | 실행 범위 |
| --- | --- | --- |
| `.venv/bin/python -m pytest -q` | 88 PASS | 분리된 F1 HTTP/PostgreSQL·worker·도구·계약 시험 |
| `npm --prefix apps/web run test` | 30 PASS | F1 화면·세션·입력·폴링 |
| `npm --prefix apps/web run build` | PASS | F1 Vue 타입 검사·프로덕션 빌드 |
| `python3 scripts/check_f1.py AC-33` | 1 PASS | 실제 F1 화면→HTTP→PostgreSQL, API/worker 재시작, 같은 질문 답변·새 run |
| F1 소스 범위 대조 | PASS | apps/tests/F1 scripts/환경 구성은 0fbdbac과 동일. F3 runtime hook·router·화면 없음 |
| `git diff --check` | PASS | 공백 오류 없음 |

직접 시험 당시 HEAD는 9c098cc이고 후속 F1 문서/기록 가져오기 변경만 dirty였다. 실행 소스와 시험 정의는 0fbdbac과 동일하다. 최종 PR commit은 문서·기록만 더하며 같은 실행 소스를 유지한다. PostgreSQL은 기존 시험 전용 컨테이너와 새 임의 schema를 사용했고 harness는 시험 프로세스/schema를 정리했다. 의존성은 동일한 기존 로컬 설치를 재사용했다.

보존한 Seal seq 84는 F3 포함 tree b4e63f4에서 생성된 과거 완료 기록이다. 이것을 PR 분리 SHA의 새로운 ha 완료로 보고하지 않는다. 이 절의 결과는 별도로 직접 실행한 검증이다. 실제 모델·F2/F3/F4 제품 통합·배포·제출은 NOT_RUN이며 모델 fake와 계약 대체를 명시한다.

## F3 구현 직접 검증 — 2026-10-09T12:53:10+09:00

기준 기반 b0bcb54c41ee, jgoneit의 F3 변경은 검사 시 미커밋이었다. 입력은 합성 fixture이며 DB는 독립 schema의 PostgreSQL 17.11, 세션·HTTP·F3 서비스는 실제 구현이다. 모델 호출은 없다. 검사 작성자는 executor, assurance local이다.

| 검사 | 결과 | 범위와 한계 |
| --- | --- | --- |
| `.venv/bin/python -m pytest -q tests/handovers` (PYTHONPATH=apps/api) | 52 PASS | 생성·조회·ACK·revision·권한·receipt·SQL 잠금 경합·rollback·실제 F1 current-lease SUPERSEDED |
| `python3 scripts/check_f3.py AC-18` | 3 PASS | 모델 부재·analysis-only/버전·F1 연결, 아직 ha 외 직접 실행 |
| `npm --prefix apps/web run build` | PASS | vue-tsc·Vite build; UI 런타임 증거 아님 |
| `npx playwright test tests/handovers.spec.ts --list` (apps/web) | PASS | AC-1/16/17 세 시험 등록만 확인 |
| `scripts/f3_browser.py AC-1/16/17` | NOT_RUN | 동일 환경 F1 Chromium 권한 실패가 기록돼 native 실행 재시도 보류; F3 사용자 흐름 미확인 |
| 전체 live T8·F2/F4 제품 연결·배포 | NOT_RUN | F3 합성 입력 경계와 별도 |

Seal baseline/current의 최종 기록 번호는 [F3 PROGRESS](docs/specs/f3-handover/PROGRESS.md)를 따른다. 브라우저 미실행을 PASS로 대신하지 않는다.

### 2026-10-09T12:55:37+09:00 F3 교차 회귀 보완

S-02의 해결 상태·재ACK 필요를 명시했고 두 경계를 회귀 시험에 추가했다. F1 시험 전체 첫 실행에서 F3 기본 hook 등록이 명시적으로 주입된 빈 FeaturePorts를 덮어써 기존 missing-adapter 시험 1개가 실패(87 PASS, 1 FAIL)했다. `create_app` 기본 구성과 명시적 주입을 구분해 수정했으며 기존 F1 시험은 변경하지 않았다. 최종 `PYTHONPATH=apps/api .venv/bin/python -m pytest -q tests/backend tests/handovers`는 **141 PASS (F1 88 + F3 53)**였다. 최종 Vue 타입 검사·빌드도 PASS다. 실제 브라우저 결과는 여전히 NOT_RUN이며 이 기록은 ha 밖에서 실행한 결과다.

## F3 실제 브라우저 재개 — 2026-10-09T13:07:51+09:00

권한 변경 후 native Chromium156.0.8078.4 실행이 성공했고 기존 block을 해제했다. 아래 결과는 실제 PostgreSQL17의 고유 schema, 실제 FastAPI·Vue, 모델 없는 합성 입력으로 확인했다. 자동화 성공 응답을 mock으로 대체하지 않는다. 네트워크 응답 유실은 실제 commit 뒤 응답만 끊어 재현한다.

| 조건 | 확인한 결과 | 기록 |
| --- | --- | --- |
| AC-1 | 실제 UI 생성·항목 ACK·동일 사건/Action/assignee·미해결 상태·상세 요약·reload/API restart·모바일 가로 넘침 없음 | PASS, ha seq55 |
| AC-16 | 새 원문 revision2·확인 중 원문 보존·수동 최신 확인/재ACK·과거 revision·cutoff 이후 추가·고정 시각·ACK 후 추가 표시 | PASS, ha seq56 |
| AC-17 | 성공한 빈 목록·실제 DB 조회 실패/복구·ACK 차단·409 표시/input 보존·명시 재확인·실제 commit 뒤 응답 유실과 동일 key replay·세션 전환 재전송 없음 | PASS, ha seq57 |

시험 선택자를 정확히 좁히고 키보드 제출의 버튼 준비를 기다리는 변경(eb5ad4e)이 있어, 최종 커밋의18개 조건 유효 판정은 F3 실행 bundle에서 다시 기록한다. 기존18개 baseline 무효 기록은 삭제하지 않았다. 유효 baseline/current, 최종 SHA·완료 기록은 [F3 PROGRESS](docs/specs/f3-handover/PROGRESS.md)를 따른다. 전체 live T8·F2/F4 제품 서비스·실제 모델·배포/제출은 NOT_RUN이다.

## F3 전용 PR 브랜치 재검증 — 2026-10-09T13:22:06+09:00

사용자 요청 “F3작업에 대한 내용을 jgoneit에 pr올려줘”에 따라 `codex/f3-handover-pr`를 F1 PR #6 head `ec6c9f1`에서 만들었다. 대상은 `jgoneit`이며 F1 선행 병합이 필요하다. F3 추가 diff는33개 파일로, F1 목표/실행기록·기존 시험·공유 migration은 바꾸지 않았다. F1 PR의 범위/검증 설명은 보존했다.

시험 시 source commit은 `740ed5a`이며 apps/scripts/tests와 의존성 파일은 원본 `fd10159`와 byte단위로 동일하다. 이후 추가한 PR 안내 문서는 실행 소스와 시험을 바꾸지 않는다.

| 검사 | 결과 | 범위 |
| --- | --- | --- |
| `PYTHONPATH=apps/api .venv/bin/python -m pytest -q tests/backend tests/handovers` | 141 PASS | F1 88 + F3 53, 실제 PostgreSQL·HTTP·경합 |
| `npm --prefix apps/web run build` | PASS | Vue 타입 검사·Vite |
| `.venv/bin/python scripts/f3_browser.py AC-1` | PASS | 실제 UI 생성·인수·API 재시작·같은 DB 재조회 |
| `.venv/bin/python scripts/f3_browser.py AC-16` | PASS | 변경 재인수·과거 revision·고정 cutoff·추가 항목 |
| `.venv/bin/python scripts/f3_browser.py AC-17` | PASS | 실제 DB 실패·409·응답 유실·동일 키 재시도·세션 전환 |
| 원본 앱/시험 byte동일성·F1 diff범위·공백 검사 | PASS | 기존 F1 계약/시험/기록 보존, 비밀값·history제외 |

Seal18/18·완료seq98은 원본 `31052bc`에서 얻은 기록이다. 새 PR SHA의 새로운 Seal 완료라고 주장하지 않으며 위 재검증은 별도의 직접 실행이다. 입력은 합성, 모델 호출은 없음, F3 경계는 실제 UI/HTTP/PostgreSQL이다. 전체 liveT8·F2/F4 제품 통합·배포·제출은 NOT_RUN이다. 검사 작성자는 executor, assurance local이다.

## F0를 F1 기준으로 이식 — 2026-10-09

기준 F1 `ec6c9f1`, 실행 코드/시험 커밋 `b5fc484` (`codex/f0-on-f1`). 아래 검사는 해당 소스의 커밋 직전 작업 트리에서 수행했으며 이후 변경은 문서·검증 기록이다. 원래 #8의 시험 결과를 이 브랜치의 결과로 재사용하지 않았다.

| 검사 / 실제 명령 | 결과 | 범위 |
|---|---|---|
| 변경 전 `.venv/bin/python -m pytest -q` | 88 PASS | F1 baseline, PostgreSQL 17 |
| 변경 후 `.venv/bin/python -m pytest -q` | 104 PASS | 기존 F1 + 세션·worker·migration·잠금 회귀 16개, Python 3.13 |
| `npm --prefix apps/web test` | 33 PASS | 기존 화면 + 계정 전환 재진입·API prefix·feature slot refresh |
| `npm --prefix apps/web run build` | PASS | Vue 타입 검사·Vite production build |
| `.venv/bin/python scripts/export_contracts.py --check` | PASS | 세션/enum 생성 타입 일치 |
| `PYTHONPATH=apps/api .venv/bin/python scripts/f1_browser.py` | 1 PASS | 실제 Chromium→HTTP→PostgreSQL. API/worker 재시작, 원문/질문 보존, 지정자 답변·새 run. **모델 fake** |
| migration 전환 시험 | PASS | 기존 0001 업무/legacy session 보존, 0002 upgrade·downgrade·upgrade 및 ORM drift 없음 |
| `docker compose --env-file .env.f0-on-f1 -p shiftlink-f0-f1 up --build -d` | PASS | Python 3.12·Node 24, migrate/seed exit 0, DB/API healthy, Web/maintenance worker running |
| Compose API `alembic -c apps/api/alembic.ini check` | PASS | 실행 DB와 ORM 불일치 없음 |
| 실제 Web proxy HTTP smoke | PASS | 네 계정·설비/교대 조회, 접수와 동일 receipt 재사용, API restart 후 세션·원문 유지 |
| 별도 worker 시작 | PASS | 두 번째 maintenance 실행 거부, key/model 없는 live 시작 거부 |
| maintenance 동작 | PASS | QUEUED/attempt 0 유지, 시험에서 최종 만료 run 복구 |
| 환경 생성기 | PASS | 새 파일 권한 0600, 기존 파일 재실행 시 내용 보존·실패 반환 |
| `git diff --check` / 환경 ignore | PASS | 기존 .env·대화 기록·cache 미추적 |
| 실제 모델 L1a/L1b/L2/L3, F2/F3/F4 제품 통합, 외부 배포·접수 | NOT_RUN | 위 fake/로컬 결과와 별도 |

잠금 순서 회귀는 F1 원본 `tools.py`로 실행 시 `jobs FOR UPDATE NOWAIT`가 LockNotAvailable로 실패했고, Incident를 먼저 잠그는 수정 후 통과했다. 사람 명령이 Incident를 보유한 채 Job을 잠그는 동안 검색 도구는 Incident에서 기다리므로 역순 교착을 만들지 않는다. 원본 코드로 실패를 재현한 뒤 수정본을 복원하고 전체 검사를 실행했다.

작업 중 새 시험 harness에서 venv python symlink를 resolve해 시스템 Python으로 실행한 실패와, enum을 좁힌 뒤 기존 시험 문자열의 타입 추론 오류가 있었다. harness는 현재 `sys.executable`, 시험 enum은 literal tuple로 정정해 위 결과를 확인했다. 서버 시험에는 기존 Starlette/httpx deprecation 경고 1개가 남는다. npm 설치는 기존 F1 lockfile에서 audit 3건(1 moderate, 2 critical)을 보고했다. 의존성 업데이트·공개 운영 배포 검증은 이번 범위에 포함하지 않았다.

Compose 검증은 기존 `shiftlink-f0`와 분리한 `shiftlink-f0-f1` project/volume, API 18000·Web 15173을 사용했다. 새 시험 DB 컨테이너는 `shiftlink-f0-f1-tests`, 임의 schema는 검사가 정리했다. 기존 F0 DB/volume·브랜치는 변경하지 않았다. HTTP smoke Incident `efc393d1-2d47-4ace-ae35-1f4dbf3f80db`, Job `5fa96da3-2181-405a-b3e3-2c4f9f145c45`는 새 Compose DB에만 생성했다. 비밀값·쿠키는 기록하지 않았다.

현재 코드에 남긴 후속 F1 리뷰 범위: 접수 재조회 실패 시 멱등키 보존, 최신 인계 선택 순서, 모델 문맥 크기 제한. 이번 보강에서 API base URL과 도구 잠금 순서 2건을 수정했으며 외부 리뷰 thread의 해결 상태를 자동 변경하지 않았다.


## PR #6 리뷰 수정 직접 검증 — 2026-10-09

대상은 기존 PR head `ec6c9f1`의 다섯 리뷰다. [수정 명세](docs/specs/f1-review-fixes/SPEC.md)는 기존 목표·완료 기록을 보존하는 별도 문서이며, 다음 결과는 새 Seal 완료 판정이 아닌 직접 실행 결과다. 다음 표는 F0 PR #9 통합 전 `59c4ce8`의 직접 검증이다. 이후 원격에 병합된 F0 `19b589c`를 보존해 통합했으며 최종 통합 검증은 후속 절에 기록한다.

| 검사 | 결과 | 확인한 범위 |
| --- | --- | --- |
| `PYTHONPATH=apps/api .venv/bin/python -m pytest -q tests/backend` | 108 PASS | 기존 88개와 신규 20개. PostgreSQL 격리 schema의 실제 HTTP·worker·잠금·인계·문맥 예산 |
| `npm --prefix apps/web run test` | 62 PASS | 기존 30개와 신규 32개. 불확실 요청·최신 조회·세션·API prefix·설정 거부 |
| `npm --prefix apps/web run build` | PASS | Vue 타입 검사·Vite 빌드 |
| `VITE_API_BASE_URL=/api/v1 PYTHONPATH=apps/api .venv/bin/python scripts/f1_browser.py` | 2 PASS | 실제 Chromium→Vue→HTTP→PostgreSQL. API/worker 재시작·지정 답변, 실제 저장 후 응답 유실·동일 receipt 재시도 |
| `VITE_API_BASE_URL=/gateway/api/v1/ PYTHONPATH=apps/api .venv/bin/python scripts/f1_browser.py` | 2 PASS | 비기본 prefix·끝 슬래시 정규화·개발 프록시를 통한 동일 두 흐름 |
| 실제 모델·전체 F2/F3/F4 제품 통합·배포·제출 | NOT_RUN | 모델 transport는 명시적 fake. 바이트 예산이 특정 모델의 context window 적합성을 보장하지 않음 |

수정 전 신규 회귀 시험에서 tool 저장과 RUNNING Job 재시도 두 경로의 `40P01` 교착, 생성 시각/동일 시각 인계 요약 오선택, 조회 후 멱등 키 유실 및 API prefix 무시를 확인했다. 입력 예산 시험에서는 14개 메시지의 모델 context가 1,309,427 bytes로 상한을 넘었다. 기존 시험을 지우거나 기대 결과를 완화하지 않고 해당 경계를 보완했다.

수정 후 잠금 시험은 실제 두 연결의 대기를 관측해 tool OK와 retry 409, 교착 없음 및 기다리는 동안 만료/재할당된 lease의 쓰기 거부를 확인한다. 인계 시험은 같은 사건의 복수 인계·동일 시각·삽입 역순·사업장/참여자 범위를 확인한다. 문맥 시험은 DB 원문 보존, 필수 trigger·질문/답변·Action·승인, 정정 연결의 전체 포함/생략, 생략 근거 인용 거부, 누적 도구 입력과 필수 정보 용량 초과를 확인한다.

브라우저의 장애 주입은 실제 API의 202와 저장 결과를 받은 뒤 첫 응답만 끊는다. 이후 조회 실패/성공에서도 입력과 원 키를 유지하고, 재시도는 `Idempotent-Replayed: true`, 같은 사건·Job ID를 반환한다. fresh schema의 사건 수는 1만 증가하고 같은 원문 Message는 한 건이다. 실제 서버 성공 응답을 합성하지 않았다.

harness가 생성 schema와 API/worker/Vue 프로세스를 정리했다. 원래 시험 컨테이너는 보존했다. 서버에는 기존 Starlette TestClient deprecation warning 1개가 있으며 실패는 없다. 검사 작성자는 Codex, 보증 범위는 local이다. 기본·비기본 경로 결과는 별도 실행이며 마지막 로컬 브라우저 산출물은 `apps/web/test-results/`, 프로세스 로그는 `.cache/f1-browser/`에 있다.


### F0 PR #9 동시 통합 후 최종 재검증

최초 push 전 원격 PR #6에 F0 PR #9(`19b589c`)가 병합되어 fast-forward push가 거부됐다. 이를 덮어쓰지 않고 리뷰 수정본을 새 원격 기반으로 통합했다. 실행 소스는 `8ef1dba`와 공개 슬롯 호환을 보완한 `34b154a`다. 서버는 `8ef1dba`에서 검사했으며 `34b154a`는 IncidentDetail의 슬롯 wrapper만 변경했다. UI·빌드 및 두 브라우저 경로는 그 wrapper를 포함한 소스로 확인했다. 이후 변경은 이 기록과 현재 요약뿐이다.

| 최종 검사 | 결과 |
| --- | --- |
| `PYTHONPATH=apps/api .venv/bin/python -m pytest -q tests/backend` | 124 PASS (F0/F1 104 + 새 회귀 20) |
| `PYTHONPATH=apps/api .venv/bin/python scripts/export_contracts.py --check` | PASS |
| `npm --prefix apps/web run test` | 65 PASS (F0/F1 33 + 새 회귀 32) |
| `npm --prefix apps/web run build` | PASS |
| 기본 `/api/v1` 브라우저 | 2 PASS |
| `/gateway/api/v1/` 브라우저 | 2 PASS |
| Compose 설정 연결 | PASS. 비밀이 아닌 시험 값과 `--env-file /dev/null`로 config를 해석해 API·worker 양쪽에 AGENT_MAX_INPUT_BYTES=65536 전달 확인; 컨테이너 재기동 없음 |

F0의 `lock_incident_graph → fence` 구현, 세션 교대 migration 0002, auth·모델, maintenance/live 단일 worker와 반려 사건의 조사 시작 제한을 보존했다. API client의 명시적 생성자 prefix 인자도 유지했다. F0의 공개 feature slot은 Promise<void> 계약을 유지하고 내부 재조회 결과 판단만 Promise<boolean>을 사용한다. 이 호환 보완 전 타입 검사에서 드러난 충돌을 고쳤으며 기존 시험의 기대값은 완화하지 않았다.

이번 최종 결과도 local 검증이며 실제 모델·전체 F2/F3/F4 통합·새 Compose 기동·배포·제출은 수행하지 않았다. F0의 과거 Compose 실행 결과는 위 원래 기록으로 보존한다.

## PR #6 후속 리뷰 네 항목 — 2026-10-09

기준은 F0 통합과 앞선 다섯 리뷰 수정이 포함된 `c46d490`이다. [후속 명세](docs/specs/f1-review-followups/SPEC.md)의 세 동작 결함을 고쳤고, 아직 기본 실행에 연결되지 않은 F2 어댑터 정합성은 [이슈 #11](https://github.com/minjcho/shiftLink/issues/11)로 남겼다. 아래 결과는 이 후속 변경 작업 트리에서 직접 실행했으며 새 Seal 완료 기록이 아니다.

| 검사 | 결과 | 관측 범위 |
| --- | --- | --- |
| `PYTHONPATH=apps/api .venv/bin/python -m pytest -q tests/backend` | 133 PASS | 기존 124 + 혼합 참조 3 + 검색 관련성 6. 실제 HTTP·PostgreSQL 격리 schema |
| `npm --prefix apps/web run test` | 70 PASS | 기존 65 + 목록 페이지 갱신 5. 페이지 순서·부분 실패·조회 경합·필터·세션 |
| `npm --prefix apps/web run build` | PASS | Vue 타입 검사·Vite 빌드 |
| `PYTHONPATH=apps/api .venv/bin/python scripts/export_contracts.py --check` | PASS | 공유 생성 타입 일치 |
| `VITE_API_BASE_URL=/api/v1 PYTHONPATH=apps/api .venv/bin/python scripts/f1_browser.py` | 3 PASS | 기존 재시작/답변·응답 유실/receipt + 실제 20개 초과 사건의 cursor 페이지·폴링 |
| `VITE_API_BASE_URL=/gateway/api/v1/ PYTHONPATH=apps/api .venv/bin/python scripts/f1_browser.py` | 3 PASS | 같은 세 흐름의 비기본 prefix·끝 슬래시 정규화 |
| 실제 모델·F2/F3/F4 전체 제품 통합·새 Compose 기동·배포·제출 | NOT_RUN | 모델은 fake. 기존 직접 검증과 외부 통합을 구분 |

혼합 참조 시험은 수정 전 세 경우 모두 202 저장으로 실패했다. 수정 후에는 `422 VALIDATION_ERROR`이고 Message·Request·Incident·Event·Job·CommandReceipt 전체 snapshot이 같다. 같은 멱등 키로 정상 답변·정정·일반 기록을 보내면 기존 동작대로 저장된다.

검색 시험은 수정 전 여섯 중 다섯이 실패했다. 실제 제목·본문에 일치가 없는 동일 설비 SOP가 조회 코드 또는 별칭 때문에 검색됐다. 수정 후 EMPTY/빈 근거를 확인하며, 실제 제목의 설비 코드·본문·별칭 일치와 승인·사업장·설비 범위, 동점 순서·개수·발췌 상한·ERROR 처리를 유지한다. OR 검색 의미는 바꾸지 않았다.

목록 회귀는 수정 전 다음 페이지가 폴링 뒤 사라짐을 확인했다. 수정 후 최신 cursor로 읽은 페이지 수만큼 갱신하며, 뒤 페이지 실패 시 기존 전체 목록·cursor·성공 시각을 보존한다. 실제 브라우저에서는 worker 처리가 끝난 20개 초과 사건을 읽고, 다음 폴링의 cursor 응답 완료와 성공 조회 시각 변경까지 기다린 후 전체 개수와 서버 순서를 대조한다. 코드 검토에서 요청 발생만 기다리던 초기 시험을 발견해 응답 반영까지 기다리도록 보강한 뒤 두 prefix에서 재실행했다.

이슈 #11은 격리 PostgreSQL과 시험용 F2 어댑터로 별도 재현했다. 유효한 MAIN_FOLLOWUP을 반환하면서 EXTRA_FOLLOWUP도 저장하면 Action 두 행과 Incident ACTION_REQUIRED, Job/AgentRun SUCCEEDED가 함께 남았다. 현재 API/worker 기본 FeaturePorts는 F2 미연결이므로 이번에는 코드 수정 없이 전체 Action 집합 검증과 원자적 rollback 조건을 이슈에 기록했다. 이 문제를 해결된 것으로 표시하지 않는다.

별도 읽기 전용 검토에서 세 제품 수정의 추가 확정 결함은 발견하지 못했다. Spec의 변경 전 설명을 기준 SHA로 한정하고 AC-1~6·유지 시나리오·결정 출처·실제 경계와 범위를 대조했다. 미결정 사항은 없으며, 저장 데이터·설정 형식·migration 변경은 적용 대상이 아니다. 서버에는 기존 Starlette/httpx deprecation warning 1개가 남는다. 브라우저 harness는 시험 schema와 API/worker/Vue 프로세스를 정리했다.

## F2/F1 서버 통합 직접 검증 — 2026-10-09

- 기준: F1 #6 `c46d490` + F2 #5 `3670cd2` 서버 로직 + `codex/f2-on-f1` 수정. 기존 이력/Seal 결과와 별도 직접 실행이다.
- 환경: Python 3.13, PostgreSQL 17(기존 시험 전용 서버, 매 시험 새 격리 schema), Node 25.9.0. 업무 DB와 volume은 수정하지 않았다.
- `F2_TEST_DATABASE_URL=<시험 DB> /private/tmp/shiftlink-f0-on-f1/.venv/bin/python -m pytest -q tests/backend apps/api/tests/actions`: **233 PASS, 0 SKIP**, 42.07초. 기존 F1/F0 124 + F2 독립 85(메모리/HTTP 계약 72·별도 stub 테이블 DB 제약 13) + 신규 실제 ORM/HTTP 24.
- 신규 24: 실제 F1 finalizer→F2 확정, 권한/두 버전, 빈 작업·미답변·승인/근거 결함, 멱등/충돌, 후속 인계 hook 실패 rollback, 초과 Action 삽입 거부, 최종 lease 만료 rollback, 동시 완료, REJECT 차단, 늦은 결과·불변 fixture snapshot, API/worker 공통 조립.
- 위 24 중 1개는 별도 uvicorn 프로세스·loopback HTTP·PostgreSQL로 제보/승인/착수/결과를 수행하고 API 프로세스 재시작 후 세션·같은 Action/결과·정확한 receipt 재사용을 확인한다. 모델 단계만 합성 후보/결과를 명시적으로 주입한다. 실제 모델 호출 증거는 아니다.
- 기존 migration 시험이 0001→head(0003)→0001→head 왕복, 기존 업무/legacy session 보존, ORM metadata drift 없음을 확인했다. 신규 실제 DB 시험은 승인 revision 중복 INSERT 거부를 확인했다.
- `python scripts/export_contracts.py --check`: PASS. 첫 시도는 Web 하위 경로에서 실행해 파일 경로 오류가 있었으며 저장소 루트에서 재실행해 통과했다.
- `npm ci`, `npm test`, `npm run build`: 설치 완료, 기존 Web **65 PASS**, vue-tsc·Vite production build PASS. Node 25에 대한 일부 전이 의존성 engine 경고와 기존 lockfile audit 3건(중간1·심각2)이 출력됐다. 이번 작업에서 의존성/lockfile은 변경하지 않았다.
- `git diff --check`: PASS.
- 중간 실패: 신규 다른 사건 근거 fixture를 만들 때 Incident INSERT 전에 Evidence FK UPDATE가 실행됐다. fixture의 부모 INSERT를 먼저 flush해 수정했고 전체 재검증 233 PASS. 생산 코드 결함으로 기록하지 않는다.
- 잔존 경고: 기존 Starlette/httpx TestClient deprecation 1개.
- **NOT_RUN:** F2 패널 브라우저 E2E, F3 실제 인수와 전체 T8, F4 RESOLVE/RETURN·실제 해결 사례 생성, L1a/L1b/L2/L3 실제 모델, 외부 배포·접수.

### 최신 F1 반영 후 최종 재검증

- 작업 중 F1 `7072e63`을 발견해 `c027c54`에서 통합했다. 기존 233 PASS 기록은 당시 c46d490 기반 실행으로 보존한다.
- 새 메시지/검색 시험 포함 재검증 242 PASS 이후, 실제 F2 adapter의 generation 1 작업 재사용과 rollback 시 analysis·proposal event 보존을 추가 확인했다.
- 최종 `F2_TEST_DATABASE_URL=<시험 DB> /private/tmp/shiftlink-f0-on-f1/.venv/bin/python -m pytest -q`: **243 PASS, 0 SKIP**, 50.87초. F1/F0 133 + F2 독립 85 + 신규 실제 ORM/HTTP 25. 시험 수집 경로에 기존 F2 독립 시험도 등록했다.
- 최신 F1 Web **70 PASS**, vue-tsc·Vite build PASS. 생성 계약·공백 검사 PASS. 최종 기반 확인 SHA `7072e63`. 실제 F2 패널의 브라우저 시험은 이 수에 포함되지 않는다.
- 이슈 #11은 이 브랜치의 전체 Action 집합 검사와 정상 생성·재사용·초과 생성 거부/rollback 시험으로 대응했다. 원격 이슈 상태는 변경하지 않았다.

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

## PR #5 업데이트 전 병합 검증 — 2026-10-09

기존 origin/minjcho 3670cd2 이력과 작업 패널을 F2 통합 브랜치에 merge했다. 서버·서버 시험·pyproject는 최종 243 PASS 소스 ff1fb4e와 동일함을 git diff로 확인했다. 기록은 양쪽을 보존했다.

- 기존 F2 패널: 독립 `npm test` **17 PASS**, `npm run typecheck` PASS.
- 공통 Web: `npm test` **70 PASS**, `npm run build` PASS.
- Node 25.9.0에서 실행. 기존 feature package의 Node engine 경고는 있었으며 의존성과 lockfile은 변경하지 않았다.
- 서버 시험은 코드 동일성 확인으로 이전 243 PASS 결과를 유지하며 이번 턴에 재실행하지 않았다.
- 화면 슬롯 연결·F3/F4 전체 통합·실제 모델은 후속이다. PR #5는 F1 브랜치를 대상으로 하는 Draft로 유지한다.

## F2 PR #5 리뷰 보완 — 2026-10-09

승인·착수·완료 production route의 필수 Idempotency-Key를 OpenAPI에 선언하고 공통 명령에 명시적으로 전달했다. 완료 result는 20,000자, evidence_refs는 100개로 제한했다.

- 실제 PostgreSQL 17 / Python 3.13: `F2_TEST_DATABASE_URL=<local test DB> /private/tmp/shiftlink-f0-on-f1/.venv/bin/python -m pytest -q` → **249 PASS, 0 SKIP**, 47.77초. 기존 243개 + 리뷰 회귀 6개.
- 회귀: 세 경로 OpenAPI 필수 헤더·헤더 누락 422, 결과/근거 초과 입력 422 및 DB/receipt 무변경, 최대 경계값 수용·원문 보존.
- `python scripts/export_contracts.py --check`, `git diff --check`: PASS.
- Web 수정 없음; 이번 Web 재실행 NOT_RUN(이전 공통70/F2 17 PASS 유지). 실제 모델·브라우저 전체 전주기·배포 NOT_RUN.
- 시간 제약으로 미완료 범위는 이슈 #16, Worker Lock 등 기존 #10/#13/#14/#15에서 추적한다. 해당 이슈는 이 시험의 해결 범위가 아니다.

## F4 사람 검증·해결 이력 직접 검증 — 2026-10-09

- 실행 코드: `978b12cdd4ba602e32dc823f86619a26714e861e`와 동일한 작업 트리. 기반 F2 `ff1fb4e`/F1 `7072e63`. 문서 커밋은 별도다.
- 환경: Python 3.13, PostgreSQL 17 시험 전용 서버의 매 시험 고유 schema, Node 25.9.0, Chromium, 실제 HTTP. 기존 업무 DB·Compose 서비스·volume은 변경하지 않았다.
- F4 `tests/backend/test_resolution.py`: **30 PASS**. 실제 F1 finalizer→F2 승인/착수/완료 후 F4 해결/RETURN을 사용한다. T1c/T2b/T5/T6/T10의 owner·사업장·근거·질문·결과·사유·검토 차단, 같은 응답 replay, snapshot/receipt rollback, 두 해결 요청, 메시지/해결 양방향 경합, case pagination/범위, 검색 source_type, 재시작을 확인했다.
- PR #7 `5486b8f10825ef63ebc608ee0f332c9b73629a88`의 실제 handovers 패키지 export를 시험에 조립한 `test_resolution_handover.py`: **3 PASS**. 미완료 ACK→같은 assignee 결과→새 owner 검증→단일 case, 이전 owner 차단, 과거 인계 revision 보존, 해결 뒤 늦은 ACK/replay, ACK/해결 양방향 경합. 제품 F3 통합 완료를 의미하지 않는다.
- 최종 전체 `SHIFTLINK_F3_FEATURE_ROOT=<기록한 F3 export> F2_TEST_DATABASE_URL=<시험 DB> python -m pytest -q`: **276 PASS, 0 SKIP**, 76.13초. 기존 F1/F0 133 + F2 독립 85(메모리/독립 HTTP72 + stub FK 테이블 DB 제약13) + F2 실제 ORM/HTTP25 + F4 실제 ORM/HTTP30 + 실제 F3 연결3. 실제 모델 호출 없음.
- 중간 기본 실행: **260 PASS, 13 SKIP**, 63.29초. F2_TEST_DATABASE_URL을 주지 않은 F2 독립 DB 제약13은 당시 SKIP이었다. F3 조건부 시험을 추가하기 전 실행이며 최종 276 결과와 구분한다.
- `npm --prefix apps/web test`: **78 PASS**(기존70 + F4 화면8). 불확실한 요청/503/잘못된 성공 body의 동일 key 재전송, 성공 후 재조회 실패, 버전 충돌, 작성 중 polling, 사건/계정 전환 뒤 늦은 응답을 포함한다.
- `npm --prefix apps/web run build`, `python scripts/export_contracts.py --check`, `git diff --check`: **PASS**. 기존 의존성·공유 생성 타입·migration은 변경하지 않았다.
- `PYTHONPATH=apps/api SHIFTLINK_F3_FEATURE_ROOT=<export> python scripts/f4_browser.py`: 기본 `/api/v1` **2 PASS**(3.7초). `VITE_API_BASE_URL=/gateway/api/v1/` **2 PASS**(5.5초). prefix 실행은 해결 후 추가 인수 불필요 표시 보완까지 포함한다.
- 브라우저 harness는 실제 migration 0001→0003, HTTP 제보/승인/착수/인수/완료, 명시적 결정론적 F1 tool/finalizer, 실제 F4 UI 해결/RETURN·case 읽기·API 프로세스 재시작을 사용한다. 선행 F2/F3 조작은 HTTP로 수행하며 질문/답변 전체 시나리오나 F2/F3 화면 E2E는 아니다.
- 스크린샷 `apps/web/test-results/.../f4-resolved.png`, `f4-return.png`를 생성했다. 해결 화면을 직접 시각 확인해 case/검토 사유/작성자/시각/업무 이력을 확인했다. 산출물과 실행 log는 Git 제외 경로에 있다.
- script는 자신이 시작한 API/Vue/Chromium과 고유 schema를 정리한다. F3 export는 제품 코드에 포함하지 않았다.
- 잔존 경고: 기존 Starlette/httpx TestClient deprecation 1개, 브라우저 NO_COLOR/FORCE_COLOR 충돌 경고. 시험 실패 없음.
- **NOT_RUN:** 모든 기능 화면과 실제 질문/답변을 포함한 전체 T8, 실제 모델 L1a/L1b/L2/L3, F3가 머지된 제품 기본 조립, 외부 배포·현장 사용·리허설·제출. worker guard 후속 이슈 #10은 이번 범위에서 변경하지 않았다.

### F2 PR #5 최신 이력 통합 확인

- `6b33370`에서 원격 minjcho `92cab3f`를 병합했다. 원래 F2 독립 패널/작업 이력을 보존했으며 문서 append 충돌은 양쪽 기록을 모두 유지했다.
- `978b12c`와 비교해 서버·F4 화면·F4 시험/harness 소스의 변경 없음. 전체 시험을 불필요하게 반복하지 않고 추가된 F2 패널이 포함된 공통 vue-tsc/Vite 빌드를 실행해 PASS를 확인했다. 산출물 JS hash도 동일했다.
- `git diff --check origin/minjcho...HEAD`: PASS. F2를 제외한 F4 기능 diff만 PR에 표시한다.

## F4 최신 main 반영·리뷰 준비 — 2026-10-09

- 기준: main c726425(F2 리뷰 보완 f053c58 포함)를 e551304에 병합. 충돌한 CODEX_WORKLOG/PROGRESS/TEST_RESULTS의 양쪽 기록을 보존했다. 공통 명령의 명시적 멱등 키 전달과 F2 완료 입력 상한을 유지한다.
- `SHIFTLINK_F3_FEATURE_ROOT=<기존 5486b8f export> F2_TEST_DATABASE_URL=<시험 DB> python -m pytest -q`: **282 PASS, 0 SKIP**, 66.93초. 이전276 + main의 F2 리뷰 회귀6. 테스트 소스 기준 e551304. 실제 PostgreSQL·F3 원본 서비스 연결이며 모델 호출 없음.
- `npm --prefix apps/web run build`, `python scripts/export_contracts.py --check`, `git diff --check origin/main...HEAD`: **PASS**. 기존 Starlette/httpx 경고1개.
- 화면 소스는 변경하지 않아 기존 Web78/브라우저 기본2·prefix2 PASS 기록을 유지하며 이번에는 재실행하지 않았다. 실제 모델·전체 T8·F3 제품 통합·배포는 NOT_RUN을 유지한다.

## F3 main 통합·승인 경계 리뷰 — 2026-10-09

기준: F3 `5486b8f`에 main `c726425`를 통합한 이번 소스. 원본 F3 완료 기록과 별도의 직접 검증이며 전체 F3 결함 해결·live·배포·제출 판정이 아니다. Python 3.14 / PostgreSQL 17.11 / 기존 web 의존성 환경. 각 DB 시험은 임의 schema만 생성·정리했다.

| 검증 | 결과 | 범위 |
| --- | --- | --- |
| `.venv/bin/python -m pytest -q tests/backend tests/handovers apps/api/tests/actions` | 315 PASS, 0 SKIP | 시험 전용 F2_TEST_DATABASE_URL 설정. F1/F2 서버·독립 계약·F3·추가 회귀 포함 |
| `npm --prefix apps/web test` | 70 PASS | 현재 공통 Web 실행 범위. F2 독립 패널 시험 17개는 이번에 재실행하지 않음 |
| `npm --prefix apps/web run build` | PASS | vue-tsc + Vite |
| `.venv/bin/python scripts/export_contracts.py --check` | PASS | 공유 enum·세션 타입 일치 |
| `.venv/bin/python scripts/f3_browser.py AC-1` | PASS | 실제 Vue/HTTP/DB 생성·ACK·API 재시작, dcf118c6a0e14f4eae98bcb27e683304 |
| `.venv/bin/python scripts/f3_browser.py AC-16` | PASS | revision·과거 내용·일반 추가 사건·cutoff, ea61f13a493142f7bfc4196c1e36897a |
| `.venv/bin/python scripts/f3_browser.py AC-17` | PASS | DB 오류·409·응답 유실 재시도·세션 전환, 8e76fd0ba56142268a087272047ca003 |

추가 회귀 13개: 승인 경계 8개(수정 전 3 FAIL/5 PASS, 수정 후 모두 PASS), 실제 F2/F3 업무·기본 조립 2개, 서로 다른 Job의 log/SOP/case 근거 동시 발급 3개. 승인 삽입·삭제·교체·ORM/SQL 수정 거부와 전체 rollback, 정상 생성/재사용을 구분했다. 인수→새 책임자 승인→기존 담당자 착수·완료→snapshot/completion_report·재ACK를 실제 API/DB로 확인했다.

F3 인증 fixture는 변경 전의 유효 세션을 준비한 뒤 권한 변경을 가해 403/401을 검사한다. 로그인 단계의 교대 미배정 거부와 현재 사업장 검사 자체는 변경하지 않았다. 기존 최신 인계 선택·목록 페이지·불확실한 명령 복구·잠금 순서를 보존했다.

검증 한계: 모델 결정은 합성 입력이다. F2 작업 패널·전체 브라우저 T8·F4 사람 검증·실제 모델·배포·제출은 NOT_RUN. P2 #17/#18/#19는 미수정이며 해당 재현을 PASS로 계산하지 않는다. 과거 동일 기능 시험과 이번 결과를 합산해 새 성능·안전성 주장으로 사용하지 않는다.


## F4 F3-main 병합·Job 조회 회귀 — 2026-10-09

기준: F4 `6614d8d`에 F3 포함 main `5edcef1`을 병합한 소스. Python3.13, 실제 시험 PostgreSQL의 고유 schema. F3 export 없이 기본 production_ports/routes를 사용했다.

- 신규 Web 회귀3: 수정 전 Job503 후 재검토/저장 성공 재조회2 FAIL, Incident 조회 실패 차단1 PASS. 수정 후3 PASS. F1의 Job 조회 실패 시 거부 명령 보존 시험도 PASS.
- `F2_TEST_DATABASE_URL=<시험 DB> python -m pytest -q tests/backend tests/handovers apps/api/tests/actions`: **348 PASS, 0 SKIP**, 99.92초. F3 기본 구성의 인수→완료→새 owner 해결 및 양방향 ACK/해결 경합 포함. 기존 Starlette/httpx 경고와 Pydantic alias 경고2개.
- `npm --prefix apps/web test`: **81 PASS**. 공통 Web70 + F4 기존8 + 신규3. 별도 F2 독립 화면17은 이번 범위에서 재실행하지 않았다.
- `npm --prefix apps/web run build`, `python scripts/export_contracts.py --check`, staged/unstaged diff check: **PASS**.
- `PYTHONPATH=apps/api python scripts/f4_browser.py`: 기본 prefix **2 PASS**(5.8초), `VITE_API_BASE_URL=/gateway/api/v1/` **2 PASS**(5.2초). 실제 F3 ACK/F2 완료 HTTP 선행, F4 UI 해결/RETURN, 해결된 인계 표시, API 재시작 후 불변 case 조회.
- `PYTHONPATH=apps/api python scripts/f3_browser.py AC-1`: **1 PASS**(4.7초), 생성·인수 UI/HTTP/DB·재시작 확인. 근거 `.cache/f3-browser/1b3aec4dad2046f79bbc9a3dfaf4a229/result.json`. 첫 실행은 harness가 요구한 `.venv/bin/python` 부재로 앱 시험 시작 전 실패했고, 기존 시험 venv를 임시 연결한 후 통과했다. 임시 연결은 제거했다.
- **NOT_RUN:** 실제 모델, 전체 질문/답변·F2/F3/F4 모든 화면을 포함한 T8, 배포·제출. F3 AC-16/17은 이번 실행에 포함하지 않음. F4 나머지 P2(헤더 명세, 해결 후 승인 표시, case 인수 이력)는 미수정이다.

## Toss 스타일 UI 통합 — 2026-10-09

기준 main `599fef3`, 브랜치 `feature/toss-ui-integrated`. 기존 기능 소스 위에 표시용 배너·아이콘·스타일과 App 탐색 배치를 변경했다. 사용자 요청으로 단위 테스트·타입 검사·빌드·브라우저 검증·실제 모델 호출은 **NOT_RUN**이다. 이전 기능 시험 PASS를 이번 UI의 검증 결과로 재사용하지 않는다.
