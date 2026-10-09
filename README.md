# ShiftLink 개발 구현 문서

v0.3 구현 계약 · 2026-10-09 · F1·F3 구현 및 독립 검증 진행

ShiftLink는 모호한 점검 기록에서 확인할 내용과 남은 작업을 찾고, 사람의 승인·작업 수행·교대 인수·최종 해결 확인까지 같은 사건으로 연결하는 서비스다. F1 실행 앱과 개발 명세를 포함한다. F1의 독립 구현·검증 상태는 [Seal 실행 기록](docs/specs/f1-intake-investigation/PROGRESS.md), 설치·실행·외부 기능 경계는 [F1 실행 안내](docs/F1_IMPLEMENTATION.md)를 따른다. F3 구현과 실행 방법은 [F3 실행 안내](docs/F3_IMPLEMENTATION.md), 18개 완료 조건의 판정은 [F3 Seal 기록](docs/specs/f3-handover/PROGRESS.md)을 따른다. 전체 기능 통합·실제 모델·배포 상태는 별도로 기록한다.

## 먼저 읽을 문서

1. [프로젝트 목표](docs/01_PROJECT_PLAN.md)에서 Phase 1 전주기를 확인한다.
2. [기능별 개발 계획](docs/08_BUILD_PLAN.md)에서 맡을 기능과 의존성을 선택한다.
3. [도메인 계약](docs/03_DOMAIN_MODEL.md)과 [API 계약](docs/04_API_CONTRACT.md)을 함께 읽는다.
4. [기능별 Codex 작업 지시](docs/12_CODEX_TASKS.md)와 [시험 계획](docs/07_TEST_PLAN.md)을 해당 기능의 완료 조건으로 사용한다.
5. [.env.example](.env.example)을 참고하고 [환경 설정](docs/ENVIRONMENT.md)에 따라 로컬 `.env`를 준비한다. F1 앱은 프로세스 환경변수를 읽으며 `.env`를 자동으로 열지 않는다.

## 기능별 책임

다음은 개발을 시작할 때 사용할 초기 배정안이다. 각 담당자는 자신의 기능에 필요한 화면·API·DB·권한·시험을 함께 구현한다. 기술 계층별 전담으로 나누지 않는다.

| 작업 | 초기 담당 | 끝까지 책임질 결과 |
|---|---|---|
| F0 공통 실행 기반·계약 | 재곤 통합, 민재 검토 | 세션·seed·DB·공유 DTO·명령 처리 기반과 첫 화면 연결 |
| F1 접수·AI 조사·질문과 답변 | 재곤 | 원문 저장부터 실제 질문·답변·작업 후보 생성까지 |
| F2 작업 제안 확정·승인·착수·결과 | 민재 | 작업 생성 서비스부터 승인된 작업의 결과 제출까지 |
| F3 교대 인계·인수 | 재곤 | 미해결 목록·snapshot·ACK·책임 이전·재확인 |
| F4 최종 검증·해결 이력 | 민재 | 종료 조건 검사·사람 검증·해결 사례 조회 |
| F5 전주기 검증·제출 | 공동 | 같은 Incident의 전주기와 실행 근거·배포·제출 대응 |

공유 enum·마이그레이션 이력·공통 상세 응답·화면 shell은 한 번에 한 통합 담당자만 변경한다. 기능별 패널과 서비스는 분리해 병렬 작업한다. 개인의 실제 착수·완료 여부는 [PROGRESS.md](PROGRESS.md)에 별도로 기록한다.

## 전체 문서 지도

