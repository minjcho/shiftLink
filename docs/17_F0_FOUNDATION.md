# F0 공통 실행 기반과 기능 연결

2026-10-09 · `main`의 `9de625e`에서 분기한 `feature/f0-foundation`. F2 코드는 별도 `minjcho` / PR #5에 유지한다. 이번 사용자 요청으로 민재가 F0 구현을 진행했다.

## 실행 범위

- 실제 PostgreSQL 17, SQLAlchemy, Alembic `0001` migration 및 반복 가능한 기본 seed.
- 네 계정의 서버 세션과 `/api/v1/demo/session`, `/me`, `/equipment`, `/shifts`.
- 서버 보관 세션의 쿠키는 HttpOnly/SameSite=Lax이며, 운영 설정은 Secure를 요구한다. 계정 교체는 이전 토큰을 폐기한다. 저장소에는 토큰의 HMAC만 보관한다.
- 모든 쓰기의 정확한 Origin 검사, 사용자 enabled·사업장·교대 배정 재검사, 공통 오류 envelope.
- 트랜잭션, Incident 선잠금·버전 증가, 완료 응답 재사용·멱등 키 충돌·진행 중 요청 처리.
- Job claim/attempt/lease, stale 입력·만료 worker 차단, 최종 attempt 만료 복구.
- Vue 세 화면 경로·패널 슬롯, 실제 계정·설비·교대 조회, 공통 HTTP client. Python에서 생성한 TypeScript 세션/상태/상세 DTO.

현재 사건 접수·조회, AI 조사, 작업 명령, 교대 인수, 최종 해결 기능은 각 기능 PR에서 연결한다. 화면에 준비 중 상태를 표시하고 가짜 사건·작업·성공 결과를 넣지 않는다. F2 독립 메모리 데모를 다시 추가한 것이 아니다.

## 로컬 부팅

Docker Compose와 Node 24, Python 3.12/3.13을 기준으로 한다. Compose 자체는 Python 3.12와 Node 24 이미지에서 검증했다.

```sh
python3 scripts/setup_env.py
docker compose up --build -d
```

기존 `.env`가 있으면 생성기는 덮어쓰지 않고 종료한다. 별도 설정은 다음처럼 만든다.

```sh
python3 scripts/setup_env.py --output .env.f0
docker compose --env-file .env.f0 up --build -d
```

Web `http://127.0.0.1:5173`, API `http://127.0.0.1:8000`, OpenAPI `/docs`. 네 계정은 화면의 계정 선택 또는 Origin 헤더가 있는 session POST로 시작한다. DB 포트는 외부에 노출하지 않는다. Compose는 로컬 개발용이며, 공개 운영 배포 구성이 아니다.

순서: DB healthy → migrate 완료 → seed 완료 → API healthy → Web/worker. seed는 최초 네 계정·두 설비·두 고정 교대·배정표만 추가하며 사건이나 업무 결과를 만들지 않는다. F1의 SOP·로그·검색 자료 seed는 후속이다.

기존 `.env`를 보존하기 위해 이번 실제 실행은 `docker compose --env-file docs/history/f0-runtime.env -p shiftlink-f0 up --build -d`를 사용했다. 이 파일은 로컬 비밀값이므로 Git에 포함하지 않는다. 종료는 같은 옵션의 `down`을 사용하며, DB 보존을 위해 `-v`를 붙이지 않는다.

## 서버와 migration 연결

`app.core.schema.metadata`가 공유 metadata다. `0001`은 참조 테이블, Incident/Message/Request/Evidence/Event, Job/AgentRun/Draft, 세션·명령 영수증을 만든다. 업무별 Action/Approval·인계·검증 테이블은 각 후속 migration에서 추가한다.

F2 연결 시 `define_action_tables(metadata)`를 등록하고 **0001 다음 migration**에서 actions/approvals와 messages.action_id FK를 추가한다. F1 연결 시 messages.reply_to_request_id의 FK와 출처 자료 테이블을 등록한다. 현재 해당 두 ID 필드는 향후 FK 등록을 위한 UUID다. 기능 서비스는 동일 사건 관계를 항상 검증해야 한다. 이미 적용한 0001을 수정하지 않는다.

F2의 읽기 projection은 공유 ORM으로 교체할 필요가 없다. 다음 adapter를 F2 PR에 추가한다.

1. `core.sessions.current_session`의 서버 principal을 F2 Principal에 투영한다.
2. `core.database.transaction(engine)`의 connection을 F2 ActionTransaction 구현에서 공유한다. F2가 자체 commit하지 않는다.
3. `core.receipts.reserve_command/finish_command`를 연결하고 ReceiptResponse와 F2 CommandResponse를 변환한다. DomainError를 F2 ActionError로 변환해 오류 receipt 처리 계약을 유지한다.
4. Action→Incident→site 범위를 확인한 후 receipt를 먼저 재사용한다. 신규 명령만 Incident, 관련 업무 행(ID 순), 인계 항목, Job 순서로 잠근다.
5. `bump_incident`는 잠근 사건을 트랜잭션당 한 번만 증가시킨다. F2 save_transition에서 이미 계산된 version을 그대로 중복 증가시키지 않는다.
6. 새 승인/결과/근거/이벤트만 append하며 F3 revision hook을 같은 transaction에 둔다. 전체 collection 삭제·교체를 하지 않는다.

