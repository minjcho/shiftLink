# F1 PR 후속 리뷰의 입력·목록·검색 보완

Status: Ready

## 목표와 범위

PR #6에서 답변이 남지 않은 후속 리뷰 네 항목을 현재 코드 기준으로 분류한다. 현재 F1의 입력·목록·검색 결함 세 항목은 고치고, 아직 연결되지 않은 F2 어댑터의 추가 Action 생성은 통합 전에 해결할 이슈로 남긴다. 기존 코드의 작은 수정 세 건이며 새 기능이나 기존 다섯 리뷰의 재설계가 아니다.

수정 전 기준 `c46d490`에서 `apps/api/app/features/intake/schemas.py`는 답변과 정정 참조를 동시에 허용한다. `apps/web/src/features/intake/IncidentList.vue`는 폴링마다 첫 페이지로 목록을 덮어쓴다. `apps/api/app/agent/tools.py`는 조회 설비 코드를 모든 후보 SOP에 덧붙여 실제 내용이 무관해도 검색 일치를 만든다. `apps/api/app/agent/finalizer.py`는 F2 반환 행과 기존 행을 검사하지만 호출 후 전체 Action 집합을 비교하지 않는다. 기본 `FeaturePorts`에는 F2 서비스가 연결되지 않았다.

앞선 [다섯 리뷰 수정 명세](../f1-review-fixes/SPEC.md)와 원래 F1 목표·기록은 보존한다. F2 제품 통합, 신규 Action slot, DB 마이그레이션·기존 데이터 보정, 검색을 AND 의미로 바꾸는 일, 실제 모델 평가·배포·병합은 범위 밖이다.

## 결정과 근거

- 현재 F1 호출에서 재현되는 입력·화면·검색 세 건은 즉시 수정한다. 추가 Action 건은 F2 연결 전 차단할 추적 이슈로 둔다. 근거: 사용자 “정합성 이슈나 이런거는 issue만 추가해주고 바로 수정이 필요한 부분들은 판단해서 수정 진행해줘”, 현재 `core/ports.py`와 API/worker의 기본 구성.
- 지정 답변과 원문 정정은 별도 입력으로 취급하고 둘을 동시에 지정하면 422로 거부한다. 근거: [F1 AC-4](../f1-intake-investigation/SPEC.md), 도메인 Message.kind 구분 및 [리뷰](https://github.com/minjcho/shiftLink/pull/6#discussion_r4226830471).
- 목록은 사용자가 읽은 페이지 수만큼 최신 cursor를 따라 다시 읽고 전체 성공 때 함께 반영한다. 필터 변경은 첫 페이지로 돌아간다. 근거: [목록 API](../../04_API_CONTRACT.md), [마지막 성공 화면 보존](../../06_UI_SPEC.md), [리뷰](https://github.com/minjcho/shiftLink/pull/6#discussion_r4226830492). 구현 선택은 사용자가 위임한 판단이다.
- 문서 검색은 실제 제목·본문과 기존 별칭 해석으로 점수를 계산한다. 실제 제목에 설비 코드가 있는 경우에는 그대로 일치할 수 있으며 기존 OR 검색 의미는 바꾸지 않는다. 근거: [Agent 검색 계약](../../05_AGENT_DESIGN.md), 현재 `search_score`, [리뷰](https://github.com/minjcho/shiftLink/pull/6#discussion_r4226830496).

## 사용 시나리오

| 종류 | 시나리오 | 조건 |
| --- | --- | --- |
| 경계 | 지정 질문에 답하면서 정정 참조도 보낸 요청은 저장되기 전에 거부되며 열린 질문과 원문은 그대로 남는다. | AC-1 |
| 흐름 | 사용자가 다음 페이지까지 읽은 사건 목록을 폴링 뒤에도 같은 조회 범위에서 확인한다. | AC-2 |
| 경계 | 여러 페이지 갱신의 일부만 실패하거나 필터·계정이 바뀌면 부분 목록과 오래된 응답이 현재 화면을 덮어쓰지 않는다. | AC-3 |
| 흐름 | 조사 도구가 설비 코드와 검색어를 보냈을 때 실제 자료의 일치만 근거로 반환한다. | AC-4 |
| 유지 | 정상 답변·정정·일반 기록, 멱등 재전송·권한·버전·세션·lease와 기존 검색 범위·상한을 유지한다. | AC-1, AC-3, AC-4, AC-5 |
| 경계 | 현재 연결되지 않은 F2가 반환 외 Action을 생성할 수 있는 문제를 통합 담당자가 재현 근거와 해결 조건이 있는 이슈로 확인한다. | AC-6 |

## Acceptance Criteria

- **AC-1** 실제 HTTP에서 `reply_to_request_id`와 `correction_of`를 모두 non-null로 보내면 `422 VALIDATION_ERROR`를 받는다. Message·Request·Incident 버전·이벤트·Job·receipt에 후속 효과가 없으며, 같은 키로 정상 답변·정정·일반 기록을 보내는 기존 동작은 유지된다.
- **AC-2** 실제 브라우저와 HTTP·DB 목록 경계에서 20개를 넘는 사건을 다음 페이지로 읽은 뒤에도 폴링이 첫 페이지만 남기지 않는다. 갱신은 서버의 최신 순서를 따르고 같은 ID가 중복 표시되지 않는다.
- **AC-3** 갱신 중 일부 페이지가 실패하면 이전 전체 목록·cursor·마지막 성공 시각을 보존한다. 폴링과 다음 페이지 요청이 서로 결과를 버리지 않으며 필터 변경은 새 첫 페이지부터 시작한다. 계정 변경 후 이전 조회를 반영하거나 이전 쓰기를 자동 재전송하지 않는다.
- **AC-4** 실제 저장 문서에서 제목·본문에 일치가 없는 후보가 조회 설비 코드 때문에 검색되지 않는다. 결과가 없으면 EMPTY와 빈 source_refs이며 실제 제목·본문·별칭 일치는 유지된다. 동일 사업장·승인·설비 적용 범위, 결정적 동점 정렬, 개수·발췌 상한과 ERROR 구분을 유지한다.
- **AC-5** 기존 불확실한 접수 복구의 키·본문 보존과 동일 receipt 재사용, 정상 제보·지정 답변·재시작 후 같은 원문 조회, 기본·비기본 API prefix 동작은 유지된다. 공유 DTO·enum·마이그레이션·기존 저장 데이터는 변경하지 않는다.
- **AC-6** F2 어댑터의 반환 외 Action 추가 가능성에 대해 원 리뷰·기준 코드·재현 범위·영향·통합 전 해결 조건을 담은 이슈가 존재한다. 이 후속 수정에서 F2 통합이나 해당 정합성 문제를 해결했다고 표시하지 않는다.

## 관련 맥락

- [PR #6](https://github.com/minjcho/shiftLink/pull/6), [추가 Action 리뷰](https://github.com/minjcho/shiftLink/pull/6#discussion_r4226830480), [F1/F2 통합 전 해결 이슈 #11](https://github.com/minjcho/shiftLink/issues/11).
- [도메인 계약](../../03_DOMAIN_MODEL.md), [API](../../04_API_CONTRACT.md), [Agent](../../05_AGENT_DESIGN.md), [UI](../../06_UI_SPEC.md).
- 실제 모델 품질·모델별 문맥 한도와 F2/F3/F4 제품 전주기는 별도 통합 평가다. 이번 입력·화면·검색 변경의 결과와 혼동하지 않는다.

## Open Decisions

없음. 즉시 수정과 이슈 분류는 사용자 위임에 따른 위 결정을 적용한다.
