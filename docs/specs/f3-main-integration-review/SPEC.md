# F3 main 통합과 리뷰 보완

Status: Ready

## 목표

F2 PR #5가 병합된 main에 F3 PR #7을 연결해 같은 Incident의 작업 승인·수행·교대 인수가 공통 기록으로 이어지게 한다. 승인 권한을 훼손하거나 통합을 막는 문제는 수정하고, 비치명적 리뷰는 별도 이슈에서 추적한다.

기존 코드의 여러 기능 경계를 연결하는 후속 목표다. [기존 F3 명세](../f3-handover/SPEC.md)와 당시 완료 기록은 보존한다. 이 목표의 완료는 알려진 모든 F3 결함이나 전체 Phase 1의 완료를 뜻하지 않는다.

## 현재 동작과 범위

분석 기준은 main `c726425`와 F3 PR #7 `5486b8f`다. main에는 F2 소스 `f053c58`이 병합돼 있다.

- main의 `apps/api/app/core/ports.py`는 작업 확정과 종료 준비 검사를 연결한다. F3의 `apps/api/app/main.py`, `apps/api/app/agent/worker.py`는 인계 갱신을 별도로 연결한다. 통합 후 세 기능이 API와 worker에서 함께 제공돼야 한다.
- `apps/api/app/agent/finalizer.py`는 기존 Approval의 내용을 검사하지만 새 Approval ID의 추가를 기존 집합과 비교하지 않는다. 후보 확정 경계가 사람의 승인을 추가·수정·삭제하지 못하도록 보완한다.
- main의 `apps/api/app/core/auth.py`는 교대 미배정 계정의 세션 생성과 사업장이 불일치하는 기존 세션을 거부한다. F3 시험은 현재 계약을 따라야 하며 인증을 완화하지 않는다.
- main의 `apps/web/src/features/intake/IncidentList.vue`는 읽은 목록 구간과 결과가 불확실한 접수 명령을 보존한다. `apps/api/app/features/intake/service.py`는 읽기 권한 범위 안의 최신 인계 요약을 결정적으로 선택한다. 이 동작을 F3 통합 뒤에도 유지한다.
- main의 `apps/api/app/agent/tools.py`, `apps/api/app/agent/jobs.py`는 같은 Incident의 근거 조회·발급을 공통 잠금 아래 처리한다. F3의 이전 실행 경로로 되돌리지 않는다.
- F3는 `apps/api/app/features/handovers/`, `apps/web/src/features/handovers/`에서 공통 ORM·세션·영수증과 상세 셸을 사용한다. 별도 사건·작업·인증 기반은 만들지 않는다.

포함 범위는 공통 기능 연결, 공유 파일 통합, 승인 경계 P1 수정, 현재 세션 계약에 맞는 F3 시험, 실제 기능 경계와 기존 동작의 검증, 리뷰별 근거와 이슈 연결이다.

제외 범위:

