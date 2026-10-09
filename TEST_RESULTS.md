# ShiftLink 검증 결과

## 1. 현재 결과

아래 초기 문서 검사와 이후 앱 시험을 분리한다. 초기 문서 작업은 앱을 실행하지 않았으며, 최신 F1/F3 실행과 한계는 하단 기록을 따른다.

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
