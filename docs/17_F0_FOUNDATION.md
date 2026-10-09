# F0 — F1 기반 공통 실행 환경과 연결 계약

2026-10-09 · 기준 F1 PR #6 `ec6c9f18983a5cbe420f71b725a7020a9b206aea` · 보강 브랜치 `codex/f0-on-f1`.

사용자 결정에 따라 F1의 작동하는 접수·질문·답변 흐름과 ORM·명령 처리·worker를 공통 구현 기준으로 채택한다. 독립 F0 PR #8의 다른 schema·초기 migration·화면 진입점은 합치지 않는다. #8의 Git 이력과 검증 기록은 보존하고 필요한 실행·권한·회귀 보장을 F1 구현으로 옮긴다.

## 실행

```sh
python3 scripts/setup_env.py
docker compose up --build -d
```

생성기는 기존 `.env`를 덮어쓰지 않는다. 별도 파일을 쓰려면 `--output .env.f0-on-f1`로 만들고 모든 Compose 명령에 `--env-file .env.f0-on-f1`을 사용한다. 기존 F0 환경과 동시에 실행할 경우 별도 project 이름 `-p shiftlink-f0-f1`, `APP_PORT`, `WEB_PORT`, 해당 포트의 `ALLOWED_ORIGINS`를 지정한다. 기존 DB volume이나 비밀값을 교체하지 않는다.

기본 Web은 `http://127.0.0.1:5173`, API는 `http://127.0.0.1:8000`이다. DB healthy → migration → seed → API healthy → Web/worker 순으로 실행한다. `/healthz`는 DB 연결을 검사한다. DB 포트는 노출하지 않으며 Web/API는 loopback에만 바인딩한다. 이 Compose는 로컬 개발용이다.

API는 모델 키 없이 제보·원문·질문 답변·Job을 저장한다. 기본 `WORKER_MODE=maintenance`는 마지막 attempt 만료 복구만 수행하고 QUEUED claim·모델 호출·임의 성공 처리를 하지 않는다. 따라서 새 제보의 AI 조사는 대기 상태다.

실제 조사 실행 시 로컬 설정에 유효한 `OPENAI_API_KEY`, `OPENAI_AGENT_MODEL`, `AGENT_MODE=live`, `WORKER_MODE=live`를 넣고 다음을 실행한다.

```sh
docker compose up -d --force-recreate worker
```

같은 worker 서비스가 maintenance에서 live로 교체된다. key/model이 없으면 시작 오류이며 fake로 전환하지 않는다. 독립 호스트 실행은 `python -m app.agent.worker --mode live` 또는 `--mode maintenance`다. 실제 모델 접근·L1a/L1b/L2/L3는 NOT_RUN이다.

## 보존한 공통 구현

| 영역 | 통합 기준과 이식한 보장 |
|---|---|
| DB | `app.core.models.Base`, SQLAlchemy ORM `Session`, `core.db.create_session_factory` |
| 명령 | F1 `execute_command`: site/actor/key, method/route/body 해시, advisory lock, 완료 응답 우선 재사용 |
| 업무 버전 | F1 `bump_incident`, `new_event`, 같은 transaction의 `FeaturePorts.handover_refresher` |
| 조사 | F1 `claim_job → prepare_run → run_agent → finalize`; 최초 전이 커밋 후 input_version 확정 |
| 도구 잠금 | Incident → Action/Request → HandoverItem → Job. 도구 저장에서도 같은 순서를 사용 |
| worker | PostgreSQL 전용 connection의 단일 실행 잠금, 연결 유실 시 중단, SIGTERM 정리 |
| 세션 | F1 HMAC token·쿠키·Origin 유지, 교대 고정·매 요청 enabled/site/배정 재검사 추가 |
| 타입 | Python `core/contracts.py`의 세션·Incident/Action/Job enum → `web/src/lib/contracts.ts` 생성 |
| 화면 | F1 `App.vue`·`IncidentDetail.vue` 유지. `actions/resolution/history` slot은 같은 detail/session/refresh 사용 |

`run_once`의 주입 가능한 fake/replay는 시험 경계다. 제품 실행 CLI는 live 또는 maintenance만 제공한다. 단일 worker 보호는 CLI 프로세스에 적용하며, F1의 DB lease fencing은 개별 Job의 최종 반영을 계속 보호한다.

F0 기존 세션 P1에 해당하는 겹친 전환은 F1 화면의 `sessionBusy` 재진입 차단을 유지하고 회귀시험으로 확인했다. 전환 중 이전 사용자 화면을 해제하며 새 session POST가 끝나기 전에 두 번째 POST를 보내지 않는다.

## migration과 세션 전환

유일한 chain은 `0001_f1_foundation → 0002_session_shift`다. 기존 F1의 0001 파일은 변경하지 않았다. 0002는 `session_tokens.shift_occurrence_id`와 FK만 추가하며 Incident·Message·Request·Job을 수정하지 않는다.

