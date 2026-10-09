# 11 설계 결정과 출처

v0.3 구현 문서 · 2026-10-09

## 1. 출처와 적용 범위

| ID | 자료 | 이번 문서에 적용한 범위 | 적용하지 않는 해석 |
|---|---|---|---|
| S1 | 사용자 제공 ShiftLink_Development_Docs_v0.2.zip | 01~15 문서 지도, 아키텍처, 작업·시험·제출 기록 양식 | 이전 enum·SQLite·자동 사건 연결·기술 계층별 분업을 현재 계약으로 적용하지 않음 |
| S2 | ShiftLink_Integrated_Development_Plan_v0_3.md 및 동명 DOCX | Phase 1 전주기, PostgreSQL, 단일 worker, 네 도구, 승인·인수·해결 의미 | 목표·예상 일정·시험 횟수를 실행 결과로 취급하지 않음 |
| S3 | 이 대화의 사용자 요청 | 개발 역할을 기능별로 구성, 구현 문서 생성, .env 제외와 .env.example 추가 | 앱 구현·배포·외부 제출까지 요청한 것으로 확대하지 않음 |
| S4 | [행사 공식 안내](https://luma.com/f7h7onav) | 17:00 KST 마감, 4분 예선 발표, 평가·제출 항목 | 세부 제출 플랫폼·권한·기록 형식의 확인을 대신하지 않음 |
| S5 | 아래 OpenAI 공식 문서 | Responses의 도구·구조화 결과·문맥·데이터 설정 | 계정별 사용 가능 모델·가격·지연·테스트 성공 증거 아님 |

S1·S2 로컬 원본은 사용자가 제공한 `Downloads/hackaton/OpenAI/DevDay_2026` 디렉터리에서 읽었다. 원본은 수정하지 않았다. 원문 파일을 저장소에 복사하는 대신 이 묶음에 필요한 계약을 재작성했다. 출처 생성·수령·저장소 반영 시점은 [PREWORK](../PREWORK.md)에서 구분한다.

## 2. 계약 보완 결정

다음은 v0.3 분석에서 확인한 해석 차이를 닫기 위해 이 문서 묶음에서 구체화한 구현 계약이다. 실제 제품이 이미 이 규칙을 구현했다는 뜻은 아니다.

| ID | 결정 | 이유와 영향 | 검증 |
|---|---|---|---|
| D01 | 새 메시지·답변·승인/반려·착수·결과·검증·ACK 등 새로운 업무 입력은 상태명 변화와 무관하게 Incident.version을 트랜잭션당 한 번 증가 | AI가 조사 중 들어온 일반 메시지를 놓친 채 최신성 검사를 통과하지 않게 함. 캐시·analysis·Job 상태만 변경되면 증가하지 않음 | T3, T6, T9 |
| D02 | REJECT와 RETURN은 INVESTIGATING + review_required=true + 사유/이벤트로 보류 | 승인 반려는 Action REJECTED, 검증 RETURN은 COMPLETED 보존. Phase 1에는 해제 API·generation 2가 없으며 자동 준비/해결을 차단. 읽기·추가 원문·인수는 가능 | T10 |
| D03 | Job 재시도는 같은 ID의 새 attempt와 새 AgentRun, lease token으로 소유권 검사 | 최종 업무 반영뿐 아니라 Job 성공/실패 갱신도 현재 token·attempt·RUNNING·유효 lease를 요구. 과거 run 보존, 오래된 worker의 덮어쓰기 차단 | T7, T11 |
| D04 | 허용된 같은 사업장의 순서 있는 교대 쌍과 Handover 고유키 사용 | 출발 책임자만 생성하고 지정 수신자가 ACK. 같은 인계 갱신은 이미 이전된 항목도 유지하되 다른 교대·사업장을 가져오지 않음. 자신의 ACK 버전만으로 즉시 재인수 요구하지 않음 | T4, T12 |
| D05 | 모든 도메인 쓰기 멱등성, Action 명령에는 부모 버전도 명시 | 키 범위는 site/actor/key, 입력 해시는 method/route/body 포함. 완료 응답 재사용을 상태 검사보다 먼저 수행. Action expected_version + expected_incident_version으로 화면의 두 버전을 검사 | T1, T2, T6 |
| D06 | 사람 해결에는 실제 필수 작업·유효 승인·답변·결과·근거·최신 버전·검토 사유·review_required=false 필요 | 빈 작업 집합과 사람 반려 상태가 해결되는 것을 방지. 완료 API가 작성자·시각을 가진 completion_report 근거를 생성 | T5, T8, T10 |
| D07 | 목표·문서 검사·서버 시험·live·배포·접수를 별도 기록 | L1a/L1b/L2/L3 최소 4 live run. L4 대조 검증은 필수 통과 후 우선 권장. 미실행은 NOT_RUN | 전체 시험·제출 인덱스 |

Action 명령의 `expected_incident_version`과 `review_required`, lease attempt/token은 v0.3의 의도를 실행 가능한 필드로 구체화한 추가 계약이다. `/demo/session`은 인증을 시작하는 로컬 데모용 명령이므로 도메인 멱등 키 적용의 명시적 예외다. Origin·허용 계정 검사와 세션 회전을 적용한다.

D03의 마지막 attempt가 종료 기록 없이 만료되면 시스템 복구 처리가 Job 행 잠금 아래 `RUNNING + lease 만료 + 최대 시도 도달`을 재확인해 Job과 해당 미종료 run을 `FAILED / ATTEMPTS_EXHAUSTED`로 정리한다. 이전 token을 폐기하고 업무·analysis·새 모델 호출은 반영하지 않는다. 이 제한된 복구 경로가 없으면 마지막 만료 Job이 영구 RUNNING으로 남을 수 있다. 일반 worker의 현재 lease 검사는 그대로 유지한다.

## 3. 세부 설계 선택

- **작업 단위:** 재곤 F1/F3, 민재 F2/F4의 초기 배정. 각각 화면부터 시험까지 연결한다. F0의 공유 계약과 마이그레이션 통합은 한 명이 조정한다.
- **질문 목적:** `VERIFY_SCOPE`, `VERIFY_RESULT`의 서버 허용 목록을 사용한다. 질문 대상자는 사건의 허용 담당자 집합에서 검사한다.
- **후속 검토:** Phase 1에서는 반려를 실패 없이 보존하는 데까지 구현한다. 보류 해제와 두 번째 작업 전주기는 Phase 2에 별도 계약·시험으로 추가한다.
- **재실행:** DB 업무 반영 한 번과 외부 모델 호출 한 번은 다른 보장이다. lease 복구 중 모델 호출이 중복될 수 있으므로 usage와 attempt를 남긴다.
- **설정 상한:** 도구 6회·모델 7회·run 60초·검색 5 chunk에 출력 2,000 tokens·chunk 2,000자를 초기값으로 추가한다. 정확도·지연·가격 검증 결과로 변경하며 성능 실측값으로 발표하지 않는다.
- **검색:** 실제 키워드·설비 별칭·문서 내용으로 조회한다. 과거 사례를 현재 설비의 관측 사실로 취급하지 않는다.
- **환경 파일:** `.env`·변형 파일은 로컬 전용, `.env.example`만 Git 대상. API 키·세션 비밀값·모델 ID는 빈 값으로 두고 실제 환경에서 채운다.

## 4. 공식 기술 자료

- [Function calling](https://developers.openai.com/api/docs/guides/function-calling): strict·required·nullable·additionalProperties·call_id·도구 결과 연결.
- [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs): 최종 `text.format` schema와 실패 분기.
- [Conversation state](https://developers.openai.com/api/docs/guides/conversation-state): 같은 run의 문맥 전달과 새 업무 이벤트의 문맥 재구성 참고.
- [Data controls](https://developers.openai.com/api/docs/guides/your-data): `store:false`를 전체 무보관과 동일시하지 않음.

이번 대화에서 Function calling과 Structured Outputs의 공식 본문을 확인했다. 나머지 링크는 v0.3이 제공한 참고 자료이며 계정 설정 확인을 대신하지 않는다. SDK·모델 선택과 실호출 검증은 구현 시 수행한다. reasoning 모델이 반환한 필요한 output 항목은 프로토콜에 맞춰 다음 요청으로 전달하되 내부 추론을 사용자 업무 기록으로 요구하거나 공개하지 않는다.

## 5. 미확정 사항

| 항목 | 결정 담당 | 결정 시점 | 현재 상태 |
|---|---|---|---|
| 실제 모델 ID·SDK 버전·계정 접근 | F1 | 최초 live smoke 전 | NOT_VERIFIED |
| 배포 위치·공개 데모 인증·비용 한도 | F0/F5 | 외부 공개 전 | NOT_DECIDED |
| 초기 기능 담당 수락·작업 시작 | 두 개발자 | 구현 시작 시 | 초기 배정안 |
| 제출 플랫폼·Codex 기록 형식·접근 권한 | F5 | 제출 준비 시작 시 | NOT_VERIFIED |
| 현장 SOP 적합성·고객 인터뷰·효과 | 파일럿 담당 | 운영 적용 전 | NOT_RUN |

문서 변경 시 이 결정의 이유와 영향받는 기능·API·시험을 함께 갱신한다. 과거 시험 결과는 당시 버전으로 보존한다.
