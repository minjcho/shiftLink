# ShiftLink 검증 결과

## 1. 현재 결과

문서 검사와 앱 시험을 분리한다. 앱·DB·worker·실제 OpenAI 호출을 이번 문서 작업에서 실행하지 않았다.

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