0001에서 생성한 기존 세션에는 교대를 추측해 채우지 않는다. NULL을 유지하며 인증 시 재로그인을 요구한다. 새 로그인은 같은 site의 배정을 active 교대 우선, 시작 시각·ID 순으로 선택해 token에 고정한다. 현재 교대 변경만으로 이미 로그인한 사람의 교대를 조용히 변경하지 않는다. 교대 배정 삭제는 403, 만료/disabled/site 불일치/legacy token은 401이다. 유효한 배정 없는 새 로그인은 422이고 이전 세션을 폐기하지 않는다.

**기존 #8 DB에는 이 migration chain을 직접 적용하거나 stamp하지 않는다.** #8의 UUID schema와 F1의 ORM schema는 다르다. 이번 검증은 별도 project/volume을 사용했다. 기존 #8 DB 데이터가 필요한 경우 별도의 데이터 변환 계획과 검증이 필요하며 이번 PR에는 포함하지 않는다. `docker compose down`은 volume을 보존하고, `-v`는 사용하지 않는다.

## F2/F3/F4 연결

- F2는 F1의 `FeaturePorts.action_finalizer(tx, incident_id, run_id, input_version, draft_id, trigger_event_id)`를 구현한다. `tx`는 ORM Session이며 직접 commit·외부 호출을 하지 않는다. `{action_id, created, action_version}`을 반환하고 F1이 다시 검증한다.
- F4는 `FeaturePorts.readiness_evaluator(tx, incident=...)`에 연결한다. Action 완료와 사람의 사건 해결을 분리한다.
- F3는 `FeaturePorts.handover_refresher(tx, incident=..., event=...)`에 연결한다. 기존 인계 항목이 있는데 adapter가 없으면 전체 transaction을 거부한다.
- API의 `create_app(..., ports=...)`와 worker의 `run_once(..., ports=...)` 양쪽에 같은 서비스를 넣어야 한다. 기본 CLI는 아직 비어 있는 FeaturePorts를 사용한다. F2/F3/F4 제품 통합을 성공으로 표시하지 않는다.
- F1 0001에는 actions/approvals·handover·verification의 읽기 projection용 테이블도 이미 있다. 다른 기능의 CREATE TABLE migration을 그대로 붙이지 말고 실제 모델·제약 차이만 후속 revision으로 통합한다.
- F2/F4 패널은 `IncidentDetail.vue` slot에 연결한다. 부모가 한 상세 응답을 전달하고 명령 성공 시 `refresh()`를 호출한다. 새 상세 화면이나 자체 조회 결과를 병렬 권한 근거로 만들지 않는다.
- 생성 타입의 보장 범위는 세션과 세 enum이다. 전체 상세 응답 타입은 현재 F1 `lib/types.ts`이며 F2의 승인·결과 패널 연결 때 추가 필드를 함께 구체화한다. F0의 다른 상세 DTO로 덮어쓰지 않는다.

## 검증

```sh
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements.lock
# TEST_DATABASE_URL은 업무 DB와 분리한 PostgreSQL 시험 DB를 지정한다.
.venv/bin/python -m pytest -q
.venv/bin/python scripts/export_contracts.py --check
npm --prefix apps/web ci
npm --prefix apps/web test
npm --prefix apps/web run build
# 최초 한 번: cd apps/web && npx playwright install chromium
PYTHONPATH=apps/api .venv/bin/python scripts/f1_browser.py
```

시험용 기본 URL과 컨테이너 생성은 [F1 실행 안내](F1_IMPLEMENTATION.md)를 따른다. 시험은 매번 임의 schema를 생성·정리한다. migration 시험은 기존 0001의 업무 데이터/legacy token을 만든 뒤 0002 upgrade·downgrade·upgrade 및 ORM drift를 검사한다. 브라우저 시험은 실제 HTTP·PostgreSQL과 명시적인 fake 모델을 사용한다. 실제 결과는 [TEST_RESULTS](../TEST_RESULTS.md)에 구분한다.

## PR과 남은 범위

새 보강 PR의 base는 `codex/f1-intake-investigation-pr`이다. 따라서 F1 구현 전체를 중복 diff에 넣지 않고 F0 이식분만 검토할 수 있다. 보강 PR을 F1에 통합한 뒤 PR #6의 대상인 `jgoneit`으로 진행하고 main 반영은 별도 통합한다. 이번 작업은 PR 생성까지이며 병합은 수행하지 않는다.

F1 리뷰 중 도구 잠금 순서와 `VITE_API_BASE_URL` 미반영은 이 보강분에서 수정했다. 재조회 실패 시 접수 멱등키 보존, 최신 인계 선택 순서, 모델 입력 크기 제한은 F1 후속 작업이다. 실제 모델·F2/F3/F4 제품 통합·외부 배포·제출은 NOT_RUN이다.
