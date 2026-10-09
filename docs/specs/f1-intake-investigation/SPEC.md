# F1 접수·AI 조사·질문과 답변

Status: Ready

## 목표

사용자가 제보한 원문이 AI 가용 여부와 무관하게 저장되고, 같은 Incident에서 실제 자료 조사, 지정자 질문과 답변, 검증된 작업 후보의 전달까지 이어진다. 화면·HTTP API·PostgreSQL·조사 실행기의 경계를 연결하며, 실패·재전송·동시 변경에서도 원문과 사람의 업무 상태를 보존한다.

사용자 요청은 README의 기능별 책임 중 **F1의 모든 작업을 Task로 나누는 것**이다. 이 명세는 신규 기능의 결과와 완료 조건을 정의한다. 작은 수정에 해당하지 않는다. Task는 아래 W1~W12의 결과 단위이며 실행 일정이나 진행 상태가 아니다.

## 현재 상태와 적용 범위

- 현재 저장소는 구현 문서와 기록 양식을 보유한다. 실행 앱·물리 스키마·F1 실행 결과는 아직 없다. 근거: [README](../../../README.md), [현재 진행 기록](../../../PROGRESS.md), [도메인 모델 서문](../../03_DOMAIN_MODEL.md).
- 기존 `scripts/export_codex_history.py`는 로컬 대화 기록 도구이며 F1 앱 구현이 아니다.
- 작성 대상은 신규 목표 `docs/specs/f1-intake-investigation/`이다. 기존 F1-a/F1-b의 내용을 대체하거나 축소하지 않고 FR-02~05와 AC-F1.1~11을 구체화한다.
- 포함: S-01 제보·목록, S-02 원문·질문·조사 패널, F1 API·읽기 모델·데이터, 세 조회 도구와 후보 도구, Responses 실행, finalizer, Job 조회·재시도·복구, 근거와 정제된 실행 기록, F1이 호출하는 기능 간 경계.
- 유지: v0.3의 enum·API·권한·D01~D07·불변 원문·generation=1·사람의 최종 해결 권한. 현재 구현된 앱 동작을 유지한다는 뜻이 아니라 이미 합의된 계약을 보존한다는 뜻이다.
- 범위 밖: F0 전체 구축, F2의 승인·착수·결과 제출, F3 인계 생성·ACK 구현, F4 최종 검증·해결 사례 생성, F5 배포·제출, 음성·관리형 검색·알림·복수 Action·generation 2·실제 설비 제어.
- 신규 endpoint, 자동 사건 병합, 별도 미연결 Report, 임의 상태 변경 API, 모델의 승인·해결 권한을 추가하지 않는다.

## 기능 간 책임과 제약

상세 경계와 Task별 결과는 [TASKS.md](TASKS.md)를 함께 읽는다. v0.3의 우선순위는 결정 D01~D07 → 도메인 → API → 기능·Agent·화면·시험 문서다.

| 경계 | F1이 책임질 결과 | 기존 담당 영역 |
|---|---|---|
| F0 → F1 | 서버 principal·receipt·버전·잠금·Job 계약을 사용한 F1 동작과 해당 경계의 거부 처리 | 세션·공유 enum/DTO·상세 셸·migration registry·공통 lease 기반 |
| F1 → F2 | 이번 run의 선택 draft와 사건/버전/trigger 전달, caller transaction·lease·부모 버전·Job/Run 종료 | `finalize_action_proposal`의 정식 Action 생성·재사용·고유키·담당표·Action 이벤트 |
| F4 → F1 | `REQUEST_VERIFICATION`에서 공통 준비 결과를 적용하고 부족 조건과 반려 차단을 보존 | `evaluate_resolution_readiness`와 사람의 최종 검증 |
| F1 ↔ F3 | 미응답 질문·원문·실패를 조회 가능하게 유지하고 새 업무 내용을 공통 인계 갱신 경계에 전달; ACK 등 새 업무 버전 뒤 오래된 분석 차단 | 인계 집합·snapshot·revision·ACK·owner 이전 |
| F1 → F5 | 실제 실행과 저장 효과를 연결할 ID·모드·버전·오류·관측 usage | 전체 전주기 평가·배포·제출 |

