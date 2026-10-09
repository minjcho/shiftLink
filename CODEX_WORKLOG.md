# Codex 작업 기록

대화 원문은 `docs/history/`에 로컬로 보관한다. 이 파일은 실제 요청·산출물·사람 검토·검증을 연결하는 공개용 요약의 초안이다. 사람의 검토 결과와 시험 성공을 추정하지 않는다.

## DOC-001 기능별 구현 문서 작성

| 항목 | 기록 |
|---|---|
| 요청 일자 | 2026-10-09 |
| 실제 요청 | 기술 계층별 분담을 기능별로 바꾸고, ZIP 형식을 참고해 구현 문서를 생성. .env 제외와 .env.example 추가 |
| 입력 자료 | ZIP v0.2 문서 구조, 통합 계획 v0.3, 앞선 분석에서 확인한 계약 보완점 |
| 수행 범위 | F0~F5 책임·명세·API·도메인·Agent·UI·시험·데모·제출 문서, 환경 예시와 ignore 규칙 |
| 앱 변경 | 없음. 앱·seed·시험 코드는 구현하지 않음 |
| 작성 방식 | Codex가 도메인/API, 기능/UI/작업, Agent/시험 문서를 병렬 작성하고 교차 검토 |
| 사람 검토 | NOT_REVIEWED. 이번 초안의 검토 결과는 실제 피드백 후 기록 |
| 구현/통합 commit | 문서 게시 이력은 Git commit/PR 참조. 앱 구현 commit 없음 |
| 문서 검사 | 링크·JSON·ZIP 구성·계약·ignore 검사 통과. TEST_RESULTS의 DOC/ENV 항목에 기록 |
| 런타임 검증 | NOT_RUN |

## 이후 기록

새 기능 작업은 [작업 양식](templates/CODEX_WORKLOG.md)의 work_id와 F/AC/T-ID로 기록한다. 제안된 프롬프트를 실제 실행한 지시처럼 기록하지 않는다. 사람이 수정하지 않은 코드를 수정했다고 꾸미지 않는다.


## F0-001 공통 실행 기반

- 실제 지시: main에서 F0 브랜치 생성·구현 순서를 제안한 뒤 사용자가 `ㄱㄱㄱ`로 진행 지시. 기존 재곤 담당 제안에서 이번 F0 구현은 민재가 진행하는 것으로 안내했다.
- 브랜치: main fast-forward 확인 후 feature/f0-foundation 생성. F2 PR #5와 코드는 그대로 유지했다.
- 변경: PostgreSQL shared schema/migration/seed, 설정·세션·권한·오류, 명령 receipt·잠금·버전, worker lease/복구, Vue 공통 client/DTO/화면, Compose 및 시험.
- 검증: Python 35 PASS, Web 7 PASS, 타입/빌드, migration 왕복, Compose·HTTP·API 재시작 후 세션 보존 PASS.
- 실패와 수정: Docker의 짧은 디렉터리 경로에서 .env 탐색 실패를 확인해 저장소 marker 기반으로 수정하고 container-layout 회귀 시험 추가.
- 경계: F1 live handler/접수·F2 DB adapter/업무 패널 연결·F3 인계·F4 verification은 구현하지 않았다. Worker는 F1 연결 전 만료 복구만 실행한다.
- 기존 .env를 보존하고 실행용 비밀값은 Git 제외 로컬 파일에 생성했다. 대화 원문은 공개 PR에 포함하지 않는다.
- 사람 코드 검토·실제 브라우저 확인: NOT_REVIEWED / NOT_RUN. 기능별 세부 커밋과 Draft PR로 인계한다.


## F0-002 PR 리뷰 P1 수정

- 실제 지시: 사용자가 F0 리뷰 확인 후 `수정 ㄱㄱ` 지시.
- 변경: Job lease 예약→최초 조사 상태 커밋→기준 version/run 생성으로 분리. 기존 Claim 반환 형식 유지. 최초 전이 이벤트·F3 hook의 transaction 및 lease 검사를 제공한다.
- 검증: 수정 전 새 회귀 1 FAIL을 확인하고, 수정 후 PostgreSQL 서버 전체 48 PASS. 기존 Web 코드는 변경하지 않았다.
- 인계: claim_job이 최초 상태 전환을 보장하므로 F1은 반환 Claim을 사용하고 별도 중복 전이를 하지 않는다. 준비 중 run 미생성 상태는 lease 재확보/최종 만료 복구로 처리한다.
- 범위: 코드·시험 수정과 검증 문서 갱신을 분리 커밋해 같은 F0 PR에 push한다. 리뷰 답글이나 thread resolve는 수행하지 않는다.
