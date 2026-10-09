# F2 구현과 F0 연결 인계

2026-10-09 · 기준 커밋 `9de625e`에서 시작한 F2 기능 구현. F2/F4 준비 검사 코드와 독립 시험을 추가했다. **F0 앱·DB adapter·실제 세션·F1 live·화면 통합은 아직 없다.** 시험용 메모리 저장소는 production adapter가 아니다.

## 구현 범위

- `apps/api/app/features/actions/`: 후보 확정, 승인·반려·착수·완료, FastAPI router, 명령/응답 DTO, F2 SQLAlchemy 테이블 정의.
- `apps/api/app/features/resolution/readiness.py`: 필수 작업·승인 snapshot/hash·질문 답변·결과/근거·검토 차단을 확인하는 순수 함수. RESOLVE/RETURN API는 미구현.
- `apps/web/src/features/actions/`: Vue 작업 패널, 쿠키 인증 HTTP client, 동일 요청 재시도, 버전 충돌 재검토, 독립 컴포넌트 시험.

F0/F1/F3 파일·로그인·Compose·공유 상세 페이지·migration head는 만들지 않았다. 서비스에서 사용하는 `*View`는 기능의 읽기 projection이며 새로운 공유 ORM 모델이 아니다. 기존 03/04 계약의 endpoint·상태·body는 유지한다. 승인 사유는 UI 계약대로 승인/반려 모두 공백 불가다. 반려는 근거가 사용 불가해져도 가능하지만 승인·착수·완료는 유효 근거를 요구한다.

## F0가 연결할 서버 계약

`ports.py`의 `TransactionFactory`와 `ActionTransaction`을 실제 DB에 구현한다. 기본 구현이나 메모리 fallback은 제공하지 않는다.

| 함수 | 필요한 실제 동작 |
|---|---|
| `transaction()` | 진입 시 DB transaction. 정상 종료 commit, 예외 시 receipt 포함 전체 rollback |
| `assert_action_scope(action_id, site_id)` | Action→Incident의 불변 관계로 사업장 확인. 타 사업장/없는 객체는 404 |
| `reserve_command(principal, key, fingerprint)` | `(site, actor, key)` 예약. 완료 응답은 상태 검사 전에 반환. 해시 충돌/진행 중은 문서의 409 오류 |
| `lock_context(incident_id / action_id)` | Incident를 먼저 잠그고 관련 행을 ID 순으로 잠금. 모든 필수 질문·답변·작업·승인·근거를 빠짐없이 projection으로 반환 |
| `save_transition(before, transition)` | 변경된 Incident/Action 저장, 새 Approval/Message/Evidence/Event만 추가, F3 인계 revision hook 반영. 기존 원문/승인 삭제·덮어쓰기 금지 |
| `append_event(event)` | 해결 이후 인가된 늦은 입력의 `rejected_input` 저장. Incident 버전·snapshot은 불변 |
| `finish_command(principal, key, response)` | HTTP status와 전체 body/meta를 같은 transaction의 receipt에 저장. 재전송에 원응답 사용 |
| `load_draft`, `load_run` | 실제 F1 draft/run 조회. RunView.incident_id는 Job을 조인해 제공 |
| `resolve_assignment(context)` | 설비/교대의 서버 지정 담당자와 서버 기한 정책 적용. 미등록이면 `SHIFT_ASSIGNMENT_MISSING` |
| `stage_proposal(action, event)` | 신규 Action/event와 Incident ACTION_REQUIRED를 staging. **Incident 버전 증가·commit은 하지 않음** |

F0의 모든 형제 기능 writer도 Incident 선잠금 규칙을 사용해야 한다. projection의 collection을 단순 교체하는 방식으로 ORM에 저장하지 않는다. 성공·거부 receipt는 업무 변경과 원자적으로 저장한다. 이미 처리된 동일 명령은 owner가 바뀌거나 사건이 해결돼도 최초 응답을 반환한다. 신규 요청은 현재 권한을 다시 검사한다.

