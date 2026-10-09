# F3 구현·검증 인계

작성 기준: 2026-10-09, `jgoneit`에서 분리한 검증 checkout. 목표는 [F3 SPEC](specs/f3-handover/SPEC.md)의 18개 AC다. 구현과 관측한 검증 범위를 정리한다. 최종 Seal 상태·완료 여부는 [F3 PROGRESS](specs/f3-handover/PROGRESS.md)와 실행 기록에서 확인한다.

## 현재 확인 범위

| 구분 | 상태 | 확인한 범위 |
| --- | --- | --- |
| F3 서버 | 구현·직접 시험 PASS | 합성 업무 입력, 실제 FastAPI HTTP·서버 세션·PostgreSQL 시험 53개 |
| F1 서버 회귀 | 직접 시험 PASS | F3 53개와 F1 88개를 함께 실행해 총 141개 통과. 이후 브라우저 선택자 수정은 구현 코드를 변경하지 않음 |
| F3 화면 | 구현·빌드 PASS | S-01 생성, S-03 조회·인수, S-02 인수 요약 연결. `vue-tsc`와 Vite 빌드 |
| 실제 브라우저 AC-1/16/17 | PASS | Chromium `156.0.8078.4`, 합성 업무 입력·실제 Vue/HTTP/PostgreSQL. `ha check` seq 55/56/57에서 각각 통과 |
| Seal baseline/current 판정 | 기록 진행 | 서버 조건과 브라우저 조건에 기록이 있음. 최종 commit의 전체 조건 freshness와 완료 상태는 PROGRESS 및 `ha status`로 확인 |
| 전체 live T8·배포·제출 | NOT_RUN | F1/F2/F4와의 전체 live 전주기는 완료 후 공동 평가 대상 |

`runs.jsonl`의 시작은 seq 1, 작업 위치 입력은 seq 2다. 기록된 baseline은 `b0bcb54c41eeab22c88888e0279992a4bdc2323e`이며 시작 당시 작업 트리는 dirty였다. 사용자 요청으로 총 검증 예산은 100회로 확대되었다. AC-1 통과 뒤 검사 선택자를 명확히 하는 변경 `eb5ad4e14914f4d75b185eac289943f5918bd5c1`이 있었으므로, 개별 과거 PASS만으로 최종 commit의 전체 판정을 대신하지 않는다. 최신 상태는 `ha status docs/specs/f3-handover`, [PROGRESS](specs/f3-handover/PROGRESS.md), [실행 기록](specs/f3-handover/runs.jsonl)을 우선한다.

