# F2 — F1 ORM 연결과 F4 준비 검사 인계

2026-10-09 · 최초 기준 F1 #6 `c46d490`에서 시작해 작업 중 최신 `7072e63`을 통합했고, 기존 F2 #5 `3670cd2`. F1 ORM·세션·명령 receipt에 F2 서버를 연결했다. 사람의 RESOLVE/RETURN, 해결 사례 API, F2 화면 연결과 실제 모델 호출은 후속이다.

## 단일 실행 기반

- 생산 API는 F1 `main.command → core.transactions.execute_command`를 사용한다. 세션·Origin·사업장 범위를 확인하고 같은 actor/site/key의 완료 응답을 먼저 재사용한다.
- `features/actions/orm.py`가 F1 ORM Session과 기존 F2 순수 업무 판정을 연결한다. 별도 engine/commit/receipt를 만들지 않는다. `ActionApplication`과 독립 router는 기존 계약 시험용으로 보존하며 생산 앱에 중복 등록하지 않는다.
- 신규 명령은 Incident → Action/Request를 ID 순으로 잠근다. 부모 버전은 `bump_incident`가 한 번만 증가시키고 F3 hook도 같은 transaction에서 실행한다.
- API 기본 조립과 worker CLI는 `core.ports.production_ports()`를 공통 사용한다. 명시적으로 주입한 FeaturePorts는 시험이나 다른 명시적 조립을 위해 그대로 보존한다.

## F1 → F2 작업 확정

`FeaturePorts.action_finalizer(tx, incident_id, run_id, input_version, draft_id, trigger_event_id)`는 `{action_id, created, action_version}`을 반환한다. ID는 경계에서 문자열/UUID로 변환하며 실제 ORM identity는 문자열이다.

F1이 전체 사건 그래프와 Job lease를 잠그고 검사한 transaction 안에서 호출한다. F2는 그 Session으로 완전한 업무 context와 draft/run을 읽고 **Action 행만** staging한다. Incident 상태·버전·proposal event·인계 revision·Job/Run과 최종 lease 검사는 F1 소유다. 최종 검사 실패 시 Action도 rollback된다. 생성·재사용 모두 후보 경계 호출 전후의 전체 Approval ID 집합과 DB 값을 검사한다. 승인 추가·삭제·교체·수정은 거부하며 F1/F2/F3 효과를 함께 rollback한다. `stage_proposal(action)`은 부모나 이벤트를 쓰지 않는다.

F1은 기존 Action/Approval의 불변성과 호출 전후 전체 Action ID 집합을 검사한다. 반환된 한 작업 외 다른 slot의 작업을 함께 추가해도 거부한다. 같은 generation의 기존 Action은 재활성화하지 않고 동일 ID를 반환한다.

배정은 설비의 default maintainer와 현재 owner 교대의 MAINTENANCE 배정, enabled/site를 서버에서 확인한다. Phase 1 소프트웨어 데모의 기한은 생성 시각 +1시간이며 모델이 지정하지 않는다. 실제 현장 SLA나 안전 기한이라는 의미는 없다.

## 승인·착수·결과

기존 API의 body/성공 응답은 유지한다. 승인/반려는 현재 owner supervisor, 착수/결과는 assignee 권한을 검사한다. 모든 명령은 Action과 Incident 버전을 함께 검사한다.

승인 payload는 title/scope/assignee/due_at/criteria/revision/evidence를 정규화해 SHA-256으로 보존한다. 승인 후 수정 API는 없다. 결과는 작성자·시각이 있는 append-only Message와 completion_report Evidence로 저장한다. 문자열의 원문 공백·개행은 보존한다.

새 승인/결과/근거/이벤트만 추가하며 기존 collection을 삭제하거나 교체하지 않는다. F3 hook이나 저장 오류는 receipt까지 전체 rollback한다. 정상적인 부족 조건은 결과 저장 성공과 함께 반환한다. 해결 뒤 인가된 새 입력은 rejected_input과 거부 receipt만 저장하고 사건 버전·snapshot은 바꾸지 않는다.

## 공통 준비 검사

`resolution/readiness.py`의 순수 함수는 실제 필수 작업·유효 승인·필수 답변·결과 원문과 completion_report·근거·review_required를 검사한다. DB adapter는 model context의 크기 제한이나 UI 페이지네이션을 사용하지 않고 전체 업무 자료를 읽는다.

- F2 완료 응답: `verification_ready`, `unmet_requirements`.
- F1 port: `readiness_evaluator(tx, incident=...) → {ready: bool, unmet_requirements: list[str]}`.
- 조회용 자료의 잘못된 필수 형태는 `INVALID_RESOLUTION_INPUT`으로 차단한다. 임시 빈 값으로 조건을 통과시키지 않는다.
- 준비 검사 자체에는 PENDING_VERIFICATION 상태를 요구하지 않는다. 실제 검증/RESOLVE는 후속 F4에서 owner·최신 버전·대기 상태·notes를 추가 검사한다.

근거의 동일 사건·사업장·설비 범위와 hash를 확인한다. SOP는 보존된 승인 상태와 equipment_ids 범위를 검사한다. 다른 설비의 과거 case는 명시적 comparison_only 근거로만 허용하고 source_type·출처를 유지한다.

## 기존 DB 유지

F1의 기존 actions/approvals 모델을 재사용한다. `0001_f1_foundation → 0002_session_shift → 0003_action_approval_unique`에서 승인 revision 고유키만 추가한다. 기존 중복 승인 자료가 있으면 migration은 실패하며 과거 자료를 임의 삭제하지 않는다.

기존 F2 `tables.py`는 독립 PostgreSQL 계약 시험용이다. 생산 Base에 등록하거나 다른 UUID schema를 현재 DB에 붙이지 않는다. 상태·근거·본문의 세부 계약은 서버에서도 검증한다.

## 시험과 다음 단계

저장소 루트에서 동일한 requirements.lock 환경으로 실행한다.

```sh
python -m pytest -q tests/backend apps/api/tests/actions
python scripts/export_contracts.py --check
```

`TEST_DATABASE_URL`은 업무 DB와 분리한 PostgreSQL을 지정한다. 독립 테이블 계약 시험에는 `F2_TEST_DATABASE_URL`도 지정한다. 각각 임의 schema만 생성·정리하며 기존 업무 데이터는 수정하지 않는다.

`test_actions_integration.py`는 실제 F1 finalizer와 F2 ORM·HTTP 경로를 시험한다. `test_actions_http_process.py`는 별도 uvicorn 프로세스·실제 loopback HTTP·PostgreSQL로 승인/착수/결과를 수행하고 프로세스를 재시작해 세션·동일 receipt·결과 보존을 확인한다. 모델 결과는 명시적인 합성 fixture이며 live AI 증거가 아니다.

F2 전체 상태는 IN_PROGRESS다. 기존 #5의 작업 패널은 F1 상세 슬롯에 후속 연결한다. F3 실제 ACK와 이후 F2 승인·수행·결과·인계 revision은 서버 통합 시험에서 확인했다. F4 RESOLVE/RETURN, 같은 사건의 전체 화면 T8, 실제 모델 L1b는 별도 검증한다. 정확한 실행 결과는 TEST_RESULTS의 F2/F1 통합 절을 따른다.

최종 검증 소스는 F1 7072e63 통합본이며 서버 243 PASS, 기존 Web 70 PASS·빌드·생성 계약 PASS다. F2 화면·사람 검증·live는 위 후속 범위를 유지한다.
