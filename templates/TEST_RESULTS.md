# 테스트 실행 결과 양식 — v0.3

> 초기 상태: **NOT_RUN**. 이 파일은 양식이다. 실제 실행 후 별도 결과 파일에 채우며 측정값·PASS를 미리 작성하지 않는다. 기준은 [테스트 계획](../docs/07_TEST_PLAN.md)과 [fixture](../docs/10_FIXTURES.md)다.

## 1. 실행 식별

| 항목 | 실제 값 |
|---|---|
| trial_id / run_group_id | 미작성 |
| 실행자·검토자·실제 일시(시간대 포함) | 미작성 |
| 앱 commit 전체 SHA / working_tree_dirty | 미작성 / UNKNOWN |
| dataset_id / dataset_version / source 문서 hash | 미작성 |
| fixture 합성 시각 / 실제 실행 시각 | 미작성 / 미작성 |
| 기능 F0~F5 / 결정 D01~D07 / AC 참조 | 미작성 |
| 유형 | SERVICE / TOOL / WORKER / LIVE / E2E / SUBMISSION 중 실제 유형 |
| AGENT_MODE | 미확인 — fake / live / replay 중 실제 값 |
| model_id / SDK 버전 / prompt_version / tool_schema_version | 미작성 |
| config fingerprint / 검색 모드·자료 버전 | 미작성 |
| 단계 | 개발 / 필수 검증 / 선택 대조 / 회귀 중 실제 값 |
| 기대값·scenario ID를 모델 입력에서 분리했는지 | NOT_VERIFIED |
| replay 원본 run ID·원본 SHA·녹화 시각 | 해당 시 작성, 현재 미작성 |
| 기준 종료 지점 | 미작성 — 미해결 ACK / 최종 해결 등 실제 범위 |

`.env`·키·세션 토큰을 복사하지 않는다. fingerprint는 비밀값을 포함하지 않는 정규화된 설정과 버전으로 만든다.

## 2. 시도별 결과

| 시험 ID / trial | 관련 F·D·AC | mode | 실제 run/command IDs | 초기 상태·입력 | 기대 | 실제 DB·설명 | 결과 | 증거 경로 |
|---|---|---|---|---|---|---|---|---|
| 미작성 | — | — | — | — | — | — | NOT_RUN | — |

결과값은 **NOT_RUN / PASS / FAIL / BLOCKED**만 쓴다. 실행 오류·시간 초과·중단은 시도 내 사유로 남기고 필요한 검증을 끝내지 못했다면 PASS로 표시하지 않는다. BLOCKED는 실행 전제·환경 때문에 확인을 못한 경우이며 원인을 적는다. 실패 후 재시험해도 원래 시도 행을 보존한다.

부정 시험은 HTTP 오류만으로 통과 처리하지 않는다. 예상 거부, 업무 변화 0개, 원문 보존/거부 입력 보존 여부, event·receipt·Job 수를 함께 기록한다. fake·live·replay 결과를 같은 성능 모수로 합산하지 않는다.

## 3. 필수 검증 진행표

| ID | 범위 | 결과 | 실제 하위 시험 수 / 전체 | 근거 |
|---|---|---|---|---|
| T1 | 권한·승인 | NOT_RUN | — | — |
| T2 | 멱등성·고유키 | NOT_RUN | — | — |
| T3 | AI 최신성 | NOT_RUN | — | — |
| T4 | ACK·revision | NOT_RUN | — | — |
| T5 | 해결 gate·근거 | NOT_RUN | — | — |
| T6 | 최종 검증 경합 | NOT_RUN | — | — |
| T7 | 실패·budget·복구 | NOT_RUN | — | — |
| T8 | 같은 Incident 전주기 | NOT_RUN | — | — |
| T9 | 상태 유지 추가 원문의 버전 | NOT_RUN | — | — |
| T10 | 반려 차단 | NOT_RUN | — | — |
| T11 | stale worker 종료 | NOT_RUN | — | — |
| T12 | 인계 범위·중복 | NOT_RUN | — | — |
| 도구/DTO | schema·출처·분기 부정 시험 | NOT_RUN | — | — |
| L1a | 실제 조회→질문 | NOT_RUN | — | — |
| L1b | 실제 답변→Action 확정 | NOT_RUN | — | — |
| L2 | 실제 기존 Action 유지 | NOT_RUN | — | — |
| L3 | 실제 ERROR 수신→BLOCKED | NOT_RUN | — | — |
| L4 선택 | 충분한 입력 대조 | NOT_RUN | — | — |

