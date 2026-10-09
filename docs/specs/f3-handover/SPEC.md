# F3 교대 인계·인수와 변경 재확인

Status: Ready

## 목표

출발 교대 책임자가 자신이 넘길 미해결 사건 전체를 인계하고, 지정 수신 책임자가 실제로 확인한 사건별 내용을 인수한다. 인수 후에도 같은 사건·작업·원문을 유지하며, 새로운 업무 정보가 들어오면 변경된 내용만 새 revision으로 재확인할 수 있다. 화면·API·PostgreSQL을 연결한 F3 전체가 대상이다.

이 문서는 사용자의 “기능별 책임에서 F3에 해당하는 모든 작업들에 대해 Task를 나눠서 진행” 요청으로 작성한 신규 기능 목표 명세다. [README](../../../README.md), [PROGRESS](../../../PROGRESS.md), [개발 계획](../../08_BUILD_PLAN.md)에 있는 F3 책임을 구체화한다. 작은 수정이 아니다. 원본은 `worktree-brave-river-ff80`의 `docs/specs/f3-handover/SPEC.md`이며, 사용자의 현재 브랜치 반영 요청에 따라 [F1 명세](../f1-intake-investigation/SPEC.md)와 공유 계약을 맞췄다. 현재 저장소에는 개발 문서만 있고 앱·DB schema·시험 runner는 아직 없다. 문서 상태는 구현 완료나 런타임 검증 결과를 뜻하지 않는다.

## 범위와 제외 범위

포함 범위는 FR-09 / AC-F3.1~4, 교대 범위·대상 집합, Handover와 항목의 불변 revision, 생성·조회·항목 ACK API, 책임 이전·재ACK, 권한·멱등성·경합·실패 보존이다. 화면은 S-01의 생성 진입점, S-03 인수 화면, S-02의 인수 요약과 링크를 포함한다. F3 담당은 각 결과의 화면·API·데이터·권한·시험을 함께 책임진다.

기존 계약 중 원문·근거 보존, 현재 owner 권한, 고정 assignee, 미해결/해결 상태 구분, review_required 차단, 공통 세션·receipt·버전 규칙은 유지한다. 인수는 작업 완료·최종 해결·Agent 성공을 대신하지 않는다.

F0 전체 구축, F1 Agent/질문 생성, F2 작업 명령, F4 종료 서비스의 신규 구현은 별도 기능이다. F3에 필요한 공통 계약 연결은 포함하지만 해당 기능 전체의 완료를 F3의 완료 기준으로 삼지 않는다. 독립 합성 자료로 F3 입력 상태를 준비할 수 있어야 하며, F3 화면→실제 API→실제 DB 경계 자체는 대체 응답으로 대신하지 않는다.

추가 AI 인계 문장, 자동 알림, 별도 대시보드, 일괄 인수, 임의 owner/assignee 변경, 복수 주 작업, 반려 해제·generation 2, 해결 사건 재개, 배포·발표·외부 제출은 포함하지 않는다.

## 사용 시나리오

| 종류 | 시나리오 | 조건 |
| --- | --- | --- |
| 흐름 | 출발 책임자가 S-01에서 허용 교대 쌍으로 인계를 만들고 S-03에서 질문·승인·작업·검증 대기 사건 전체와 근거를 확인한다. | AC-1, AC-2, AC-3, AC-4, AC-5, AC-16 |
| 흐름 | 지정 수신자가 항목 하나를 인수하고 새로고침한다. 그 사건의 owner/owner_shift만 이전되며 동일 Action의 assignee와 미해결 상태가 남는다. | AC-1, AC-7, AC-8, AC-16 |
| 흐름 | 인수 뒤 추가 원문이 들어온다. 이전 snapshot과 새 내용을 구분하고 새 revision을 다시 확인해 인수한다. | AC-6, AC-9, AC-15 |
| 흐름 | 최초 인계 이후 새 사건이 생긴다. 갱신 후에도 최초 cutoff와 ‘추가됨’ 표시를 유지하고 새 항목은 별도로 인수한다. | AC-3, AC-10, AC-16 |
| 경계 | 같은 인계를 동시에 만들거나 성공 ACK 응답이 유실된다. 동일 객체·receipt로 수렴하고 효과가 중복되지 않는다. | AC-4, AC-12, AC-13 |
| 경계 | 다른 책임자·사업장·교대 또는 위조 token으로 생성·조회·ACK를 시도한다. 내용 유출과 책임 변경이 없다. | AC-2, AC-11 |
| 경계 | 오래된 revision을 ACK하거나 ACK와 새 원문·결과·해결이 경합한다. 최신 내용만 인수되며 부분 반영은 없다. | AC-9, AC-13, AC-14 |
| 경계 | 모델이 중단되어도 DB 기본 인계는 사용한다. DB 조회가 실패하면 성공한 빈 목록으로 표시하지 않고 ACK를 막는다. | AC-17, AC-18 |
| 유지 | REJECT/RETURN으로 후속 검토가 필요한 사건도 인계되며 사유·완료 Action·review_required는 그대로 남는다. | AC-3, AC-15 |
| 유지 | 과거 revision·원문·승인·결과·해결 snapshot은 새 인수나 조회 때문에 덮어쓰이지 않는다. | AC-5, AC-6, AC-14, AC-15 |
| 유지 | S-02는 공유 조회·셸을 사용하고 ACK 뒤 현재 owner와 같은 assignee를 표시한다. 이전 owner의 업무 권한을 되살리지 않는다. | AC-1, AC-15, AC-16 |

