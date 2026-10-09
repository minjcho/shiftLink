# F1 구현과 실행 경계

## 제공 범위

F1의 접수·추가 원문·정정·지정 질문 답변·목록·상세·근거·Job 조회와 재시도, 자료 검색, Responses 실행, 질문 확정, 버전/lease 차단을 구현했다. 화면은 Vue 3, API는 FastAPI, DB는 PostgreSQL, worker는 별도 Python 프로세스다.

세션·DB·명령 receipt·공유 모델·마이그레이션은 F1을 실행하기 위한 최소 공통 기반이다. F2 승인/착수/결과, F3 인계 생성/ACK, F4 사람 검증/해결 endpoint는 제공하지 않는다. 모델이 제안한 draft는 정식 Action이 아니다.

## 기능 연결

| 호출 경계 | 기본 실행 | 다른 기능을 연결할 지점 |
| --- | --- | --- |
| F2 Action 확정 | 미연결이면 실패, 질문·Action·analysis 부분 확정 없음 | `FeaturePorts.action_finalizer`, 기존 caller-owned transaction 인자와 반환 계약 |
| F4 검증 준비 | 미연결이면 실패, 준비 성공을 합성하지 않음 | `FeaturePorts.readiness_evaluator`, `ready`와 미충족 조건 |
| F3 기존 항목 갱신 | 항목이 없으면 무효과, 기존 항목이 있으면 미연결 오류와 전체 rollback | `FeaturePorts.handover_refresher`, 같은 transaction의 Incident와 Event |

포트는 `create_app(..., ports=...)`와 `run_once(..., ports, ...)` 양쪽에 같은 서비스 구현을 주입한다. 공유 schema·migration head는 이 저장소에서 한 번에 통합한다. 최초 migration은 현재 ORM을 다시 읽지 않는 고정 DDL이다.

## 로컬 실행

설정은 프로세스 환경변수만 읽는다. `.env` 파일을 자동으로 열지 않는다. 아래 개발 환경은 localhost에만 노출한다.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
export PYTHONPATH=apps/api
export POSTGRES_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
export SESSION_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
export DATABASE_URL="postgresql+psycopg://shiftlink:${POSTGRES_PASSWORD}@127.0.0.1:55433/shiftlink"
export ALLOWED_ORIGINS=http://127.0.0.1:5173
export SESSION_COOKIE_SECURE=false
export DEMO_ACCOUNT_SWITCH_ENABLED=true
export AGENT_MODE=live
docker compose --env-file /dev/null -f compose.f1.yaml up -d db
.venv/bin/python -m alembic -c apps/api/alembic.ini upgrade head
.venv/bin/python -m app.core.seed
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

별도 터미널에서 웹을 실행한다.

```sh
cd apps/web
npm ci
npm run dev -- --host 127.0.0.1 --port 5173
```

`http://127.0.0.1:5173`에서 `reporter` 계정으로 제보한다. worker가 없어도 원문과 Job은 저장된다. seed는 합성 교대 A를 명시적인 현재 배정으로 선택한다. 시스템의 실제 날짜가 바뀌었다는 이유로 합성 교대 책임자를 자동 변경하지 않는다. 운영 교대 설정은 별도 통합 대상이다.

실제 worker는 같은 DB·세션 설정과 유효한 `OPENAI_API_KEY`, 검증한 `OPENAI_AGENT_MODEL`이 있어야 시작한다.

```sh
.venv/bin/python -m app.agent.worker
```

미설정·실패한 live를 fake로 전환하지 않는다. 이 구현 작업은 실제 계정 호출을 실행하지 않았으며 모델별 사용 가능 여부를 주장하지 않는다. Responses 전송은 strict schema, `store:false`, `parallel_tool_calls:false`, 같은 run output과 call ID를 보존한다. 스키마 제약은 [OpenAI 공식 function calling 문서](https://developers.openai.com/api/docs/guides/function-calling#strict-mode)를 따랐다.

## 독립 검증 환경

시험은 사용자 업무 DB와 분리한 PostgreSQL 17에서 매 시험마다 임의 schema를 생성·삭제한다. 기본 시험 URI의 계정은 localhost의 폐기 가능한 시험 전용 값이다. 다른 DB를 쓰면 `TEST_DATABASE_URL`을 명시한다. 기존 업무 데이터베이스를 시험 대상으로 지정하지 않는다.

```sh
docker run --detach --name shiftlink-f1-tests --label shiftlink.purpose=f1-isolated-verification --publish 127.0.0.1:55432:5432 --env POSTGRES_USER=f1_test --env POSTGRES_PASSWORD=f1_test_local_only --env POSTGRES_DB=f1_test postgres:17
.venv/bin/python -m pytest -q
npm --prefix apps/web run test
npm --prefix apps/web run build
cd apps/web
npx playwright install chromium
cd ../..
PYTHONPATH=apps/api .venv/bin/python scripts/f1_browser.py
```

이름이 같은 시험 컨테이너가 이미 실행 중이면 재사용한다. `scripts/f1_browser.py`는 실제 Alembic migration·seed, API, 별도 fake worker, Vue 서버와 Chromium을 연결한다. 브라우저가 원문·질문 ID를 확인한 뒤 API와 worker를 실제로 종료·재시작하고 지정자가 같은 질문에 답하는 흐름을 실행한다. 재시작 요청은 시험 프로세스 사이의 파일로만 전달하며 앱에 시험용 endpoint를 추가하지 않는다.

`tests/browser_worker.py`와 계약 검증용 포트는 시험 대체다. 런타임 worker의 기본 실행 경로가 이를 가져오지 않는다. UI/HTTP/PostgreSQL 연결 결과와 실제 모델 품질·F2/F3/F4 제품 통합 성공은 별도다.

## 기록과 다음 통합

[Seal 실행 진행](specs/f1-intake-investigation/PROGRESS.md)이 커밋·조건별 검사·완료 여부의 기준이다. [실행 계획](specs/f1-intake-investigation/PLAN.md)은 모든 AC를 실제 검사 명령에 연결한다. executor가 검사도 작성하며 보증 범위는 `local`이다.

F1 전체 통합 완료에는 SPEC의 L1a/L1b/L2/L3 실제 모델 run과 F2/F3/F4 서비스 연결 평가가 더 필요하다. 배포·제출·실제 현장 설비 검증은 이번 작업에 포함되지 않는다.

2026-10-09 재개 세션에서 Chromium 기동과 실제 AC-33 브라우저 흐름이 통과했다. 같은 PostgreSQL의 원문·질문을 API/worker 재시작 후 다시 읽고 지정 답변과 별도 새 run을 확인했다. 모델은 명시적인 fake이며 실제 모델 성공 증거가 아니다. 과거 권한 실패 기록은 [TEST_RESULTS](../TEST_RESULTS.md)에 보존하고, 커밋 기준 Seal 판정은 실행 기록에서 확인한다.

### F1 전용 PR 소스

이 PR은 F1 단독 실행 구성을 사용한다. F3 기본 서비스·router·화면은 포함하지 않고 외부 기능은 위 FeaturePorts 계약으로 연결한다. 기존 Seal 완료 기록은 원본 b4e63f4에 대한 결과이며, F1 전용 소스에서 다시 실행한 서버88·화면30·빌드·실제 Chromium 결과는 TEST_RESULTS.md의 분리 검증 절에 기록했다.