필수 최소 계획은 3개 시나리오·4개 live 업무 run이다. 이는 실행 실적이 아니다. run 하나의 여러 모델 호출을 여러 독립 사례로 세지 않는다.

## 4. 실행별 상세 증거

- Incident / Action / Request / Job / event ID: 미작성
- input_version / 최종 Incident·Action version: 미작성
- Job attempt / lease 검증 결과: 미작성 — lease token 원문은 공개하지 않음
- 도구 선택·실제 반환 source ID·오류: 미작성
- 최종 decision / 생성·재사용 ID / 서버 거부 사유: 미작성
- 승인 payload hash / ACK revision·snapshot_version·ack_applied_version: 미작성
- completion_report / 검토자 / resolution_case: 미작성
- HTTP 응답 / DB snapshot / UI·녹화 근거: 미작성
- 재시작·경합 실행 순서와 관측: 미작성

모델 비공개 추론을 수집하지 않는다. tool trace와 짧은 사용자용 reason, 실제 저장 결과만 연결한다.

## 5. 수치와 해석

| 측정 항목 | 값 | 계산·범위·제한 |
|---|---|---|
| 계획 / 실제 시도 / 완료 / PASS / FAIL / BLOCKED / NOT_RUN | NOT_MEASURED | live·fake·replay 각각 집계 |
| 모델의 잘못된 설명·판단 | NOT_MEASURED | 어떤 근거/분기가 잘못됐는지 |
| 서버가 차단한 잘못된 변경 시도 | NOT_MEASURED | 거부 코드·버전·근거 |
| 실제 잘못 커밋된 업무 상태 | NOT_MEASURED | 앞 두 항목과 분리 |
| 중복 Request / Action / Job / case | NOT_MEASURED | 재사용 ID·실제 추가 행 수 |
| 인계 누락 / 잘못된 추가 / stale ACK 허용 | NOT_MEASURED | 서버 집합·snapshot·최신 버전 비교 |
| 필요한 / 불필요한 / 누락 질문 | NOT_MEASURED | 총 질문 수만으로 평가하지 않음 |
| run·모델·도구 시간 / 전체 경과 | NOT_MEASURED | 사람 대기와 재시도 포함 여부 명시 |
| 모델 호출 / 도구 호출 / claim attempt 수 | NOT_MEASURED | 실패·재시도도 실제 횟수 포함 |
| API usage / 미수집 호출 수 | NOT_MEASURED | usage 없음을 0으로 기록하지 않음 |
| 비용·통화·단가 출처·기준일 | NOT_MEASURED | 추정과 청구/크레딧 관측 구분 |

성공 run만 비용·지연에 포함하지 않는다. 소규모 합성 시험으로 사고 감소율·현장 절감률을 추정하지 않는다. ACK는 인수 기록이고 실제 이해도·안전 해소를 증명하지 않는다.

## 6. 실패·수정·재검증

| improvement_id | 실패 시험·증거 | 확인 원인 / 가설 | 수정 commit·설정 | 같은 조건 재시험 | 남은 리스크 |
|---|---|---|---|---|---|
| 미작성 | — | — | — | NOT_RUN | — |

[IMPROVEMENT_RECORD.md](IMPROVEMENT_RECORD.md)로 상세를 연결한다. 결과를 보고 oracle을 바꾸면 변경 이유와 비교 불가 범위를 적는다. 코드·모델·자료를 동시에 바꾼 경우 어느 변화의 효과인지 단정하지 않는다.

## 7. 공개·제출 확인

- 원본 증거 위치 / 공개본 위치: 미작성
- 인증 정보·개인정보 제외 검토자·시각: 미작성
- 발표 주장과 연결한 실제 시험·표본: 미작성
- 앱 commit과 실행·녹화 commit 일치: NOT_VERIFIED
- 다른 버전이면 차이·재검증 범위: 미작성
- Codex 작업과 사람 리뷰 기록: 미작성
- 미실행/실패 항목·제출 제한: 미작성

**최종 상태: NOT_RUN.** 문서가 작성됐다는 사실과 앱·live·E2E 검증 성공은 별개다.