## 기능 간 계약과 제약

### 데이터와 서버 경계

- 기준은 [결정 D01~D07](../../11_DECISIONS_AND_SOURCES.md) → [도메인](../../03_DOMAIN_MODEL.md) → [API](../../04_API_CONTRACT.md) 순이다. 아래 사용자 결정은 기존에 미정이었던 cutoff 갱신 의미를 보완한다.
- F0에서 서버 principal, site/교대 배정, 공통 오류·CommandReceipt, 트랜잭션·잠금·버전 계약과 공유 상세 셸을 제공한다. 공유 enum·DTO·migration head·셸은 한 통합자가 조정한다. F3는 기능별 schema·서비스·패널과 필요한 계약 확장을 소유한다.
- PostgreSQL·SQLAlchemy·Alembic, Vue 3 TypeScript·FastAPI/Pydantic을 기준으로 한다. 예정 경로는 `apps/api/app/features/handovers/`, `apps/web/src/features/handovers/`이며 현재 존재하는 코드 경로가 아니다.
- Handover의 고유키는 `(site_id, from_shift_occurrence_id, to_shift_occurrence_id)`, 항목은 `(handover_id, incident_id)`, revision과 ACK는 각각 `(item_id, revision)`이다. 공개 snapshot은 불변이고 ACK 기록은 별도다.
- snapshot token은 item ID·revision·snapshot_version·표시 내용의 정규화 해시에 묶인다. token을 알고 있다는 이유로 세션 권한을 얻지 않는다. 과거 snapshot과 현재 업무 상태는 분리해서 제공한다.
- `cutoff_at`은 최초 생성 시각으로 고정한다. 이후 갱신에서도 기준을 바꾸지 않는다. 기준 이후 추가 사건의 `added_since_cutoff`와 내용 revision/ACK 상태는 별도 의미다. 같은 요청의 재시도뿐 아니라 새 키의 재생성도 cutoff를 바꾸지 않는다.
- 새 업무 정보는 D01대로 Incident.version을 트랜잭션당 한 번 증가시킨다. 자기 ACK의 `ack_applied_version`만으로 stale을 만들지 않는다. 원문 등 후속 정보는 새 revision과 재확인을 요구한다.
- F3도 공통 `Incident → Action/Request → Handover item → Job` 잠금 순서와 종류 내 ID 정렬을 따른다. 업무 효과·이벤트·필요 revision·receipt는 원자적으로 확정한다. 외부 모델 호출은 F3 기본 인계의 선행조건이 아니다.

### API와 화면 연결

| 경계 | 입력과 결과 | 유지할 의미 |
| --- | --- | --- |
| POST `/api/v1/handovers` | 출발/수신 교대 발생 ID. 신규 201, 기존 200. handover_id·고정 cutoff_at·receiver_id·items | 수신자와 대상 사건은 서버 결정. 동일 교대 쌍은 같은 객체 |
| GET `/api/v1/handovers/{id}` | 현재 항목과 cutoff 이후 추가 대상. `item_id`·`revision`으로 과거 내용 조회 | 읽기만으로 인수·책임 이전하지 않음. 과거 내용과 최신 revision/stale/해결 여부 구분 |
| POST `/api/v1/handovers/{id}/items/{item_id}/ack` | revision·snapshot_token·expected_version, Idempotency-Key | expected_version은 snapshot의 Incident 버전. 지정 수신자만 최신 내용 인수 |
| S-01 → S-03 | 허용 교대 쌍 선택 → 실제 생성 응답의 인계 ID | client에서 receiver·대상 목록을 만들지 않음 |
| S-03 → S-02 | 실제 Incident 링크와 인수 요약, ACK 성공 후 상위 상세 갱신 | 단일 조회·셸 공유, 다른 패널의 상태를 직접 조작하지 않음 |
| F3 → F4/F1/F2 | 현재 owner/owner_shift, 사건 버전, snapshot/ACK 적용 버전, 수신자, 변하지 않은 Action/assignee | 다음 업무 명령의 권한·최신성 판단은 현재 서버 값 사용 |

