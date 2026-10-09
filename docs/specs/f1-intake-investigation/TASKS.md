# F1 Task별 결과와 경계

이 문서는 [SPEC.md](SPEC.md)의 W1~W12를 자세히 정의한다. 각 W는 완료 때 관측 가능한 결과이며 실행 순서·일정·체크리스트·진척 기록이 아니다. 조건 ID와 정책은 SPEC.md가 기준이다. 사용자 결정에 따라 Phase 1의 확인 질문은 모두 필수다.

F0 계약·공유 통합과 F2/F4의 실제 서비스 제공은 별도의 책임이다. 아래 의존 관계는 F1 결과 사이의 관계이고, 타 기능 전체 구현을 이 목표의 완료 조건으로 대체하지 않는다. 기존 시험 ID는 기대 결과를 찾는 참조이며 실행 명령이나 통과 기록이 아니다.

F3와 맞물리는 W2~W12의 연결 계약은 [F3 SPEC](../f3-handover/SPEC.md#f1과-공유하는-연결-계약)을 함께 적용한다. F3의 W1~W8은 F1의 같은 W 번호와 독립적이며, 두 기능 전체의 완료를 서로 선행조건으로 만들지 않는다.

## W1 — AI 상태와 무관한 제보 접수와 재조회

- **결과:** 사용자가 S-01에서 허용 설비와 원문을 제출하면 실제 Incident를 열어 같은 원문을 읽는다. 모델이 중단되어도 접수는 유지된다.
- **화면·API:** 제보 입력·불확실한 전송 보존·접수 상태, `POST /api/v1/incidents`와 생성 후 상세 연결. 202는 저장 완료이고 조사/Action 성공이 아니다.
- **데이터·권한:** Incident/REPORT Message/이벤트/Job/receipt 일괄 저장, version=1, 현재 교대 책임자 서버 결정. 세션·Origin·site·설비·배정 검증과 오류 계약을 공통 기반에서 적용한다.
- **경계 결과:** 같은 key의 재전송과 중복 클릭은 같은 응답/ID로 수렴한다. 같은 key의 다른 입력·누락 배정·무권한은 새 업무를 만들지 않는다.
- **조건:** AC-1, AC-2, AC-3. **의존:** 없음.
- **기존 연결:** FR-02, AC-F1.1~1.2, T1d/T2a~d/T7, UI S-01. 출처: [기능 §4](../../02_FUNCTIONAL_SPEC.md), [API §4](../../04_API_CONTRACT.md).

## W2 — 추가 기록·정정·종료 경계의 원문 보존

- **결과:** 추가 NOTE와 CORRECTION을 원문과 함께 읽고 각 기록의 작성자·시각·질문/정정 연결을 구별한다.
- **화면·API:** S-02 일반 추가 입력과 `POST /incidents/{id}/messages`, `reply_to_request_id=null`의 일반 기록 경로. 정정도 새 기록이며 기존 text는 그대로다.
- **데이터·권한:** 같은 사건의 correction_of만 허용하고 새 업무 입력은 상태명과 무관하게 version +1. 이벤트·필요 Job·receipt 및 관련 인계 갱신과 원자적으로 연결한다. 기존 인계 revision은 보존하고 최신 내용의 revision·재확인 상태는 F0/F3 공통 계약으로 반영한다.
- **경계 결과:** 검증 대기 중 입력은 재조사로 연결한다. 해결 후 인가된 늦은 입력은 rejected_input/receipt로 보존되고 snapshot·version은 그대로다. 재전송 거부 기록도 하나다.
- **조건:** AC-3~AC-7. **의존:** W1.
- **기존 연결:** AC-F1.3, T3a/T6a~b/T9a~d/T10d. 출처: [도메인 §4.2·4.7·5](../../03_DOMAIN_MODEL.md), [API §4](../../04_API_CONTRACT.md).

## W3 — 실제 사건 목록·상세·근거·Job 조회

- **결과:** 사용자가 자신의 범위에서 사건을 찾고 저장된 원문·질문·업무 상태·근거와 조사 상태를 다시 읽는다.
- **화면·API:** S-01 목록과 S-02의 F1 데이터, `GET /incidents`, `/incidents/{id}`, `/evidence/{id}`, `/jobs/{id}`. mine은 owner/assignee/OPEN 질문 대상에 따라 계산한다.
- **데이터·권한:** 동일 site 필터·cursor·정렬·페이지 제한, 관련 사건 접근 권한, Evidence 원문 snapshot, 실제 Job/run 상태. 공통 상세 DTO와 셸에 기여하며 복제 상세 화면이나 합성 성공 데이터를 만들지 않는다.
- **경계 결과:** 실제 빈 응답과 조회 실패를 구분한다. 타 사업장 자원·근거·버전은 오류에서도 누출되지 않고 진단의 추가 정보는 현재 owner 권한을 따른다. 동일 site의 상세 읽기가 지정 인계 참여자만의 snapshot·token·타 항목 내용에 대한 조회 권한으로 확대되지 않는다.
- **조건:** AC-8, AC-9. **의존:** W1.
- **기존 연결:** T1d, 근거 부정 시험, UI S-01/S-02. 출처: [API §2·5·9](../../04_API_CONTRACT.md), [UI §1~5](../../06_UI_SPEC.md).

## W4 — 영속 조사·Job 조회·수동 재시도·lease 복구

- **결과:** 조사 중단·실패·재점유를 동일 Job과 서로 다른 attempt/run으로 추적하고 원문/업무 효과를 보존한다.
- **API·실행 경계:** `/jobs/{id}`와 owner supervisor의 `/jobs/{id}/retry`. 최초 OPEN 전이 이후 input_version을 고정하고 DB 잠금 밖에서 모델 작업을 수행한다.
- **데이터·권한:** F0의 claim/lease/잠금 계약에 참여한다. 업무 성공·실패·SUPERSEDED·analysis 모두 현재 소유권을 검사한다. 유효 재시도는 같은 Job/trigger/dedupe_key, 새 attempt/run을 만든다.
- **경계 결과:** RUNNING/SUCCEEDED/SUPERSEDED/비재시도 FAILED/시도 소진/반려/해결의 응답이 API 계약과 일치한다. WAITING_INPUT 대기는 재시도 대상이 아니다. 마지막 만료 attempt는 복구기가 추가 호출 없이 종료한다.
- **조건:** AC-10, AC-27, AC-28, AC-29. **의존:** W1.
- **기존 연결:** T7a/c/d/e/g, T11a~d. 출처: [도메인 §6](../../03_DOMAIN_MODEL.md), [Agent §7](../../05_AGENT_DESIGN.md), [API §9](../../04_API_CONTRACT.md).

## W5 — 실제 자료 검색·출처와 run 내부 작업 후보

- **결과:** 설비 문맥·승인 SOP·해결 사례의 실제 조회 결과와 출처가 조사에 제공되고, 후보는 정식 작업과 구별된다.
- **도구:** `get_equipment_context`, `search_documents`, `search_similar_incidents`, `propose_action`의 고정 입력/출력. site·actor·run·input_version은 서버가 주입한다.
- **데이터·권한:** query/별칭/본문 기반 조회, SOP 승인·적용 범위, 해결 case만 검색, 이번 run이 본 근거만 후보에 사용. 발췌·출처·버전·시각·범위·hash가 보존된다.
- **경계 결과:** ERROR/EMPTY/partial이 변조되지 않는다. fixture ID로 정답을 고르거나 자료의 지시를 실행하지 않는다. 타 run draft·허위/타 사건 출처·임의 assignee/승인/기한은 거부된다. 검색·draft만으로 업무 버전과 Action은 늘지 않는다.
- **조건:** AC-11~AC-15. **의존:** W1.
- **기존 연결:** 도구별 부정 시험, T9c, L1a/L3의 입력 경계. 출처: [Agent §3~4](../../05_AGENT_DESIGN.md), [Fixture의 기대값 격리](../../10_FIXTURES.md).

## W6 — Responses 실행과 다섯 최종 판단의 검증

- **결과:** 최신 DB 문맥의 조사에서 실제 제공된 도구 결과와 최종 DTO를 연결하고 유효 결과와 실패를 구분한다.
- **실행 계약:** 같은 run의 필요한 output/call_id 보존, strict와 nullable schema, 출력 추가 필드 거부, 서버 전용 key·store 설정, 모델·도구·deadline·출력 상한.
- **판단 범위:** ASK_USER / PROPOSE_ACTION / WAIT_EXISTING / REQUEST_VERIFICATION / BLOCKED의 필드 조합·ID·근거·질문 수·선택 후보를 검사한다. 분기별 실제 반영은 W7/W9/W10의 경계다.
- **경계 결과:** 모델 refusal/incomplete/API/파싱 실패와 도구 ERROR 뒤 유효 BLOCKED를 구별한다. 후보 생성 후 DTO 실패의 업무 효과는 없다. F3 ACK를 포함해 input_version이 달라지면 stale 결과가 현재 analysis·질문·Action을 덮어쓰지 않는다. 자기 ACK에 대한 인계 최신성 예외와 Agent 버전 검사는 별개다.
- **조건:** AC-16, AC-17, AC-18, AC-26. **의존:** W4, W5.
- **기존 연결:** T3a/b, T7a~c, T9, 도구 부정 시험, L1a/L1b/L2/L3의 실행 경계. 출처: [Agent §5~8](../../05_AGENT_DESIGN.md), [시험 계획](../../07_TEST_PLAN.md).

## W7 — 지정자에게 보이는 영속 필수 확인 질문

- **결과:** 질문은 실제 Request ID·목적·대상·원문·근거·상태를 가지며 지정자에게 표시된다. 같은 목적의 열린 질문은 중복되지 않는다.
- **저장·표시:** ASK_USER의 유효 1~2개 질문, 허용 목적과 서버 정비 담당자, OPEN 중복키 재사용. S-02 카드에는 모델 초안 대신 확정된 질문이 보인다.
- **데이터·권한:** 새 질문 효과와 최종 분석/이벤트/버전/관련 인계 갱신/Job/Run 종료가 같은 확정 경계에 있다. 기존 질문 재사용만으로 업무 버전을 올리지 않는다. VERIFY_SCOPE/VERIFY_RESULT 모두 서버가 `is_required=true`로 저장하며 모델·클라이언트의 선택 질문 전환은 허용하지 않는다.
- **경계 결과:** 실제 OPEN 질문이 있어야 Run WAITING_INPUT/Job SUCCEEDED가 된다. 사람 답변을 기다리며 연결·재시도 큐·반복 호출을 유지하지 않는다.
- **조건:** AC-5, AC-19, AC-20. **의존:** W6.
- **기존 연결:** AC-F1.4/1.7/1.9, T2f/T7e, L1a. 출처: [FR-04](../../02_FUNCTIONAL_SPEC.md), [도메인 §4.2](../../03_DOMAIN_MODEL.md), [Agent §5·7](../../05_AGENT_DESIGN.md).

## W8 — 지정 답변과 새로운 조사

- **결과:** 지정 정비 담당자의 답변을 같은 Request에서 읽고, 최신 답변을 포함한 별도 새 run을 확인한다.
- **화면·API:** S-02의 지정 질문 답변 입력과 일반 추가 입력을 구별하고 `reply_to_request_id`와 부모 expected_version을 전달한다.
- **데이터·권한:** 같은 사건·OPEN·대상자·버전 검사 뒤 답변 Message/Request ANSWERED·버전/이벤트/새 Job/Incident 버전과 관련 인계 갱신을 함께 반영한다. owner의 대리 답변 권한은 없다.
- **경계 결과:** 다른 대상·타 사건·닫힌 질문·구버전·동시 답변은 부분 효과가 없다. 성공 재전송은 최초 응답을 재사용한다. worker/API 재시작 뒤에도 같은 질문에 답할 수 있고 이전 대기 run은 그대로 남는다. F3 인수로 owner가 바뀌어도 기존 질문의 필수 여부와 지정 응답자는 유지되며 새 owner가 답변을 대신하지 못한다.
- **조건:** AC-3, AC-5, AC-21, AC-22. **의존:** W2, W7.
- **기존 연결:** AC-F1.7~1.9, T1f/T2a/T3a/T7e, L1a→L1b. 출처: [API §4](../../04_API_CONTRACT.md), [FR-04](../../02_FUNCTIONAL_SPEC.md).

## W9 — F2 후보 확정 경계와 기존 업무 재사용

- **결과:** 선택된 후보 하나만 F2의 정식 확정 경계에 전달되고, 기존 generation 1 작업은 같은 ID로 유지된다.
- **내부 인터페이스:** `finalize_action_proposal(tx, *, incident_id, run_id, input_version, draft_id, trigger_event_id) -> {action_id, created, action_version}`. 별도 브라우저 Action 생성 endpoint를 만들지 않는다.
- **F1 책임:** 현재 run/draft/버전·출처·대상 검증, caller transaction, 마지막 현재 Job lease 확인, 부모 버전 한 번 증가와 관련 인계 revision/decision/analysis/Job/Run 종료 반영. F2는 고유키와 Action 데이터/이벤트를 책임진다.
- **경계 결과:** 내부 호출 실패·충돌·rollback 시 부분 성공이 없다. WAIT_EXISTING은 실제 같은 사건 ID를 참조하고 completed/rejected Action을 재활성화하거나 generation 2를 만들지 않는다.
- **조건:** AC-23, AC-24, AC-26. **의존:** W6.
- **기존 연결:** AC-F1.10, AC-F2.1/2.2의 접점, T2e/T3/T11, L1b/L2. 실제 F2 서비스 연결은 SPEC의 통합 평가에 포함한다. 출처: [API 내부 확정 계약](../../04_API_CONTRACT.md), [개발 계획 §5](../../08_BUILD_PLAN.md).

## W10 — 검증 준비 요청과 반려 후 보류

- **결과:** 모델의 준비 요청은 F4의 현재 준비 조건과 일치하고, 사람의 반려를 재조사가 해제하지 못한다.
- **내부 경계:** F4 공통 준비 판정과 관련 인계 revision 갱신을 같은 업무 트랜잭션에서 사용한다. 빈 Action·승인·완료·필수 질문·결과·근거·review_required의 부족 조건이 보존된다.
- **F1 책임:** 유효 REQUEST_VERIFICATION은 준비 상태까지만 옮긴다. review_required에서 원문과 기존 Action/승인/결과/사유를 보존하며 BLOCKED analysis만 갱신한다.
- **경계 결과:** 새 질문·신규 작업·자동 준비·RESOLVED·플래그 해제가 없다. 기존 완료 Action만으로 재검증에 진입하지 않으며 F4의 사람 검증 API를 모델이 호출하지 않는다.
- **조건:** AC-25, AC-34. **의존:** W6.
- **기존 연결:** AC-F1.11, T5a~i/T10c~d 및 준비 DTO 부정 시험. 실제 F4 연결은 통합 평가다. 출처: [D02/D06](../../11_DECISIONS_AND_SOURCES.md), [도메인 §8](../../03_DOMAIN_MODEL.md), [Agent §5](../../05_AGENT_DESIGN.md).

## W11 — 상태를 구별하는 화면과 실행 근거

- **결과:** 사용자가 제보 저장 여부·질문 대기·조사 실패·이전 분석·현재 업무 상태를 구별하고 실제 출처를 열 수 있다.
- **화면:** S-01/S-02의 원문·질문·조사·근거·오류/허용 재시도 표시. 실제 Request와 정식 Action을 draft와 구별한다. 사실/사람 진술·가설·미확인·모의 자료를 명확히 표시한다. analysis의 갱신 필요와 F3의 재인수 필요를 별도로 표시하고 정상 ACK 이후 오래된 분석만으로 추가 인수를 요구하지 않는다.
- **상호작용:** 폴링·네트워크 오류·409·계정 전환이 편집 입력을 잃거나 이전 명령을 다른 세션으로 보내지 않는다. 마지막 정상 조회·빈 값·캐시·오류를 구분하고 입력 label/키보드/모바일 폭을 지원한다.
- **기록·권한:** run/Job/attempt/input·applied version/실제 도구 인자·결과/source/업무 ID/최종 DTO/검증 거부·모드·모델/프롬프트/schema·오류·usage를 앱 SHA·dirty·자료 버전·설정 식별자·run_group_id와 연결한다. 일반 업무 안내와 owner의 정제 진단을 구분한다. 비밀·전체 환경·내부 추론은 제외한다.
- **조건:** AC-9, AC-30, AC-31, AC-32. **의존:** W2, W3, W4, W7, W8, W9, W10.
- **기존 연결:** UI §2~5·10~11, T2/T3/T7/T9/T10, L1a/L1b/L3의 화면 근거. 출처: [UI](../../06_UI_SPEC.md), [API §9~10](../../04_API_CONTRACT.md), [Agent §8](../../05_AGENT_DESIGN.md).

## W12 — 실제 F1 경계와 독립적으로 확인 가능한 결과

- **결과:** W1~W11의 정상·실패·동시 변경 결과가 실제 F1의 UI/HTTP/PostgreSQL과 저장된 실행 ID로 연결된다. 서로 다른 샘플 화면이나 개별 mock 결과만으로 전주기를 주장하지 않는다.
- **실제 경계:** 제보→원문 재조회, 지정 질문→답변→새 Job/run, 재시작 후 동일 ID/원문/질문, 409·권한 실패·멱등 재전송·lease 만료의 DB 효과.
- **외부 경계:** F2/F4를 계약 대체로 관측했다면 F1의 입력·거부·rollback만 확인한 것으로 식별한다. 실제 모델과 실제 타 기능 연결은 SPEC의 L1a/L1b/L2/L3 및 기능 연계 평가로 구별한다.
- **보존 결과:** 승인 payload·담당자·사람 결과·인계 revision·해결 snapshot을 F1 오류나 재조사가 바꾸지 않는다. 도구 부정 입력·fixture 기대값 노출·오래된 worker의 각 종료 경로·마지막 attempt 소진이 대표 성공 한 건에 묻히지 않는다.
- **조건:** AC-1~AC-34, 특히 AC-33/AC-34. **의존:** W1~W11.
- **기존 연결:** F1 관련 T1/T2/T3/T5/T6/T7/T9/T10/T11와 도구 부정 사례. F3의 전체 T4/T12, 전체 T8, 배포·제출은 F1 독립 완료 범위가 아니다. 출처: [시험 계획](../../07_TEST_PLAN.md), [기존 F1 구현 지시](../../12_CODEX_TASKS.md).

## 책임 인계 시 보존할 계약

| 대상 | F1 결과에서 확인 가능한 인계 내용 |
|---|---|
| F0 | 필요한 F1 데이터·제약·읽기 필드·오류, 공통 transaction/receipt/lease 사용, 공유 셸 패널 경계 |
| F2 | 이번 run/사건/버전의 선택 draft·trigger·허용 근거, 같은 transaction의 호출/반환 및 실패 원자성 |
| F3 | 원문·필수 OPEN 질문·현재 업무/owner·Evidence가 조회 가능하고 새로운 내용은 업무 버전과 공통 인계 갱신 경계에 원자적으로 반영됨; 기존 revision 보존과 최신 재확인 상태 연결 |
| F4 | 질문의 필수/답변 상태, 허용 근거·반려 차단, 준비 판정 재사용과 사람 해결 권한 보존 |
| F5 | 실제 ID·모드·버전·오류·관측 usage·원본 replay 참조. 계정·모델·F2/F4 미연결 상태를 live 성공으로 바꾸지 않음 |

이 문서가 F0/F2/F3/F4의 제품 기능을 F1 담당 범위로 이전하지 않는다. 상대 기능의 정확한 기한 정책·전체 구현 완료·배포 환경 제공을 F1이 임의 결정하지 않는다.