- F2 전체 작업 패널 연결은 기존 [이슈 #16](https://github.com/minjcho/shiftLink/issues/16)에서 추적한다. F2 독립 시험 기반의 광범위한 정리도 이번에 수행하지 않는다.
- 조회 Evidence만 늘어난 경우의 불필요한 revision, 동시 접수 사건의 최초 인계 이후 추가 표시, 이전 교대 구간의 영구 stale 표시는 후속 P2 이슈로 추적한다. 이번 완료 조건에 세 결함의 수정 완료를 포함하지 않는다.
- F4 사람의 최종 해결 확인, 실제 모델, 복수 작업·generation 2, 반려 해제, 배포·제출은 포함하지 않는다.

## 사용 시나리오

| 종류 | 시나리오 | 조건 |
| --- | --- | --- |
| 흐름 | F1 후보가 F2 작업으로 저장되고, 사건을 인수한 새 책임자가 승인한 뒤 기존 담당자가 착수·결과를 제출한다. 인계에서 변경된 작업과 결과를 다시 확인한다. | AC-1, AC-4, AC-5 |
| 경계 | 인계 갱신이 실패하면 승인·결과·버전·이벤트와 새 revision이 부분 저장되지 않는다. | AC-2 |
| 경계 | 후보 확정 경계가 기존 작업의 승인 이력을 추가·변경·삭제하려 하면 거부되고 원래 기록이 유지된다. | AC-3 |
| 경계 | 교대 배정이나 사업장 범위가 유효하지 않은 계정·세션은 인계·토큰·타인의 영수증을 얻지 못한다. | AC-6 |
| 유지 | ACK와 작업 결과 제출은 사건 해결을 대신하지 않으며, 담당자와 과거 승인·snapshot을 보존한다. | AC-4, AC-5, AC-9 |
| 유지 | F3 화면을 연결해도 목록 페이지, 불확실한 접수 복구, 계정 전환, 최신 인계 선택과 공통 API 계약은 유지된다. | AC-7, AC-8 |
| 유지 | 동일 사건의 겹치는 Agent 조회는 같은 출처·버전의 근거를 재사용하고 업무 상태를 바꾸지 않는다. | AC-7 |
| 흐름 | 리뷰 작성자는 각 지적에서 수정 근거 또는 후속 이슈를 확인하고 미수정 범위를 구별한다. | AC-10 |

## 계약과 제약

[결정 D01~D07](../../11_DECISIONS_AND_SOURCES.md), [도메인](../../03_DOMAIN_MODEL.md), [API](../../04_API_CONTRACT.md) 순으로 해석한다. 업무·이벤트·버전·필요한 인계 revision과 응답은 같은 트랜잭션에서 확정한다. 공통 잠금 순서, lease, 서버 principal·site·현재 owner·assignee 검사를 유지한다.

공유 enum·DTO·마이그레이션 이력·상세 셸은 main 기준으로 통합한다. 기존 스키마·사용자 설정·업무 데이터를 이전 F3 정의로 되돌리지 않는다. `.env`는 변경 대상이 아니다. 실제 저장 경계, 합성 모델 입력, 브라우저, 실제 모델의 검증 근거를 구별한다.

## 결정과 근거

| 결정 | 이유 | 출처 |
| --- | --- | --- |
| 별도 후속 명세를 사용한다. | 기존 F3 완료 기록과 이번 통합을 구별한다. | 사용자 답변 “별도 후속 명세 작성 (권장)” |
| 치명적 문제는 수정하고 나머지는 이슈로 추적한다. | 승인 권한과 핵심 연결을 우선 확보하고 미수정 범위를 명시한다. | 사용자 답변 “치명적 문제 즉시 수정, 나머지는 이슈” |
| F2가 반영된 main의 기반에 F3를 연결한다. | 실행 기반 중복과 기능 연결 누락을 막는다. | 사용자 요청, `docs/17_F0_FOUNDATION.md`, `apps/api/app/core/ports.py` |
| 후보 확정 전후 Approval 집합과 내용을 보존한다. | AI 실행 경계가 사람의 승인 권한을 취득하지 못하게 한다. | 도메인 INV-02·INV-04, [P1 리뷰](https://github.com/minjcho/shiftLink/pull/7#discussion_r4227086766) |
| 현재 인증과 main에서 해결된 네 동작을 보존한다. | 오래된 F3 기반과의 통합으로 인증·복구·동시성 문제가 재발하지 않게 한다. | `core/auth.py`, `agent/tools.py`, `agent/jobs.py`, `features/intake/service.py`, Web `IncidentList.vue`, 해당 PR 리뷰 |
| F2 화면과 미해결 P2 세 건은 후속으로 남긴다. | 사용자 심각도 처리 기준과 기존 기능 경계를 따른다. | 사용자 답변, 이슈 #16, 아래 P2 리뷰 세 건 |
| 실제 모델·F4 해결·배포·제출은 별도 공동 평가로 둔다. | 이번 출력의 기능 경계와 다른 기능·외부 환경의 완료를 혼동하지 않는다. | `docs/08_BUILD_PLAN.md`, D07 |

## Acceptance Criteria

- **AC-1** 기본 제품 구성의 실제 API·F1 업무 확정 경로·PostgreSQL에서 같은 Incident의 후보 반영, 정식 Action, F3 인수, 새 owner의 승인, 기존 assignee의 착수·결과와 인계 재확인이 연결된다. 재조회에서도 동일 식별자와 결과가 확인된다. 모델 결정은 명시적 합성 입력을 허용하되 실제 업무 반영·저장 경계를 대체하지 않는다.
- **AC-2** API와 worker 모두 작업 확정·종료 준비·인계 갱신을 함께 제공한다. 인계 항목이 있는 정상 업무가 F3 미연결로 실패하지 않는다. 인계 갱신 실패 시 업무·버전·이벤트·새 revision·완료 영수증이 부분 확정되지 않는다.
- **AC-3** Action 생성·재사용 여부와 관계없이 후보 확정 경계의 Approval 추가·수정·삭제·교체를 거부하고 기존 승인 집합·내용과 관련 업무 기록을 보존한다. 정상 신규 Action에는 승인이 없고 정상 재사용은 기존 승인을 유지한다.
- **AC-4** ACK는 owner와 owner_shift만 지정 수신자로 이전한다. Action assignee·업무 상태·승인과 질문 지정자·답변 상태는 유지된다. 이후 승인은 현재 owner만, 착수·결과는 기존 assignee만 수행한다. ACK·완료가 Incident 해결이나 review_required 해제로 기록되지 않는다.
- **AC-5** 일반 생성·ACK·후속 업무 변경에서 최초 cutoff와 공개된 snapshot·token·ACK는 보존된다. 자기 ACK는 새 revision을 만들지 않고 후속 승인·착수·결과는 최신 revision과 재확인 상태에 반영된다. 동일 완료 명령의 재전송은 응답을 재생하고 효과·버전을 중복 생성하지 않는다. 제외한 세 P2 재현 조건의 변경은 요구하지 않는다.
- **AC-6** 교대 미배정 계정의 세션 생성은 `422 SHIFT_ASSIGNMENT_MISSING`, 기존 세션의 사업장 불일치는 `401 UNAUTHENTICATED`, 세션의 교대 배정 제거는 `403 FORBIDDEN`으로 거부된다. 유효한 타 사업장·비참여자도 F3 객체 권한을 얻지 못한다. 거부 요청은 업무를 바꾸거나 제한된 인계 내용·token·영수증을 노출하지 않는다.
- **AC-7** main의 API 경로, 입력 상한, 필수 멱등 키, 응답·오류 형식, `Idempotent-Replayed` 노출, 세션 격리와 현재 lease 검사를 유지한다. 같은 Incident에서 서로 다른 실행이 같은 출처·버전의 근거를 동시에 조회해도 같은 Evidence를 재사용하고 Incident 업무 버전·owner·상태는 유지한다.
- **AC-8** 실제 F3 생성·조회·ACK 화면과 상세 링크를 사용할 수 있다. 기존에 읽은 목록 구간, 불확실한 접수의 동일 요청 복구, 세션 전환 후 이전 명령 차단, actions·resolution·history 슬롯을 유지한다. 상세의 인계 요약은 읽기 권한 범위 안에서 최신 항목을 결정적으로 선택한다.
- **AC-9** main의 사건·작업·승인·원문·세션과 F3 revision·ACK를 기존 공통 스키마에서 계속 읽고 사용할 수 있다. 초기 스키마·공유 모델을 중복 생성하거나 기존 기록·마이그레이션·사용자 설정을 삭제·회귀시키지 않는다.
- **AC-10** 리뷰 여덟 건마다 수정 근거, main 반영 근거 또는 후속 이슈를 연결한다. 미해결 P2 세 건은 재현 조건·영향·기대 동작·제외 범위가 있는 이슈로 추적하고 F2 화면은 기존 #16에 연결한다. 수정 완료와 이슈 이관, 실제 검증과 미실행을 구별한다.

## 관련 맥락

- [F3 PR #7](https://github.com/minjcho/shiftLink/pull/7), [병합된 F2 PR #5](https://github.com/minjcho/shiftLink/pull/5)
- [기존 F3 목표](../f3-handover/SPEC.md), [F0 연결 계약](../../17_F0_FOUNDATION.md), [시험 계획](../../07_TEST_PLAN.md)
- 후속 이슈: [#17 조회 Evidence](https://github.com/minjcho/shiftLink/issues/17), [#18 동시 접수 추가 표시](https://github.com/minjcho/shiftLink/issues/18), [#19 이전 교대 구간](https://github.com/minjcho/shiftLink/issues/19)
- 후속 P2 리뷰: [조회 근거와 revision](https://github.com/minjcho/shiftLink/pull/7#discussion_r4226624428), [동시 접수 추가 표시](https://github.com/minjcho/shiftLink/pull/7#discussion_r4226624432), [이전 교대 구간](https://github.com/minjcho/shiftLink/pull/7#discussion_r4227086759)

완료 후 공동 평가는 실제 모델을 통한 조사부터 F4 수신 owner의 최종 해결 확인까지의 전주기와 배포·제출이다. 기존 시험·제출 기록에서 별도로 확인하며 이번 완료 조건으로 계산하지 않는다.

## Open Decisions

없음.