항목 응답의 최소 필드는 `id, incident_id, revision, snapshot_version, snapshot_token, snapshot, ack_status, ack_applied_version, is_stale`다. ACK 결과는 `item_id, revision, ack_status, snapshot_version, ack_applied_version, incident_version, owner_id, assignee_id, acknowledged_by, acknowledged_at`을 제공한다. 부재한 작업 담당자는 공통 unknown/null 계약을 따른다.

공유 DTO에는 과거 snapshot의 owner와 현재 owner/교대·현재 사건 버전·해결 여부·최신 revision·추가 여부를 구분할 정보가 있어야 한다. S-02 `handover` 요약에도 실제 인계/항목 식별자와 링크·인수 최신성이 필요하다. 세부 필드명, 차이 계산 위치, 내부 서비스명은 구현 선택이며 별도 endpoint나 업무 상태를 늘리지 않는다.

S-02의 동일 site Incident 조회 권한은 인계 전체의 지정 출발/수신 책임자 조회 권한과 다르다. 인수 요약은 해당 사용자가 읽을 수 있는 사건 정보만 제공하며 비참여자에게 제한된 snapshot·token·다른 항목 내용을 노출하지 않는다. 링크를 제공해도 실제 현재·과거 인계 조회의 권한 검사를 대신하지 못한다. 출발 책임자가 인계 이력을 읽을 수 있다는 사실과, ACK 뒤 F1의 추가 진단·재시도에 필요한 현재 owner 권한도 구별한다.

### F1과 공유하는 연결 계약

[F1 SPEC](../f1-intake-investigation/SPEC.md)과 [F1 Task](../f1-intake-investigation/TASKS.md)의 접수·질문·답변 결과를 같은 Incident/Request로 사용한다. 아래 조건 ID는 각 목표 안에서만 고유하며, `F1 AC-n`과 이 문서의 `AC-n`은 별개다.

| 연결 상황 | 두 기능이 보존할 결과 | 조건 연결 |
| --- | --- | --- |
| 기존 인계 항목의 새 원문·정정·질문·답변·업무 상태 | F1의 수용된 업무 효과·버전·이벤트·필요 Job/receipt와 F0/F3의 관련 revision 갱신은 같은 업무 트랜잭션에 참여한다. 최초 조사 상태 전이·Action 확정·검증 준비도 적용 대상이다. 이전 snapshot은 불변이고 최신 내용·새 revision·재확인 필요가 함께 반영된다. 갱신 실패를 부분 성공으로 만들지 않는다. | F1 AC-5/10/20/21/23/25/34 ↔ AC-9/13 |
| 최초 cutoff 이후 새 Incident | 원문·사건 접수 자체는 F1에 저장되고 F3 조회에서는 서버 범위의 추가 대상으로 구분한다. 기존 항목의 내용 변경과 달리 아직 항목이 없는 새 사건은 명시적 인계 갱신으로 다음 snapshot에 편입한다. 최초 cutoff와 추가 표시는 편입·ACK 뒤에도 유지한다. | F1 AC-1/8 ↔ AC-3/10 |
| 미응답 질문을 가진 사건의 ACK | Phase 1 질문은 모두 필수다. ACK는 Request ID·target_user_id·is_required·OPEN/ANSWERED·답변 연결을 바꾸지 않는다. 미응답 질문이 있어도 미해결 사건을 인수할 수 있으며, 인수 후에도 질문 대기와 해결 준비 차단은 남는다. 새 owner에게 대리 답변 권한이 생기지 않는다. | F1 AC-19/21/25/30 ↔ AC-3/5/7/15 |
| ACK와 진행 중 AI 조사 경합 | ACK의 Incident.version 증가는 F1의 새 업무 버전이다. 자기 ACK로 인계가 stale이 되지 않는 예외를 Agent input_version 검사에 적용하지 않는다. 현재 lease를 가진 이전 버전 run은 SUPERSEDED가 되고 질문·Action·최신 analysis를 덮어쓰지 못한다. | F1 AC-26/27 ↔ AC-7/8/18 |
| 분석과 인계의 최신성 표시 | `analysis.is_stale`은 analysis.base_version과 현재 Incident.version의 비교다. 인계 최신성은 revision/snapshot_version/ack_applied_version과 후속 업무 변경으로 판단한다. 자기 ACK 후 ‘인수 완료’와 ‘이전 정보 분석’이 함께 표시될 수 있으며 오래된 분석만으로 재ACK를 요구하지 않는다. | F1 AC-5/30 ↔ AC-5/8/16/18 |
| 인수 후 F1 명령·진단 권한 | 새 Job 재시도 명령과 owner 전용 추가 run 진단은 현재 서버 owner 권한을 따른다. 제보·추가 원문·질문 답변은 각 API의 기존 역할·지정자 권한을 유지한다. 기존 완료 receipt 재사용은 공통 규칙대로 먼저 처리한다. 질문 지정자와 Action assignee는 유지된다. 인계 조회 권한으로 owner 전용 run 진단 권한을 대신하지 않는다. | F1 AC-3/9/21/29/32 ↔ AC-11/12/15 |