receipt는 `(site, actor, key)`와 정규화 method/route/body SHA-256에 묶인다. PostgreSQL transaction advisory lock으로 동시 진행 중 요청에 즉시 409를 반환한다. 완료 응답의 HTTP 상태·body/meta를 그대로 재사용한다. 오류로 transaction이 롤백되면 예약도 사라진다. 인증·객체 범위 검사는 호출자가 먼저 수행해야 하며, 예약한 정상 transaction은 반드시 finish_command까지 수행한다.

## Worker 연결

현재 별도 worker는 singleton PostgreSQL 세션 잠금 아래 **마지막 attempt 만료 복구만 실행**한다. F1 handler가 없어 QUEUED를 claim하거나 모델을 호출하거나 성공 처리하지 않는다. API는 모델 키가 없어도 부팅한다.

F1은 live handler를 등록할 때 `settings.validate_live_worker()`를 먼저 호출한다. `claim_job`은 짧은 Job 잠금 아래 attempt와 token 및 run을 생성한다. 최초 OPEN→INVESTIGATING 전이는 F1이 별도 transaction에서 완료한 후 input_version을 확보해야 한다.

외부 호출은 DB 잠금 밖에서 수행한다. `finish_job(..., apply=callback)`은 Incident를 먼저 잠그고 현재 버전을 검사한다. callback은 관련 업무 행을 잠그고 저장하되 commit/외부 호출을 하지 않는다. 마지막에 Job을 잠그고 현재 attempt/token/미만료 조건을 다시 확인한다. 그동안 lease가 만료됐으면 callback의 변경도 함께 rollback한다. 입력 버전이 바뀌면 callback 없이 SUPERSEDED로 종료한다. 필요 시 새 Job을 중복 없이 등록하는 정책은 F1이 담당한다.

## 공통 화면과 상세 DTO

`/incidents`, `/incidents/:id`, `/handovers/:id?`를 공통 router가 소유한다. `IncidentDetailPage`의 `summary/intake/actions/resolution/history` 슬롯은 동일 detail·session·refresh를 받는다. F1의 상위 조회에서 한 번 가져온 `IncidentDetail`을 패널들에 제공한다. 아직 상세 조회 endpoint가 없으므로 현재 route는 임의 데이터로 패널을 채우지 않는다.

`core/contracts.py`가 세션·enum·상세 DTO 원본이고 `scripts/export_contracts.py`가 `web/src/core/contracts.ts`를 생성한다. `--check`로 일치 여부를 확인한다. 분석·인계·Job/event의 내부 payload는 해당 기능에서 계약 검토 후 구체화한다. 컬렉션은 필수이며 조회 실패를 빈 배열 기본값으로 숨기지 않는다. F2의 필수 패널 입력에 맞춘 Action/Approval/Message/Evidence 필드를 포함한다.

계정 변경 시작 시 이전 actor의 화면을 해제하고 서버 응답으로만 권한 상태를 갱신한다. 공통 client는 불변 body·key 명령을 제공하며 409 버전 충돌을 자동 재전송하지 않는다. F2 기존 client는 연결 후 공통 client로 통합 여부를 검토한다.

## 검증 명령

```sh
uv venv --python 3.13 /tmp/shiftlink-f0-venv
uv pip install --python /tmp/shiftlink-f0-venv/bin/python -r apps/api/requirements-dev.txt
# F0_TEST_DATABASE_URL은 폐기 가능한 실제 PostgreSQL URL을 환경변수로 지정
/tmp/shiftlink-f0-venv/bin/python -m pytest apps/api/tests/core -q
/tmp/shiftlink-f0-venv/bin/python scripts/export_contracts.py --check
cd apps/web
npm ci
npm test
npm run build
```

PostgreSQL URL이 없으면 DB 시험은 SKIP하며 SQLite로 대체하지 않는다. 시험마다 고유한 f0_test_* schema를 만들고 삭제한다. 운영 DB를 시험 대상으로 지정하지 않는다. Compose의 `api`에서 `alembic check`를 실행하면 schema drift를 확인할 수 있다.

실행 결과: Python 35 PASS, Web 7 PASS, 타입/production build PASS, 실제 Compose·네 세션·기본 조회·API 프로세스 재시작 후 세션 보존 PASS. 실제 브라우저 렌더·클릭과 F1/F2/F3/F4 통합은 NOT_RUN이다. 상세는 TEST_RESULTS의 F0 절을 따른다.

구현 시 [SQLAlchemy transaction 문서](https://docs.sqlalchemy.org/en/20/core/connections.html)와 [Alembic migration 생성 문서](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)를 확인했다. 자동 생성 migration은 실제 PostgreSQL에서 upgrade/downgrade/upgrade와 metadata 일치를 검증했다.