이전 native Chromium 권한 실패와 환경 block, 이후 사용자 요청·권한 환경 변경에 따른 정상 실행 및 unblock은 [PROGRESS 타임라인](specs/f3-handover/PROGRESS.md#타임라인)에 보존한다. 해당 과거 실패는 현재 브라우저 미실행 상태를 뜻하지 않는다.

## 경로와 연결점

| 경로 | 책임 |
| --- | --- |
| `apps/api/app/features/handovers/schemas.py` | 생성·ACK 입력 DTO, 임의 추가 필드 거부 |
| `apps/api/app/features/handovers/service.py` | 교대·대상 집합, 불변 snapshot, 조회·ACK, 업무 변경 revision hook |
| `apps/api/app/features/handovers/router.py` | 공통 명령·세션 경계를 사용하는 API 등록 |
| `apps/web/src/features/handovers/` | 생성·조회·과거 내용·인수·실패/재확인 표시와 상세 요약 |
| `tests/handovers/` | 격리 PostgreSQL의 HTTP·저장 효과·경합·rollback 시험 |
| `scripts/check_f3.py` | AC별 직접 시험 및 브라우저 필수 검사 진입점 |
| `scripts/f3_browser.py`, `apps/web/tests/handovers.spec.ts` | 실제 Vue·HTTP·DB, API 재시작·DB 조회 실패의 브라우저 검증 절차 |

F3는 공유 `core.models`의 Handover/Item/Revision/Ack와 Incident·Action·Request를 사용한다. 독립 모델이나 migration head를 만들지 않았다. 공통 기반과 F1 코드는 F3 자체의 신규 구현으로 계산하지 않는다.

`register(app, command=command, with_meta=with_meta)`는 `main.create_app`에서 호출한다. F0의 Origin·서버 세션·오류·CommandReceipt를 그대로 이용하며, `create_app`에 ports를 생략하면 기본 F3 hook을 구성한다. 명시적으로 주입된 `FeaturePorts`는 hook 부재까지 그대로 보존하고 router 등록에서 변경하지 않는다. 따라서 호출자가 제공한 경계와 연결 실패 의미를 기본 F3 구현으로 덮어쓰지 않는다. worker CLI도 같은 hook을 `FeaturePorts`에 연결한다.

## HTTP와 상태 의미

| API | 입력·권한 | 결과 |
| --- | --- | --- |
| POST `/api/v1/handovers` | 출발/수신 교대 발생 UUID만 입력. 같은 사업장의 출발 지정 supervisor, 시간상 순서 있는 인접 교대와 양쪽 책임자 배정 확인 | 신규 201, 기존 교대 쌍 재사용 200. `handover_id`, 고정 `cutoff_at`, 서버 지정 수신자와 항목 |
| GET `/api/v1/handovers/{id}` | 지정 출발/수신 supervisor만 조회. 과거 조회는 `item_id`와 `revision`을 함께 지정 | 같은 인계 DTO의 `items`에 현재 항목 또는 선택한 과거 항목. 읽기로 업무 효과를 만들지 않음 |
| POST `/api/v1/handovers/{id}/items/{item_id}/ack` | 지정 수신자, `revision`, `snapshot_token`, `expected_version`, `Idempotency-Key` | 확인한 항목의 ACK와 현재 owner/교대·Incident 버전·유지된 assignee |

생성·갱신 대상은 출발 교대가 소유한 미해결 사건이며 같은 인계에서 이미 인수한 사건도 유지한다. 질문·승인·작업·최종 검증 대기와 `review_required` 사건을 포함한다. 최초 `cutoff_at`은 갱신해도 바꾸지 않는다. 아직 snapshot에 편입하지 않은 새 사건은 `pending_additions`에만 표시하며 item ID·revision·token을 발급하지 않는다. 명시적 갱신으로 편입한 뒤에도 `added_since_cutoff`는 유지된다.

Snapshot은 당시 원문·질문과 답변 연결·모든 Action·승인·결과·Evidence·owner·assignee를 보존한다. COMPLETED/REJECTED Action도 남는다. token은 item/revision/snapshot version/정규화 내용 해시에 결합하며 권한을 대신하지 않는다. 분석은 공개 업무 필드만 포함하고 진단·환경·임의 metadata를 복사하지 않는다. 오래된 분석의 사실을 현재 확정 사실로 승격하지 않는다.

ACK는 owner와 owner_shift를 수신 교대로 옮기고 Incident 버전을 한 번 증가시킨다. Action/assignee·승인·사건 업무 상태·질문 지정자/필수 여부·review 사유는 유지한다. `snapshot N → ACK N+1`을 `ack_applied_version`으로 기록하여 자신의 ACK만으로 revision이나 재인수 의무를 만들지 않는다. 이후 실제 업무 변경은 새 revision을 만들며 재ACK도 이전 owner로 되돌리지 않는다. `current_analysis_is_stale`과 인계 `is_stale`/`requires_ack`는 별도로 제공한다.

## 트랜잭션·실패 경계

기존 항목의 업무 변경자는 Incident를 잠근 같은 트랜잭션에서 `bump_incident(tx, incident, event, ports)`를 호출한다. 이 함수가 변경과 버전을 flush한 뒤 `refresh_handover_items(tx, incident=..., event=...)`를 실행한다. F3 hook은 새 revision을 저장할 뿐 독립 commit이나 추가 Incident 버전 증가를 하지 않는다. hook 실패는 원래 업무 변경과 함께 rollback된다.

필요한 행은 `Incident → Action/Request → HandoverItem → Job`, 종류 안에서는 ID 순서로 잠근다. 같은 교대 쌍의 생성은 별도 transaction advisory lock으로 직렬화한다. 업무 변경 hook은 이 교대 쌍 lock을 얻지 않으므로 Incident 잠금과 순서가 뒤집히지 않는다.

완료 receipt는 인증·site 확인 이후 최신 상태 검사보다 먼저 재사용한다. 다른 키로 같은 revision을 다시 인수해도 현재 권한·버전·상태를 재확인하며 ACK·업무 버전을 중복 생성하지 않는다. stale/위조 token은 `HANDOVER_STALE`, 해결 후 새 ACK는 `INCIDENT_RESOLVED`다. 해결 후 인가된 입력은 `rejected_input`과 거부 receipt만 함께 저장한다. 이를 위해 서비스는 예외 대신 409 응답 tuple을 반환한다. 저장된 거부 입력의 snapshot token은 S-02 공개 이벤트 투영에서 숨긴다.

화면은 표시 중인 snapshot을 자동으로 새 token과 바꿔 ACK하지 않는다. 409·새 revision은 사용자가 내용을 다시 확인해야 한다. DB 조회 실패에는 마지막 성공 시각·실패를 표시하고 ACK를 막는다. 세션 전환은 이전 사용자의 미확정 명령을 재전송하지 않는다. AC-17 실제 브라우저에서 이 경계와 성공 응답 유실 뒤 동일 키·동일 입력 재전송을 확인했다.

## 재현·후속 검증

저장소 루트에서 기존 `.venv`와 web 의존성을 사용한다. 테스트 DB는 시험 전용이어야 하며 해당 계정에 임의 schema 생성·삭제 권한이 필요하다. 기본 연결은 이미 준비된 로컬 시험 DB `127.0.0.1:55432/f1_test`다. 각 시험은 `f3_test_<uuid>`를 만들고 종료 시 그 schema만 삭제한다. `.env`를 읽거나 기존 업무 schema에 시험 데이터를 넣지 않는다.

```sh
PYTHONPATH=apps/api .venv/bin/python -m pytest tests/handovers -q
PYTHONPATH=apps/api .venv/bin/python -m pytest tests/backend tests/handovers -q
npm --prefix apps/web run build
python3 scripts/check_f3.py AC-18
```

다른 시험 전용 DB가 준비되어 있다면 명령 한 번에 연결을 명시할 수 있다. 아래 값은 비밀이 아닌 형식 예시이며 실제 사용자 DB를 가리키지 않는다.

```sh
F3_TEST_DATABASE_URL='postgresql+psycopg://test_user:test_only_password@127.0.0.1:55432/f3_test' PYTHONPATH=apps/api .venv/bin/python -m pytest tests/handovers -q
```

53개 F3 시험은 실제 HTTP와 PostgreSQL에서 유일키·대상 집합·원문 보존·receipt·순서가 통제된 경합·부분 커밋 방지를 확인했다. 기존 F1 추가 메시지 연결과 ACK 뒤 실제 F1 finalizer의 `SUPERSEDED`도 포함한다. 동일 구현의 F1 88개를 함께 실행한 직접 결과는 총 141개 PASS다. 이 직접 실행과 빌드 결과는 별도로 기록된 `ha check` 판정과 구분한다. F2 결과·F4 해결 입력을 준비한 합성 경계 시험은 해당 기능 전체를 구현하거나 전체 live T8을 통과했다는 뜻이 아니다.

AC-1/16/17 검사 진입점은 서버 검사 다음에 실제 브라우저 검사를 반드시 요구한다. 실행한 브라우저 절차는 격리 `f3_browser_<uuid>` schema, 실제 migration·API·Vue와 Chromium `156.0.8078.4`를 사용했다.

| 조건 | 실제 브라우저에서 확인한 내용 | 기록 조회 |
| --- | --- | --- |
| AC-1 | S-01 생성→S-03 단일 항목 ACK→S-02 요약, 동일 Incident/Action/인계 식별자, 새로고침·API 프로세스 재시작 뒤 snapshot/ACK/owner/assignee 유지, 모바일 폭 확인 | `ha log docs/specs/f3-handover 55` |
| AC-16 | 새 원문 뒤 수동 최신 revision 확인·재ACK, 과거 snapshot 보존, cutoff 이후 새 사건의 미편입/편입/ACK 구분과 고정 cutoff | `ha log docs/specs/f3-handover 56` |
| AC-17 | 정상 빈 목록, 실제 PostgreSQL 조회 실패와 복구·ACK 차단, 409 입력 보존과 수동 재확인, 커밋된 ACK 응답 유실 뒤 동일 키 재전송, 세션 변경 시 이전 명령 폐기 | `ha log docs/specs/f3-handover 57` |

다음 명령은 같은 실제 경계를 재현한다. harness는 임의 schema와 자식 서버를 정리하며 증거는 `.cache/f3-browser/<실행 ID>/`에 남긴다.

```sh
python3 scripts/check_f3.py AC-1
python3 scripts/check_f3.py AC-16
python3 scripts/check_f3.py AC-17
```

검증은 원래 `jgoneit`의 병행 작업을 보존하는 격리 checkout에서 진행한다. [PLAN](specs/f3-handover/PLAN.md)의 기준에 따라 baseline과 최종 검증 commit의 current 기록을 확인한다. 아래 명령은 상태 확인·재현 절차다. 이미 유효한 결과를 이유 없이 반복하지 않고 `ha status`가 가리키는 누락·변경 조건만 실행한다.

```sh
ha status docs/specs/f3-handover
ha check docs/specs/f3-handover --baseline
ha check docs/specs/f3-handover
ha check docs/specs/f3-handover EX-1
```

최종 상태와 `ha done` 기록 여부는 [PROGRESS](specs/f3-handover/PROGRESS.md)에서 확인한다. 이 문서의 개별 PASS로 완료 판정을 대신하지 않는다. 실행자 작성 시험의 assurance는 `local`이며 live 모델 호출·전체 T8·배포·제출과 구분한다.