F1이 업무 입력의 수용을, F3가 인계 내용·revision 규칙을 소유하며 F0가 공통 트랜잭션/DTO/셸을 통합한다. F3를 F1의 별도 Agent 실행기로 만들지 않는다. 실제 F1과 연결한 경합 확인은 완료 후 공동 평가로 두되, F3의 원자성·권한·버전 출력은 이 목표의 필수 조건이다.

## 결정과 근거

| 결정 | 이유 | 출처 |
| --- | --- | --- |
| F3 전체를 하나의 목표로 묶고 아래 W1~W8의 결과 단위로 분해한다. | 화면·API·DB·권한·시험을 분리 담당으로 고정하지 않고 F3 수용 조건 전체를 추적한다. | 사용자 요청, README 기능별 책임, docs/08_BUILD_PLAN.md §2·4, 이번 명세의 작업 분해 제안 |
| 서버가 허용 교대 쌍·미해결 대상·수신자를 결정하고 교대 쌍 객체를 재사용한다. | 타 사업장/교대 포함과 중복 인계를 방지한다. | docs/11_DECISIONS_AND_SOURCES.md D04, docs/03_DOMAIN_MODEL.md §7 |
| 최초 cutoff를 유지하고 이후 추가 사건 표시는 snapshot 편입·ACK 후에도 유지한다. | 최초 인계 이후 발생한 사건을 계속 구별하되, 추가 여부를 미인수 여부와 혼동하지 않는다. | 사용자의 답변: “최초 생성 시각 유지 (추천): 이후 들어온 사건을 계속 ‘추가됨’으로 구분합니다.” |
| 불변 revision과 별도 ACK 적용 버전으로 확인한 내용과 현재 책임을 구별한다. | 이미 본 내용을 바꾸거나 자기 ACK로 즉시 재인수를 요구하지 않는다. | docs/03_DOMAIN_MODEL.md §4.5·7, docs/04_API_CONTRACT.md §7 |
| ACK는 owner와 owner_shift만 이전하고 Action·사건 상태·review_required를 유지한다. | 인수와 수행·해결·반려 해제를 구별한다. | docs/11_DECISIONS_AND_SOURCES.md D01·D02·D04, docs/03_DOMAIN_MODEL.md INV-03·11 |
| 동일 완료 receipt를 상태·버전 검사보다 먼저 반환하고 신규 명령은 원자적으로 검증한다. | 응답 유실 후 중복 효과와 해결 이후 성공 응답의 변질을 방지한다. | docs/11_DECISIONS_AND_SOURCES.md D05, docs/03_DOMAIN_MODEL.md §5, docs/04_API_CONTRACT.md §1 |
| AI에 의존하지 않는 기본 인계, 기존 세 화면 연결, 실제 UI/API/DB 경계를 완료 조건에 둔다. | F3 자체를 독립적으로 사용할 수 있고 화면·서버의 불일치가 드러난다. | docs/02_FUNCTIONAL_SPEC.md FR-09, docs/06_UI_SPEC.md §8, docs/07_TEST_PLAN.md T7f·F3 gate |
| 전체 live 전주기·배포·제출은 아래의 완료 후 공동 평가 항목으로 둔다. | 다른 기능 전체 완료·계정 권한·실제 접수를 F3 단독의 완료와 섞지 않는다. F3의 실제 경계와 권한/버전 출력은 필수 조건으로 남긴다. | docs/08_BUILD_PLAN.md §2·5, docs/07_TEST_PLAN.md F3/F5 gate, docs/12_CODEX_TASKS.md §6·8·9 |
| F1의 Phase 1 필수 질문 정책과 지정 응답자를 인수 후에도 유지한다. | 사건 책임 이전이 질문 답변·필수 여부·해결 준비를 대신하지 않게 한다. | [F1 결정 및 AC-19/21/25/30](../f1-intake-investigation/SPEC.md), 사용자 답변 “Phase 1 질문은 모두 필수로 설정 (권장)” |
| F1의 수용된 원문·질문·답변과 관련 인계 revision을 공통 트랜잭션으로 연결한다. | 새 내용은 저장됐지만 인계가 이전 내용으로 남는 부분 반영을 막는다. | [F1 AC-5/20/21](../f1-intake-investigation/SPEC.md), docs/03_DOMAIN_MODEL.md §5·7 |
| 인계 최신성과 F1 분석/input_version 최신성을 별도로 판단한다. | 자기 ACK의 정상 인수 상태를 유지하면서 오래된 AI 결과도 차단한다. | [F1 AC-26/27/30](../f1-intake-investigation/SPEC.md), docs/03_DOMAIN_MODEL.md §4.2·6·7 |