F3 연결 기준은 [교대 인계 명세의 F1 연결 계약](../f3-handover/SPEC.md#f1과-공유하는-연결-계약)이다. 기존 인계 항목의 원문·질문·답변 변화는 같은 업무 트랜잭션의 revision 갱신으로 이어진다. 최초 cutoff 뒤 새로 접수한 Incident는 F3의 서버 대상 조회에서 추가된 사건으로 구분하고 명시적 갱신 때 첫 snapshot에 편입한다. 최초 cutoff와 추가 표시는 해당 F3 명세에서 확정한 의미를 유지한다.

F1이 필요한 테이블·제약을 정의하되 공유 schema·migration head·상세 DTO와 셸의 통합 소유권은 F0에 둔다. 승인된 Action 내용, 기존 인계 revision, 해결 snapshot을 F1이 수정하지 않는다. 공유 도메인 서비스를 복사해 별도 규칙으로 운영하지 않는다.

외부 모델 호출은 DB 잠금 밖에서 한다. 실제 업무 확정은 `Incident → Action/Request → Handover item → Job` 잠금 순서와 집합 내부 ID 정렬을 지키며 업무 효과·이벤트·관련 인계 revision·필요 Job·receipt·버전을 원자적으로 다룬다. 이 연결은 원문·질문·답변뿐 아니라 최초 조사 상태 전이, Action 확정, 검증 준비 등 인계 내용에 영향을 주는 F1의 모든 수용된 업무 변경에 적용한다. 같은 트랜잭션에서 Incident.version은 최대 한 번 증가한다.

## 결정과 근거

| 결정 | 이유 | 출처 |
|---|---|---|
| F1 전체를 하나의 목표와 W1~W12 결과 단위로 정리 | 같은 사건·공통 finalizer·출처 규칙의 누락과 중복을 줄이고 기능 전체를 추적 | 사용자 요청; 작업 분해는 이번 Spec 작성 제안 |
| 각 결과에 화면·API·저장·권한·경계 처리를 함께 연결 | 기술 계층별 전담으로 기능을 분리하지 않음 | [개발 계획 §1~5](../../08_BUILD_PLAN.md), [기능 명세 §1~2](../../02_FUNCTIONAL_SPEC.md) |
| 신규 접수는 202와 Incident/Message/Job 실재 ID를 반환 | 원문 저장 성공과 AI 성공을 구분 | [API §4](../../04_API_CONTRACT.md), [FR-02](../../02_FUNCTIONAL_SPEC.md) |
| 질문의 목적·대상·중복키와 원문/답변의 원자성은 기존 계약 유지 | 모델 또는 클라이언트의 권한 확대와 중복 업무를 막음 | [도메인 §4.2·5](../../03_DOMAIN_MODEL.md), [Agent §5](../../05_AGENT_DESIGN.md) |
| Phase 1의 VERIFY_SCOPE/VERIFY_RESULT 질문은 서버가 모두 `is_required=true`로 저장 | 미응답 확인 질문을 남긴 채 검증 준비를 통과하지 않게 함. 선택 질문은 Phase 1에 제공하지 않음 | 사용자 답변: “Phase 1 질문은 모두 필수로 설정 (권장)” |
| F1은 후보 생성과 확정 호출을, F2는 정식 Action 서비스를 소유 | finalizer를 분리 commit하여 최신성·원자성을 잃지 않음 | [API 내부 확정 인터페이스](../../04_API_CONTRACT.md), [개발 계획 §5](../../08_BUILD_PLAN.md) |
| 현재 문서의 실행·검색·lease 초기 상한을 유지 | 미검증 성능값을 새로 정하거나 비용 한도를 보장하지 않음 | [Agent §7](../../05_AGENT_DESIGN.md), [결정 기록 §3](../../11_DECISIONS_AND_SOURCES.md) |
| 로컬에서 검증 가능한 F1 결과와 외부 자원이 필요한 통합 평가를 구분 | 다른 기능 전체의 완료·계정 제공만을 이 목표의 완료 조건으로 만들지 않음 | 이번 Spec 작성 제안; [D07](../../11_DECISIONS_AND_SOURCES.md), [시험 계획 §4·6](../../07_TEST_PLAN.md) |

마지막 구분은 기존 AC-F1.4~7·10이나 최소 네 live run 요구를 삭제하지 않는다. 이 목표 산출물을 독립적으로 확인해도 기존 기능 전체의 F1 완료를 선언하려면 아래 통합 평가의 실제 증거가 필요하다. 외부 경계를 대체한 결과는 실제 F2/F4 연결 또는 live 성공으로 집계하지 않는다.

## 사용 시나리오

| 종류 | 시나리오 | 조건 |
|---|---|---|
| 흐름 | 작업자가 설비와 원문을 제출하고 AI가 중단되어도 실제 사건을 다시 열어 같은 원문을 읽는다 | AC-1, AC-2, AC-3, AC-33 |
| 흐름 | 사용자가 보충 기록 또는 정정을 남기고 기존 원문과 새 기록을 함께 읽는다 | AC-4, AC-5 |
| 흐름 | 사용자가 자신의 담당 사건을 찾아 원문·질문·업무와 조사 상태를 구별한다 | AC-8, AC-9, AC-30 |
| 흐름 | 조사에 실제 자료와 근거가 사용되고 검증된 질문을 지정 정비 담당자가 답하면 새 run이 시작된다 | AC-10~14, AC-17~22 |
| 흐름 | 선택된 유효 후보만 F2 경계로 전달되고 기존 주 작업이 있으면 같은 ID를 유지한다 | AC-15, AC-16, AC-23, AC-24 |
| 흐름 | 실패한 조사에서 현재 owner가 허용된 재시도를 하면 같은 Job의 새 attempt/run이 관측된다 | AC-27~29, AC-32 |
| 경계 | 같은 요청의 결과가 유실되어 재전송하거나 다른 사용자의 질문에 답하려 한다 | AC-3, AC-21, AC-22 |
| 경계 | 새 메시지·지정 답변·ACK가 조사 중 먼저 반영되어 기존 결과의 버전이 오래된다 | AC-5, AC-20, AC-26 |
| 경계 | worker가 사라지거나 마지막 attempt의 lease가 만료된 뒤 늦은 성공·실패가 도착한다 | AC-27, AC-28 |
| 경계 | 도구 조회 ERROR, 모델 refusal/incomplete, 한도 초과, 허위 출처 또는 자료 속 지시가 발생한다 | AC-11~14, AC-16~18 |
| 경계 | 이미 해결된 사건에 늦은 원문이 도착하거나 검증 대기 중 새 정보가 입력된다 | AC-6, AC-7 |
| 유지 | 승인된 작업, 인계 책임, 해결 snapshot과 원문은 F1 재조사로 덮어쓰지 않는다 | AC-4, AC-7, AC-24, AC-25, AC-34 |
| 유지 | 반려 사건은 기록과 분석을 읽을 수 있지만 새 질문·작업·자동 검증 준비로 재개하지 않는다 | AC-25, AC-30 |
| 유지 | fake·live·replay·미수집 usage와 업무 상태를 구분하고 비밀·내부 추론을 노출하지 않는다 | AC-9, AC-31, AC-32 |

## Acceptance Criteria

### 접수·원문·조회

- **AC-1** 허용된 세션의 신규 제보는 Incident·최초 Message·이벤트·Job·receipt가 모두 저장된 뒤 202와 실제 ID를 반환한다. 모델을 사용할 수 없어도 저장된 원문은 상세 재조회와 재시작 뒤 남는다. 부분 생성은 없다.
- **AC-2** 접수 owner는 서버의 현재 교대 배정으로 정해진다. 인가되지 않은 site/설비·위조 actor/role/owner·누락 배정은 기존 401/403/404/422 계약으로 거부되고 불완전한 사건이나 범위 밖 내용·버전을 노출하지 않는다.
- **AC-3** 접수·추가 원문·답변·재시도의 도메인 쓰기는 `(site, actor, key)`와 method/route/body에 대한 receipt 규칙을 지킨다. 동일 완료 요청은 이후 상태·버전 변화보다 먼저 최초 HTTP 응답을 재사용하며 `Idempotent-Replayed: true`를 반환한다. 업무·버전·이벤트·Job은 늘지 않는다. 다른 payload는 멱등 충돌, 진행 중 키는 진행 중 오류다.
- **AC-4** 일반 추가 기록과 정정은 작성자·시각·동일 사건 연결을 가진 새 Message로 남는다. `correction_of`는 같은 사건의 기존 Message만 참조하고 원문은 수정되지 않는다. 지정 답변 입력과 일반 추가 입력은 구별된다.
- **AC-5** 새 업무 원문은 상태명이 같아도 필요한 이벤트·Job과 함께 Incident.version을 정확히 한 번 증가시킨다. receipt 재사용·조회·검색·draft·analysis·Job 상태만 바꾸는 동작은 업무 버전을 올리지 않는다. 새 원문·질문·답변이 기존 인계 항목의 내용을 바꾸면 F0/F3 공통 갱신 경계에 같은 업무 트랜잭션으로 연결되어 기존 revision은 보존되고 최신 내용·새 revision·재확인 필요가 도메인 계약대로 반영된다. F1 변경만 성공하고 필요한 인계 갱신은 유실되는 부분 반영은 없다.
- **AC-6** PENDING_VERIFICATION에 새 원문이 수용되면 INVESTIGATING과 새 조사로 연결되고, 이전 버전의 검증·조사 결과는 적용되지 않는다. 반려가 없는데 `review_required`를 영구 설정하지 않는다.
- **AC-7** RESOLVED 이후 늦은 인가된 입력은 `rejected_input`과 거부 receipt에 한 번 보존되며 `409 INCIDENT_RESOLVED`와 신규 제보 안내를 받는다. Message 수용·Incident.version·해결 snapshot은 변경되지 않는다.
- **AC-8** 목록의 site·설비·상태·`all/mine`·cursor 필터가 실제 저장값을 반영한다. `mine`은 현재 owner·Action assignee·OPEN Request 대상의 합집합이다. 기본 20/최대 100, `updated_at DESC, id DESC` 순서를 따르며 기본 미해결 목록과 해결 이력을 구별한다.
- **AC-9** 상세·Job·Evidence 읽기는 사건 접근 범위를 따르고 저장된 원문/질문/답변/업무/analysis를 별도 값으로 반환한다. 존재하지 않거나 범위 밖의 근거는 404다. 일반 사용자는 업무 상태와 실패 안내를 읽고, 추가 정제 진단은 현재 owner supervisor 권한을 지킨다. 동일 site의 Incident 읽기와 지정 출발/수신 책임자의 인계 전체 읽기는 구별한다. 공유 상세의 handover 요약·링크로 비참여자에게 제한된 snapshot·token·다른 항목 내용이 노출되지 않는다.

### 자료 조사·후보·모델 실행

- **AC-10** 새로운 trigger의 조사 문맥은 최신 DB의 사건·버전·원문·질문/답변·Action·승인·서버 배정·현재 근거로 구성된다. 최초 OPEN→INVESTIGATING 전이가 필요한 경우 그 커밋 이후 input_version이 고정되고 기존 IN_PROGRESS를 조사 시작만으로 바꾸지 않는다.
- **AC-11** `get_equipment_context`, `search_documents`, `search_similar_incidents`는 실제 query·설비 별칭·자료 내용과 승인/해결 메타데이터에 따라 결과가 달라진다. 같은 사업장과 도구별 설비 적용 범위를 검증하며 타 설비 해결 사례는 비교 자료로 남는다. 검색은 최대 5 chunk·각 2,000자와 결정적 동점 순서를 지킨다.
- **AC-12** 조회의 OK·EMPTY·ERROR·partial이 구분된다. 오류는 `data=null`과 오류 코드/메시지/재시도 가능성을 가지며 모델 입력과 저장된 실행 기록에 전달된다. 조회 실패를 기록 없음·정상·해결로 바꾸지 않는다.
- **AC-13** 인용할 수 있는 근거는 이번 run의 초기 입력 또는 실제 도구 응답으로 받은 서버 발급 ID뿐이다. 출처·버전·위치·설비 범위·작성/관측/조회 시각·발췌가 추적되고 캐시나 원본 자료의 후속 변경으로 기존 Evidence snapshot을 덮어쓰지 않는다.
- **AC-14** 사람 진술·기록·시스템 상태·가설·과거 사례가 구별된다. fixture 정답·예상 답변·시험 기대값은 모델 입력에 없고, 원문·SOP 등에 포함된 지시가 도구 허용 목록이나 서버 권한을 변경하지 못한다.
- **AC-15** `propose_action`의 출력은 현재 run·Incident·input_version에 묶인 draft다. 범위·완료 기준·허용 출처가 검증되고 모델이 assignee·기한·승인·필수 여부·상태를 지정하지 못한다. 후보 생성만으로 정식 Action·승인·업무 버전이 생기지 않는다.
- **AC-16** 다섯 최종 decision의 필수·금지 조합과 모든 ID가 검증된다. 알 수 없는 ID·다른 사건/다른 run의 draft·보지 않은 출처·유효하지 않은 기존 ID·미선택 후보는 업무에 반영되지 않는다. 유효 DTO 없이 후보만 생성된 실행은 정식 Action이나 질문을 남기지 않는다.
- **AC-17** Responses 연결은 같은 run의 필요한 output과 정확한 call_id의 도구 결과를 이어 전달한다. strict 도구/최종 schema, required nullable 필드, 추가 필드 거부, `parallel_tool_calls:false`, `store:false`와 서버 전용 key 경계를 지킨다. 새 업무 이벤트는 이전 모델 문장 대신 최신 DB 문맥에서 시작한다.
- **AC-18** refusal·incomplete·파싱 오류·API 오류·timeout·호출 상한을 구별한다. 기본 모델 7회·도구 6회·run 60초·출력 2,000 tokens 내에서 실패/형식 보정도 계산하고, 늦은 결과는 반영하지 않는다. 유효 DTO가 없으면 FAILED이며, 도구 ERROR를 받은 뒤 검증된 BLOCKED 판단은 Job/Run SUCCEEDED와 보류 analysis만 남긴다. 거절을 강제 재질문으로 우회하지 않는다.

### 질문·답변·최종 업무 반영

- **AC-19** ASK_USER는 허용된 `VERIFY_SCOPE|VERIFY_RESULT`, 서버 배정의 지정 정비 담당자, 유효 근거를 가진 1~2개 질문을 저장한다. 같은 `(incident, target, purpose)`의 OPEN Request는 재사용하고 새 행·버전을 중복 생성하지 않는다. Phase 1 질문은 서버가 모두 `is_required=true`로 저장하며 모델·클라이언트가 선택 질문으로 낮출 수 없다.
- **AC-20** 저장 또는 재사용된 실제 OPEN Request가 있을 때만 해당 Run을 WAITING_INPUT, Job을 SUCCEEDED로 종료한다. 대기 중 모델 연결이나 재시도 호출을 유지하지 않는다. Request·최종 분석·이벤트·필요한 버전·종료 기록의 부분 반영은 없다.
- **AC-21** 같은 사건의 OPEN Request에 지정된 사용자만 답변할 수 있다. owner도 다른 대상자의 답변을 대신하지 못하며 F3 ACK 후에도 Request.target_user_id/is_required/status는 그대로다. 허용된 답변은 Message·Request ANSWERED/버전 +1·이벤트·새 Job·Incident 버전 +1과 함께 저장되며 같은 Request ID와 새 run ID로 연결된다. 비대상자·닫힌 질문·다른 사건·오래된 부모 버전은 후속 효과 없이 거부된다.
- **AC-22** 답변 재전송·경합은 하나의 답변과 새 Job으로 수렴하고 최초 receipt를 재사용한다. API/worker 재시작 뒤에도 저장된 질문에 답변할 수 있다. 새 답변은 기존 WAITING_INPUT run을 재사용하지 않고 새 trigger와 최신 문맥의 조사로 이어진다.
- **AC-23** PROPOSE_ACTION에서 F1은 선택 draft를 `finalize_action_proposal(tx, *, incident_id, run_id, input_version, draft_id, trigger_event_id)`에 전달한다. 반환 `{action_id, created, action_version}`를 해석하며 Action 확정/analysis/이벤트/부모 버전/관련 인계 revision/Job/Run 종료를 같은 caller transaction에서 반영한다. 이 분기는 `questions=[]`이며 새 질문을 저장하지 않는다. 외부 서비스의 거부·실패·rollback 때 F1 쪽 성공이나 부분 업무를 남기지 않는다.
- **AC-24** WAIT_EXISTING은 같은 사건의 실제 유효 Request/Action ID를 적어도 하나 유지한다. generation은 1이며 완료·반려 Action을 재생성·재활성화하지 않는다. 기존 generation 작업을 반환받은 경우 새 Action으로 표시하거나 불필요한 업무 버전을 증가시키지 않는다.
- **AC-25** REQUEST_VERIFICATION은 F4의 동일 준비 판정을 거쳐 PENDING_VERIFICATION까지만 이동하며 관련 인계 revision도 같은 업무 트랜잭션에 반영한다. 빈 Action·미승인/미완료·필수 질문 미응답·누락 결과/근거·review_required는 준비로 처리되지 않는다. 이미 검증 대기여야만 준비되는 순환 조건이 없다. review_required 사건은 원문/이력/기존 작업을 보존하며 BLOCKED analysis 외 새 질문·Action·자동 준비·해결·플래그 해제가 없다.
- **AC-26** 입력 버전이 바뀐 실행은 질문·Action·최신 analysis를 반영하지 않고 현재 lease의 소유자만 SUPERSEDED로 종료할 수 있다. F3 ACK의 업무 버전 증가도 이 검사에 포함하며, 자신의 ACK 때문에 인계 재확인을 요구하지 않는 예외를 Agent 버전 검사에 적용하지 않는다. 최신 조사할 업무와 미등록 Job이 있을 때만 후속 Job 하나를 만들며 RESOLVED·review_required에서는 자동 조사 반복을 만들지 않는다.

### 실행 복구·화면·확인 가능한 결과

- **AC-27** claim/재점유는 새 attempt·run·lease token으로 구분된다. 업무 성공뿐 아니라 실패·SUPERSEDED·analysis 저장도 RUNNING·현재 attempt/token·유효 lease를 요구한다. 오래된 worker의 모든 늦은 경로가 새 worker의 결과를 덮어쓰지 못하고 기존 run 기록은 보존된다. 모델 호출 동안 업무 DB 잠금을 유지하지 않는다.
- **AC-28** 마지막 허용 attempt의 lease가 만료되면 시스템 복구만 Job 잠금 안에서 조건을 재확인해 Job과 현재 미종료 run을 FAILED/ATTEMPTS_EXHAUSTED로 종료하고 token을 폐기한다. 추가 claim·모델 호출·analysis·업무 효과가 없으며 영구 RUNNING으로 남지 않는다.
- **AC-29** 실패 Job 재시도는 현재 owner supervisor와 기존 멱등 계약을 따른다. retryable FAILED·최대 시도 미초과·미해결·review_required=false일 때 같은 Job/trigger/dedupe_key로 QUEUED에 복귀하고 다음 claim에서 새 run이 생긴다. RUNNING은 409, SUCCEEDED는 현재 상태 200, SUPERSEDED는 최신 Job 안내 409다. WAITING_INPUT을 재시도하지 않고 Incident 버전도 증가시키지 않는다.
- **AC-30** S-01/S-02에서 접수·조사·질문 대기·답변 후 새 조사·업무 진행·후속 검토·AI 실패를 구별한다. 질문에는 실제 ID·목적·대상·필수 여부·상태·근거가 보이고 답변 입력은 지정자에게만 제공된다. `waiting_for_input`은 필수 OPEN Request의 존재로 계산하며 Phase 1의 미응답 질문이 하나라도 있으면 대기 표시와 준비 차단이 유지된다. analysis.base_version이 현재 버전과 다르면 갱신 필요를 표시하며 자신의 질문/Action 확정에 의한 버전 차이도 감추지 않는다. F3의 인수 최신성과 analysis 최신성은 별개이며 자기 ACK 뒤 ‘인수 완료’와 ‘이전 정보 분석’이 함께 표시될 수 있다. 분석 표시나 analysis만의 갱신을 이유로 인계의 추가 ACK를 요구하지 않는다.
- **AC-31** 입력은 접수 불확실성·네트워크 오류·409·폴링 동안 보존된다. 같은 명령은 같은 키, 의도적인 새 명령은 새 키를 쓴다. 세션 전환 뒤 이전 쓰기를 자동 재전송하지 않는다. 실제 빈 목록·조회 실패·캐시·마지막 성공 시각을 구별하고 숨긴 탭은 폴링을 멈춘다. 좁은 제보 화면·입력 label·키보드 조작·오류 연결이 제공된다.
- **AC-32** 저장된 실행 기록으로 Job/run/attempt/trigger/input·applied version/모드/모델/프롬프트·도구 schema 버전, 실제 도구의 정제한 인자·결과·반환 source ID·선택 후보·Request·Action·최종 DTO·검증 거부·오류·시간·관측 usage를 연결할 수 있다. 앱 SHA·dirty 여부·자료 버전·비밀을 제외한 설정 식별자·run_group_id도 연결된다. usage 미수집은 null이고 live 실패를 fake 성공으로 자동 전환하지 않는다. replay는 원본 run/commit/시각을 표시한다. 비밀·환경 전체·내부 추론은 기록·응답·화면에 없다.
- **AC-33** F1의 실제 화면 → F1 HTTP → PostgreSQL → 상세 재조회 경계에서 원문과 지정 답변의 지속성이 확인되고 재시작 뒤 같은 사건/질문으로 이어진다. 개별 컴포넌트 mock 통과만으로 이 결과를 충족하지 않는다. 모델/외부 기능 경계를 대체한 경우 그 모드를 명확하게 식별한다.
- **AC-34** 접수·답변·finalizer·복구의 중복/실패/동시 변경 결과에서 승인 payload·Action 담당자·사람 결과·인계 revision·해결 snapshot의 기존 값을 F1이 바꾸지 않는다. F2/F4 경계의 계약 거부와 rollback을 관측할 수 있고, F1 산출물의 독립 검증이 F2/F3/F4 전체 완료로 기록되지 않는다.

## 작업 분해 제안

아래 의존은 필요한 결과의 관계다. 세부 구현 순서·담당 일정·실행 상태는 정하지 않는다. 각 W의 상세 범위·화면/API/저장 경계·기존 시험 연결은 [TASKS.md](TASKS.md)에 정의한다.

| ID | 결과 | 조건 | 의존 |
|---|---|---|---|
| W1 | AI와 무관하게 원문 제보가 한 번 저장되고 다시 열린다 | AC-1, AC-2, AC-3 | — |
| W2 | 추가 원문·정정이 버전과 종료 상태를 지키며 누적된다 | AC-3, AC-4, AC-5, AC-6, AC-7 | W1 |
| W3 | 실제 목록·상세·근거·Job 읽기가 사용자 범위를 지킨다 | AC-8, AC-9 | W1 |
| W4 | 영속 조사와 중단·실패·재시도가 동일 업무 효과를 보존한다 | AC-10, AC-27, AC-28, AC-29 | W1 |
| W5 | 실제 조회 근거와 run 내부 후보가 권한·출처를 지킨다 | AC-11, AC-12, AC-13, AC-14, AC-15 | W1 |
| W6 | 최신 문맥의 Responses 결과가 다섯 분기·상한·오류 계약을 지킨다 | AC-16, AC-17, AC-18, AC-26 | W4, W5 |
| W7 | 필수 확인 질문이 중복 없이 저장되어 지정자에게 보인다 | AC-5, AC-19, AC-20 | W6 |
| W8 | 지정 답변이 같은 질문과 새 조사로 원자적으로 이어진다 | AC-3, AC-5, AC-21, AC-22 | W2, W7 |
| W9 | 유효 후보만 F2에 전달되고 기존 작업을 재사용한다 | AC-23, AC-24, AC-26 | W6 |
| W10 | 준비 판단과 반려 보류가 사람의 업무 권한을 보존한다 | AC-25, AC-34 | W6 |
| W11 | 원문·질문·조사·실패·근거를 실제 상태대로 표시한다 | AC-9, AC-30, AC-31, AC-32 | W2, W3, W4, W7, W8, W9, W10 |
| W12 | 실제 F1 경계의 지속성·거부·원자성과 실행 모드를 확인할 수 있다 | AC-1~AC-34, 특히 AC-33, AC-34 | W1, W2, W3, W4, W5, W6, W7, W8, W9, W10, W11 |

## 관련 맥락과 완료 후 통합 평가

### 기존 요구와 완료 판단의 연결

| 기존 F1 요구 | 이 목표의 조건 | 외부 자원 준비 후 추가 확인 |
|---|---|---|
| AC-F1.1~1.3 | AC-1~7, AC-26, AC-33 | T2/T3/T7/T9의 실제 통합 환경 결과 |
| AC-F1.4~1.6 | AC-10~20, AC-26~28, AC-32 | L1a, L3, T3/T11 |
| AC-F1.7~1.9 | AC-19~22, AC-27, AC-33 | 같은 Request의 L1a→L1b, 실제 재시작 |
| AC-F1.10~1.11 | AC-23~25, AC-34 | L2, 실제 F2/F4 연결의 T10 |

F1 내부의 실제 UI/HTTP/DB 경계 확인은 AC-33의 필수 결과다. F0 전체 완료를 대신 요구하지 않는다. 필요한 최소 검증 구성을 마련하는 방식은 구현자가 정하되 공통 계약과 통합 소유권을 유지한다. F2/F4가 없는 환경의 계약 대체는 F1의 전달·rollback·권한 보존만 확인하며 실제 타 기능 성공으로 간주하지 않는다.

다음 항목은 계정 접근·다른 기능의 실제 서비스·공유 실행 환경을 필요로 하므로 **이 목표 산출물 완료 후 통합 평가**로 둔다. 기존 프로젝트 문서의 F1 완료 요구는 계속 유효하며, 아래가 없으면 “독립 F1 결과 확인”과 “F1 전체 통합 완료”를 구별해야 한다.

| 평가 항목 | 실제 관측할 결과 | 확인 위치·필요 경계 |
|---|---|---|
| L1a | 실제 도구 조회와 근거에서 지정자 Request가 저장됨 | [시험 계획 L1a](../../07_TEST_PLAN.md); live 계정·모델·F1 DB/UI |
| L1b | 같은 Request의 실제 답변으로 새 live run과 정식 Action 하나가 연결됨 | [시험 계획 L1b](../../07_TEST_PLAN.md); F2 실제 확정 서비스, 동일 Incident/Request 추적 |
| L2 | 활성 주 Action을 재조사해 실제 기존 ID·개수가 유지됨 | [시험 계획 L2](../../07_TEST_PLAN.md); 실제 F2 상태와 live 조사 |
| L3 | 실제 모델이 도구 ERROR를 입력받고 유효 BLOCKED를 선택함 | [시험 계획 L3](../../07_TEST_PLAN.md); live 호출 자체 실패는 통과가 아님 |
| T3b/T5/T6/T10의 실제 기능 연계 | 실제 ACK·반려·준비/해결 경계가 F1 최신성·보류·원문 보존과 일치 | [시험 계획](../../07_TEST_PLAN.md); F2/F3/F4 실제 서비스 |
| T8 및 제출 근거 | 같은 사건 전주기와 제출 버전·접근 근거 | F5 책임, [전주기 시연](../../09_DEMO_RUNBOOK.md); F1 코드 완료와 별개 |

최소 live 업무 run은 L1a/L1b/L2/L3의 네 번이며 API 호출 수와 다르다. 충분한 최초 입력의 질문 생략 대조 L4는 기존 문서대로 권장 평가이고 새로운 필수 작업으로 올리지 않는다. 현장 SOP 적합성·고객 평가·효과 측정·운영 안전 판단·배포/접수는 이 목표의 완료 조건이 아니다.

### 기준 문서

- [기능 명세 FR-02~05](../../02_FUNCTIONAL_SPEC.md), [도메인 상태·데이터·불변식](../../03_DOMAIN_MODEL.md), [HTTP·내부 확정 API](../../04_API_CONTRACT.md)
- [Agent·도구·최종 DTO·복구](../../05_AGENT_DESIGN.md), [S-01/S-02 화면](../../06_UI_SPEC.md), [시험 계획](../../07_TEST_PLAN.md)
- [개발 책임·경계](../../08_BUILD_PLAN.md), [합성 자료·기대값 격리](../../10_FIXTURES.md), [D01~D07](../../11_DECISIONS_AND_SOURCES.md), [기존 F1-a/F1-b 지시](../../12_CODEX_TASKS.md)
- [F3 교대 인계·인수 명세](../f3-handover/SPEC.md): 필수 질문·동일 업무 트랜잭션·ACK/분석 최신성·cutoff 연결. F3 AC 번호는 F1의 같은 번호와 별개다.

## Open Decisions

없음. Phase 1 질문은 모두 필수라는 사용자 결정을 이 목표의 정책으로 적용한다.

모델 ID·SDK 버전은 실제 지원을 확인할 구현 선택이다. F2의 정확한 기한 정책은 F2 서비스의 확인 항목이며 F1이 임의 지정하지 않는다. 공개 배포·계정 접근·제출 플랫폼 미확정 사항은 위 통합 평가의 환경 조건이며 F1 제품 동작의 새 결정을 만들지 않는다.