| 문서 | 내용 |
|---|---|
| [01 프로젝트](docs/01_PROJECT_PLAN.md) | 문제·사용자·Phase·기능 책임·완료 기준 |
| [02 기능 명세](docs/02_FUNCTIONAL_SPEC.md) | 기능별 입력·처리·실패·수용 조건 |
| [03 도메인 모델](docs/03_DOMAIN_MODEL.md) | 상태·데이터·불변식·버전·잠금·반려·복구 |
| [04 API 계약](docs/04_API_CONTRACT.md) | 요청·응답·세션·권한·오류·멱등성 |
| [05 Agent 설계](docs/05_AGENT_DESIGN.md) | 도구·최종 DTO·분기·예산·실패 처리 |
| [06 화면](docs/06_UI_SPEC.md) | 세 화면·기능 패널·역할별 조작·상태 표시 |
| [07 시험](docs/07_TEST_PLAN.md) | 결정론적 시험과 실제 모델 검증 |
| [08 개발 계획](docs/08_BUILD_PLAN.md) | 기능별 순서·병렬 작업·통합·범위 축소 |
| [09 시연](docs/09_DEMO_RUNBOOK.md) | 4분 발표·실행 순서·녹화 대안 |
| [10 Fixture](docs/10_FIXTURES.md) | 합성 설비·계정·SOP·시나리오 |
| [11 결정과 출처](docs/11_DECISIONS_AND_SOURCES.md) | 원본 적용 범위·계약 보완 D01~D07·미확정 사항 |
| [12 Codex 작업](docs/12_CODEX_TASKS.md) | 기능별 구현 요청과 검증·인계 형식 |
| [13 심사 근거](docs/13_JUDGING_EVIDENCE_MAP.md) | 주장·기능·시험·실제 제출 근거 대응 |
| [14 도입과 가치](docs/14_PILOT_AND_VALUE.md) | 파일럿·현장 가설·비용과 시간 측정 |
| [15 제출 절차](docs/15_SUBMISSION_RUNBOOK.md) | 버전 동결·접근 확인·실제 접수 확인 |
| [아키텍처](docs/ARCHITECTURE.md) / [Mermaid](docs/ARCHITECTURE.mmd) | 구성요소·실행 경계·기능 간 연결 |
| [환경 설정](docs/ENVIRONMENT.md) | 환경변수·비밀값·실행 전 점검 |
| [진행](PROGRESS.md) / [시험 결과](TEST_RESULTS.md) | 현재 상태·실제 실행 결과 |
| [Codex 작업 기록](CODEX_WORKLOG.md) / [개선 기록](IMPROVEMENT_RECORD.md) | 지시·검토·실패·수정·재검증 |
| [준비 자료](PREWORK.md) / [제출 인덱스](SUBMISSION.md) | 출처·반영 시점·제출값 |
| [작업 양식](templates/CODEX_WORKLOG.md) / [개선 양식](templates/IMPROVEMENT_RECORD.md) / [시험 양식](templates/TEST_RESULTS.md) | 새 기록을 작성할 빈 양식 |

## 기준과 문서 우선순위

사용자 지시 → 이 묶음의 결정 D01~D07 → 도메인 모델 → API 계약 → 기능·Agent·화면·시험·작업 계획 순으로 해석한다. 후순위 문서가 앞선 계약과 다르면 구현으로 임의 해결하지 말고 문서를 함께 정정한다.

제공된 ZIP v0.2의 파일 구성과 명세 형식을 참고했다. 기능·상태·스택·Phase는 통합 계획 v0.3을 기준으로 재작성했다. v0.2의 SQLite, 자동 사건 연결, 과거 Action 상태명, 기술 계층별 작업 지시를 함께 구현하지 않는다. [원본과 보완 결정](docs/11_DECISIONS_AND_SOURCES.md)에 차이를 기록했다.

## 로컬 기록과 비밀값

`docs/history/`와 `.env`, `.env.*`는 Git에서 제외한다. 환경 파일 중 `.env.example`만 Git 대상이며 비밀값은 비워 둔다. 대화 원문을 공개 기록으로 간주하지 않는다. 제출용 Codex 기록은 실제 작업과 사람 검토를 확인해 별도로 정리한다.