## Acceptance Criteria

- **AC-1** 출발 책임자의 화면상 생성부터 지정 수신자의 항목 ACK, 실제 API·PostgreSQL 저장, S-02/S-03 재조회까지 같은 Handover·Incident·Action 식별자로 이어진다. 브라우저 새로고침과 API 프로세스 재시작 뒤에도 snapshot·ACK·현재 owner·유지된 assignee가 동일하다. F3 입력은 합성 자료로 준비할 수 있으나 F3 경계의 결과를 UI mock이나 메모리 데이터로 대체하지 않는다.
- **AC-2** 지정 출발 supervisor만 같은 사업장의 순서 있는 허용 인접 교대 쌍으로 인계를 만든다. 잘못된 사업장·역순·비인접 교대·미배정 수신자·무권한 생성은 거부되며 불완전한 Handover가 남지 않는다. 수신자는 서버 담당표에서 정해진다.
- **AC-3** 명시적 생성·갱신 시점에 서버가 정한 출발 교대 소유·범위의 미해결 대상과 그 snapshot에 포함된 인계 항목 집합이 일치한다. 질문·승인·작업·최종 검증 대기 및 후속 검토 필요 사건을 빠뜨리지 않는다. 같은 인계에서 이미 ACK한 미해결 사건은 재생성 후에도 남고, 다른 교대·사업장 사건은 섞이지 않는다. 해결된 과거 항목은 이력에서 읽히되 현재 ACK 대상이 아니다. 이후 조회된 새 대상 중 아직 snapshot에 편입하지 않은 사건은 AC-10의 추가 대상으로 구분하며 이미 인수 가능한 revision이 있다고 표시하지 않는다.
- **AC-4** 동일 교대 쌍을 같은 키·다른 키·동시 요청으로 생성해도 Handover 하나와 사건별 항목 하나로 수렴한다. 새 객체는 201, 기존 객체 재사용은 200이며, 같은 완료 receipt 재생은 최초 상태 코드를 유지한다. 내용 변화가 없으면 revision을 늘리지 않는다.
- **AC-5** 표시된 revision은 사건 상태·버전·원문·확정 사실·미응답 질문·현재 Action의 상태와 결과/근거·남은 업무·owner·assignee·Evidence의 당시 내용을 보존한다. 질문에는 실제 Request ID·목적·지정 대상·필수 여부·답변 상태/연결이 포함되며 Phase 1 질문은 모두 필수다. 검증 대기의 COMPLETED Action과 후속 검토 상태의 REJECTED Action도 당시 작업 내용에서 제외하지 않는다. 사실에는 근거가 연결되고 사람 진술·기록·가설을 구별하며 AI 설명이 원문을 대체하지 않는다. analysis를 포함할 때 기준 버전과 최신성을 함께 구별하고 오래된 분석을 현재 확인 사실로 승격하지 않는다. 이후 업무 변경·조회·ACK·재생성으로 이전 snapshot과 token이 바뀌지 않는다.
- **AC-6** 허용된 책임자는 현재 revision과 지정한 과거 revision을 재조회할 수 있다. 과거 snapshot의 당시 owner와 별도로 현재 owner·최신 revision·stale·해결 여부가 구별되며, 조회 자체로 업무 버전·ACK·책임이 바뀌지 않는다.
- **AC-7** 지정 수신 supervisor가 최신 revision·유효 token·일치하는 Incident 버전으로 ACK하면 해당 항목의 ACK, owner/owner_shift 이전, Incident.version의 한 번 증가, 이벤트·receipt가 함께 남는다. Action ID·assignee·승인 내용·Action 상태·Incident 상태와 Request의 지정 대상·필수 여부·답변 상태는 그대로다. 한 항목 ACK가 다른 항목을 인수하거나 미응답 질문을 답변 완료로 만들지 않는다.
- **AC-8** snapshot_version=N의 ACK 이후 Incident.version 및 ack_applied_version은 N+1이고 snapshot revision은 그대로다. 다른 업무 변경이 없다면 조회·인계 재생성·새로고침 후에도 ACKNOWLEDGED이며 자기 ACK만으로 stale이나 추가 인수 필요가 되지 않는다.
- **AC-9** 미인수 또는 인수된 사건에 새 업무 정보가 들어오면 상태명이 같더라도 이전 내용에 대한 신규 ACK는 `409 HANDOVER_STALE`로 거부되고 owner·ACK 효과가 없다. 동일 완료 receipt의 재전송은 AC-12대로 최초 응답을 재생한다. 기존 인계 항목에 대한 F1의 새 원문·정정·질문·답변과 최초 조사 상태 전이·Action 확정·검증 준비는 그 업무 변경과 같은 공통 트랜잭션에서 새 불변 revision·최신 내용·재확인 필요로 연결된다. 미인수 항목의 변경도 즉시 반영되며 조회나 수동 재생성 때까지 낡은 내용을 최신으로 유지하지 않는다. 인수 후 N+2의 새 내용을 재ACK하면 같은 수신 owner를 재확인하며 이전 owner로 돌아가지 않고 과거 revision·ACK·assignee를 보존한다. 새 사건의 첫 snapshot 편입은 AC-10과 구별한다.
- **AC-10** cutoff 이후 새 대상은 최신 조회에서 ‘추가됨’으로 보이고 다음 snapshot에 포함된다. 모든 갱신에서 cutoff는 최초 생성 시각을 유지하며, 새 항목이 snapshot에 들어가거나 ACK되어도 추가 표시는 남는다. 추가됐다는 표시나 과거 다른 항목의 ACK를 근거로 새 항목을 인수한 것으로 처리하지 않는다.
- **AC-11** 생성·조회·과거 조회·ACK는 서버 세션과 site/지정 책임자 관계로 권한을 판단한다. 유효한 세션이 없는 요청은 401로, 공통 허용 Origin 검증을 통과하지 못한 생성·ACK는 공통 오류 계약으로 거부되며 업무 효과가 없다. 다른 수신자, 다른 인계에 속한 item, 위조 token, 임의 actor/site/role/owner/assignee/receiver/대상 사건 body로 권한을 얻지 못한다. 범위 밖 객체는 404 등 공통 오류 계약으로 처리하며 본문·현재 버전·receipt가 유출되지 않는다. 동일 site의 S-02 상세 조회에 인계 요약이 포함돼도 비참여자에게 제한된 snapshot·token·타 항목 내용은 노출되지 않는다. 인계·과거 snapshot 조회는 F1 owner 전용 실행 진단의 우회 경로가 아니며 비밀·전체 환경·내부 추론을 포함하지 않는다.
- **AC-12** 생성과 ACK는 공통 멱등 키를 요구한다. 인증·site 확인 후 동일 actor/site/key/method/route/body의 완료 요청은 현재 상태·버전 검사보다 먼저 최초 HTTP 응답과 `Idempotent-Replayed: true`를 돌려주며 효과·버전·이벤트를 추가하지 않는다. 같은 키의 다른 입력은 `409 IDEMPOTENCY_CONFLICT`, 진행 중 같은 키는 `409 COMMAND_IN_PROGRESS`다. 다른 actor/site는 타인의 응답을 재사용하지 않는다. 다른 키로 이미 ACK한 같은 revision을 다시 요청해도 두 번째 ACK·버전 증가가 생기지 않는다. 새 키는 receipt 재생이 아니라 신규 명령이므로 현재 권한·상태·버전 및 해결 후 거부 규칙을 모두 적용한다.
- **AC-13** 동시 생성·ACK·새 정보·결과·해결 간 경합에서 각 고유키와 현재 권한/버전이 유지된다. 실패한 신규 업무 명령은 owner만 이전하거나 ACK만 남기는 부분 반영이 없다. 기존 항목의 F1 업무 변경과 F3 revision 갱신도 한쪽만 성공하지 않는다. 단, 해결 후 인가된 거부 입력과 receipt 보존은 AC-14에 따른다.
- **AC-14** 해결이 먼저 확정된 사건의 새 ACK는 409로 거부되고 인가된 입력은 rejected_input과 receipt로 한 번 보존된다. owner·Incident.version·해결 snapshot은 바뀌지 않는다. 이전 성공 ACK의 같은 receipt는 여전히 성공 응답을 재생한다. ACK가 먼저 확정되면 다음 업무 판단에 사용할 owner와 증가한 사건 버전이 조회되며 이전 owner/버전으로 해결한 것으로 기록되지 않는다.
- **AC-15** 인수·재인수는 원문·질문/답변·Action/승인/결과·근거·반려 사유를 보존한다. 필수 OPEN 질문이 있는 사건도 인수할 수 있지만 Request.target_user_id/is_required/status/response_message_id는 변하지 않아 질문 대기와 해결 준비 차단이 계속된다. 인수한 owner에게 타인의 질문을 대신 답할 권한이 생기지 않는다. review_required 사건도 인계되지만 플래그를 해제하거나 작업·해결을 재개하지 않는다. F2가 사용할 동일 assignee/Action과 F4가 사용할 현재 owner가 유지되며 F3가 승인·완료·최종 검증을 대신 기록하지 않는다.
- **AC-16** S-01의 생성 진입점, S-03의 실제 인계 ID·교대·최초 기준 시각·수신자·최종 조회 시각, 항목별 사건/설비/상태/질문/작업/owner/assignee/revision/근거·상세 링크가 실제 조회와 일치한다. 정상 인수·미인수·변경 후 재인수·추가됨·해결된 과거 항목을 구분하고 변경 내용을 확인할 수 있다. S-02는 같은 상세 셸에서 인수 요약·링크를 제공한다. 인수 완료와 사건 해결은 다른 표시다. F1 analysis의 갱신 필요와 F3 인계의 재인수 필요는 별도로 표시하며 정상 ACK 직후 이전 분석만으로 재ACK를 요구하지 않는다.
- **AC-17** 로딩·성공한 빈 목록·조회 실패·오래된 마지막 성공 화면을 구분한다. DB 조회 실패 중 ACK는 차단되고 마지막 내용에는 실패와 조회 시각이 표시된다. 409에서는 확인 중인 내용/입력을 보존하고 최신 revision 재확인 후 사람이 새 명령을 내도록 한다. 버전/token만 교체한 자동 ACK는 없다. 세션 전환으로 이전 사용자의 명령을 재전송하지 않는다. label·키보드 조작·연결된 오류·제출 중 안내를 제공하고 한 항목 성공을 전체 성공으로 표시하지 않는다.
- **AC-18** 모델이 중단·실패하거나 추가 AI 설명이 없어도 저장된 사건으로 기본 목록·snapshot·허용된 ACK를 사용할 수 있다. 조회·receipt 재생·analysis만의 갱신은 Incident 업무 버전을 올리지 않고 새 인수 의무를 만들지 않는다. 정상 ACK의 버전 증가와 이벤트는 F1이 이전 input_version을 식별할 수 있게 유지된다. 자기 ACK가 인계를 stale로 만들지 않는 AC-8의 예외는 F1 finalizer의 버전 검사를 면제하지 않는다. ACK 전 버전으로 조사한 결과는 F1의 현재 lease 검사 아래 SUPERSEDED 처리 대상이며 질문·Action·최신 analysis를 덮어쓰지 못한다. ACK가 Agent의 성공이나 새로운 Action 생성으로 기록되지 않는다.