`EvidenceView.applicable`과 `document_approved`는 F0가 출처·설비 적용 범위·SOP 승인 상태에서 계산하는 **서버 전용 값**이다. 브라우저·모델 body를 그대로 매핑하지 않는다. `content_hash`는 보존된 excerpt의 UTF-8 SHA-256 hex다. 과거 사례가 다른 설비라는 이유만으로 직접 관측 사실로 바꾸면 안 된다. 답변 Message에는 실제 `reply_to_request_id`가 필요하다.

승인 payload는 title/scope/assignee/due_at/criteria/revision/evidence를 정규화한다. due_at은 UTC ISO, 근거 ID는 중복 제거·정렬, criteria의 순서는 유지하며 JSON key 정렬·공백 없는 UTF-8 SHA-256을 쓴다. 원문 텍스트는 trim하지 않고 공백뿐인지 검사한다. 승인 뒤 편집 API는 없다.

### Router 조립

```python
application = ActionApplication(f0_transaction_factory)
router = create_actions_router(
    application,
    principal_dependency=f0_authenticated_origin_checked_principal,
    meta_dependency=f0_request_meta,
)
app.include_router(router, prefix="/api/v1")
```

`principal_dependency`는 서버 세션·사용자 enabled·Origin을 검사한 뒤 `Principal(user_id, site_id, role)`을 반환한다. request meta에는 F0의 request_id와 dataset/demo 식별값을 넣는다. body의 actor/site/role은 허용하지 않는다. F0 앱의 공통 `RequestValidationError`/인증 오류 handler가 04 문서의 error envelope를 반환해야 한다. 독립 TestClient는 기본 FastAPI 422를 사용하므로 공통 오류 포맷·Origin·세션 보안은 아직 검증되지 않았다.

### 테이블과 migration

`define_action_tables(f0_metadata)`를 한 번 호출한다. `actions`, `approvals`만 등록하며 공유 `incidents`, `users`, `events`, `agent_runs`, `messages`, `evidence`의 FK를 사용한다. 공유 테이블과 실제 모델의 연결은 F0가 담당한다. Alembic revision/head는 발급하지 않았다.

주요 제약은 generation 고유키, 활성 주 작업 부분 UNIQUE, 승인 revision 고유키, Phase 1 값·양수 version·비어 있지 않은 scope/criteria/evidence, 착수/완료 필수 시각·결과 참조다. 같은 사업장·근거 적용 범위·승인 불변성과 세부 문자열 검사까지 DB 제약만으로 보장한다고 주장하지 않는다.

## F1과 F4 연결

F1은 **현재 input_version과 lease를 검증하는 최종 transaction 내부**에서 기존 `finalize_action_proposal(tx, ...)`을 호출한다. F2는 draft/run/event/근거 관계와 부모 버전을 검사한다. 같은 generation 작업이 이미 있으면 기존 ID를 반환하고 재활성화하지 않는다. 새 작업이면 F1이 부모 버전을 정확히 한 번 증가시키고 F3 hook·Job/Run·최종 lease 검사를 같은 transaction에서 수행한다. 늦은 lease 실패는 F2가 staging한 Action/event까지 rollback해야 한다.

완료 명령은 결과 Message와 completion_report Evidence를 만들고 Action COMPLETED를 적용한 후보 context로 종료 조건을 검사한다. 준비 조건이 충족된 경우에만 PENDING_VERIFICATION으로 바꾼다. 미충족은 정상적인 결과 저장이며 부족 조건 목록을 반환한다. 검사/저장 시스템 예외는 정상 응답으로 숨기지 않고 전체 rollback한다. AI 호출·사건 RESOLVED·해결 snapshot 생성은 하지 않는다.