## 작업 분해 제안

각 W는 사용자가 요청한 Task에 대응하는 결과 단위다. 의존은 필요한 결과 관계이며 일정·착수 순서·실행 상태가 아니다. 실제 구현자가 내부 작업을 더 나누거나 합칠 수 있다.

표의 `—`는 다른 W에 대한 선행 의존이 없다는 뜻이다. 실제 F0 세션·교대 배정·PostgreSQL·공통 명령 기반·공유 셸은 F3가 연결할 공통 전제이며 현재 저장소에는 없다. F0 전체 기능의 완료 여부와 별개로 필요한 실제 경계가 사용 가능해야 한다. 이 기반이 없으면 합성 입력이나 UI mock만으로 AC-1을 완료했다고 할 수 없다.

| ID | 결과 | 조건 | 의존 |
| --- | --- | --- | --- |
| W1 | 허용 교대 쌍의 서버 대상 집합과 단일 인계 생성·재사용 | AC-2, AC-3, AC-4 | — |
| W2 | 당시 내용을 보존하는 snapshot/token과 현재·과거 revision 조회 | AC-5, AC-6 | W1 |
| W3 | 항목별 ACK에 따른 owner/owner_shift 이전과 자기 ACK 최신성 유지 | AC-7, AC-8 | W2 |
| W4 | 새 정보 재ACK·추가 사건·고정 cutoff를 일관되게 보여주는 인계 갱신 | AC-3, AC-9, AC-10 | W2, W3 |
| W5 | 생성·조회·ACK의 권한 격리, 중복 효과 방지, 원자적 실패 | AC-11, AC-12, AC-13 | W1, W3 |
| W6 | 해결 경합·반려 상태·다른 기능의 기록을 보존하는 F3 업무 경계 | AC-14, AC-15, AC-18 | W3, W4, W5 |
| W7 | S-01 생성·S-03 인수·S-02 요약과 오류/재확인을 실제 응답에 연결한 화면 | AC-16, AC-17 | W1, W2, W3, W4, W5 |
| W8 | 같은 사건의 화면→API→PostgreSQL 인계·인수와 재시작 후 재조회 | AC-1 | W6, W7 |

## 관련 맥락과 수용 조건 추적

| 기존 계약·시험 | 이 목표의 조건 | 연결 결과 |
| --- | --- | --- |
| FR-09 / AC-F3.1, T4e, T12f | AC-3, AC-5 | W1, W2 |
| AC-F3.2, T4b·c, T8의 미해결 ACK 구간 | AC-1, AC-7, AC-8, AC-16 | W3, W7, W8 |
| AC-F3.3, T4a·f, T12a·b·c·e | AC-2, AC-4, AC-9, AC-10, AC-11, AC-14 | W1, W4, W5, W6 |
| AC-F3.4, T4d, T12d | AC-5, AC-6, AC-9, AC-15 | W2, W4, W6 |
| T1c·d, T2b·c·d | AC-11, AC-12, AC-14, AC-15 | W5, W6 |
| T6c·d·e, T12e | AC-12, AC-13, AC-14 | W5, W6 |
| T7f, T10d | AC-3, AC-15, AC-18 | W1, W6 |
| T3b, T9a·b·c·d의 F3 제공 조건 | AC-8, AC-9, AC-12, AC-18 | W3, W4, W5, W6 |
| S-01 생성 진입점·S-02 인수 요약·S-03, UI 공통 상호작용 | AC-1, AC-6, AC-16, AC-17 | W2, W7, W8 |
| 사용자 cutoff 결정의 보완 경계 | AC-10 | W4 |
| F1 AC-5/10/20/21/23/25의 원문·질문·답변·상태 전이와 관련 인계 원자성 | AC-9, AC-13 | W4, W5 |
| F1 AC-19/21/25/30의 필수 질문·지정 답변과 인수 후 보존 | AC-3, AC-5, AC-7, AC-15, AC-16 | W1, W2, W3, W6, W7 |
| F1 AC-26/27/30의 ACK 후 실행 버전·분석 최신성 | AC-8, AC-16, AC-18 | W3, W6, W7 |
| F1 AC-3/9/29/32의 receipt·현재 owner·진단 범위 | AC-11, AC-12, AC-15 | W5, W6 |