검사 함수의 입력은 잠금 안에서 구성한 `ActionContext`, 출력은 `Readiness(verification_ready, unmet_requirements)`다. 부족 조건은 `REVIEW_REQUIRED`, `REQUIRED_ACTION_MISSING`, `MULTIPLE_MAIN_ACTIONS`, `ACTION_NOT_COMPLETED`, `APPROVAL_INVALID`, `EVIDENCE_INVALID`, `RESULT_MISSING`, `COMPLETION_EVIDENCE_INVALID`, `REQUIRED_QUESTION_UNANSWERED`, `INCIDENT_RESOLVED`다. F4는 최종 검증 시 현재 owner·version·PENDING_VERIFICATION·notes를 추가 검사해야 한다.

## 공통 상세 화면 연결

상위 IncidentDetailPage가 상세 조회를 한 번 수행하고 `ActionPanel`에 다음 props를 제공한다.

- `action`, `incident`, `session`: 서버 응답과 실제 세션에서 투영. draft를 정식 Action으로 표시하지 않는다.
- `approvals`, `result`: 해당 작업의 승인·결과 원문과 작성자/시각. Action.result_message_id로 결과를 연결한다.
- `evidenceOptions`: 같은 사건에서 접근 가능한 근거의 id/표시 제목.
- `send`: `createActionClient('/api/v1')` 또는 같은 계약의 F0 공통 HTTP adapter.
- `refresh`: 실제 상세 재조회가 끝났을 때 resolve하는 함수. 실패는 reject한다.

패널은 입력 중 버전이 바뀌면 명시적인 재검토를 요구한다. 네트워크 오류/503/응답 파싱 실패는 원래 body/key를 보존한다. 성공 뒤 조회 실패에는 재조회만 제공한다. 세션/사건/작업이 바뀌면 이전 명령과 늦은 응답을 폐기한다. 표시는 권한 보조이며 서버 검사를 대체하지 않는다.

feature 디렉터리의 package.json/lock/tsconfig/vitest 설정은 **독립 검증용**이다. F0 Web이 생기면 동일 Vue 컴포넌트를 공통 build에서 import하고 필요한 의존성을 F0 담당자가 통합한다. 별도 production 앱·라우터는 없다.

## 재현 명령과 남은 검증

저장소 루트에서 실행한다. Python 3.13, Node 24에서 검증한다.

```sh
uv venv --python 3.13 /tmp/shiftlink-f2-venv
uv pip install --python /tmp/shiftlink-f2-venv/bin/python -r apps/api/tests/actions/requirements.txt
/tmp/shiftlink-f2-venv/bin/python -m pytest apps/api/tests/actions -q
cd apps/web/src/features/actions
npm ci
npm run test
npm run typecheck
```

독립 Python 시험은 메모리 UoW로 상태·권한·receipt 계약·오류 시 원자적 호출을 확인한다. 실제 DB 잠금이나 재시작을 입증하지 않는다. UI 시험은 happy-dom 컴포넌트 시험이며 실제 브라우저/서버 전주기 시험이 아니다.

별도 폐기 가능한 PostgreSQL DB의 URL을 로컬 환경변수 `F2_TEST_DATABASE_URL`로 설정하면 `test_postgres.py`의 13개 실제 DB 시험을 실행할 수 있다. 매 시험에서 UUID 이름의 `f2_test_*` schema만 생성·삭제한다. 기존 데이터나 public schema는 수정하지 않는다. FK 대상 F0 테이블은 그 격리 schema의 ID-only fixture이며 실제 F0 adapter 시험과 구분한다. URL이 없으면 SKIP하며 PASS로 계산하지 않는다.

남은 연결: F0 실제 transaction/receipt·session/Origin·공통 상세 DTO·migration 등록, F1 live finalizer, F3 revision hook. 이 연결 후 실제 PostgreSQL 경합·부분 저장 실패·새로고침/프로세스 재시작·브라우저 E2E·L1b를 실행해야 F2 전체를 DONE으로 바꿀 수 있다.


임시 브라우저 데모는 사용자 요청으로 제거했다. 이 기능 묶음에는 별도 실행 앱이나 메모리 API 서버가 없으며, 위 독립 시험과 F0 연결 계약을 제공한다.