수용 조건의 근거는 [기능 명세](../../02_FUNCTIONAL_SPEC.md) FR-09, [UI](../../06_UI_SPEC.md) §2·4·8·10·11, [시험 계획](../../07_TEST_PLAN.md), [fixture](../../10_FIXTURES.md), [F3 작업 지시](../../12_CODEX_TASKS.md) §6이다. 사용자 cutoff 결정의 추가 관찰 조건은 반복 생성·새 snapshot 편입·ACK 이후에도 같은 기준 시각과 추가 표시를 유지하는 것이다. 이는 기존 T12c의 F3 범위를 구체화하며 실행 결과가 아니다.

F3 입력에는 네 서버 계정과 지정 교대 쌍, 질문/승인/작업/검증 대기 및 review_required 사건, 다른 사업장/교대, 새 정보·해결 경합의 독립 합성 자료가 필요하다. 자료의 UUID·기대값은 실제 앱에서 생성한 성공 기록과 구별한다. 기존 제품 데이터나 설정 파일의 마이그레이션·업데이트 호환성은 현재 실행 앱과 저장 데이터가 없어 적용 대상이 아니다. 신규 F3 영속 구조와 F0 migration 통합은 포함한다.

### 완료 후 공동 평가 항목

- F1 live 질문/답변 → F2 실제 Action 승인·착수 → F3 미해결 인수 → 같은 assignee의 결과 → F4 수신 owner 최종 검증까지 전체 T8은 [시험 계획](../../07_TEST_PLAN.md) T8과 [시험 결과](../../../TEST_RESULTS.md)에서 공동 확인한다. F3 자체의 실제 인수 경계는 AC-1의 필수 조건이며 전체 live 수행을 대신하지 않는다.
- ACK와 경합하는 F1 finalizer의 실제 SUPERSEDED(T3b), 이전 owner의 F4 검증 거부(T1c), 실제 해결 서비스와의 양방향 경합(T6)은 각 기능 통합 시 같은 시험 기록에서 확인한다. F3가 제공해야 하는 버전·owner·원자성·늦은 ACK 거부는 AC-13·14·15·18에 남아 있다.
- 배포 접근·최종 앱 SHA·리허설·접수는 [제출 절차](../../15_SUBMISSION_RUNBOOK.md)와 [제출 인덱스](../../../SUBMISSION.md)의 F5 평가다. 실제 현장 효과·안전성·장기 운영 성과는 이 합성 F3 기능의 완료 조건이 아니다.

문서 검토, 결정론적 서버 시험, 실제 브라우저 조작, live 모델 호출, 배포, 접수는 서로 다른 증거다. 실행하지 않은 앱 시험은 NOT_RUN으로 기록한다. 이 목표 문서에는 진행률·실행 명령·PASS 결과를 적지 않는다.

## Open Decisions

없음. cutoff 갱신 의미는 위 사용자 답변으로 확정했다. DTO 세부 필드명·차이 계산 위치·내부 서비스 구조 등 결과를 바꾸지 않는 사항은 구현자가 기존 공통 계약에 맞게 정한다.
