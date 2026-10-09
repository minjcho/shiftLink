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

## F2-001 작업 승인·수행과 F4 준비 검사

| 항목 | 실제 수행 |
|---|---|
| 요청 | F2 구현 논의 후 사용자가 `Implement the plan.` 지시 |
| 합의 | F0는 재곤 담당 유지. F2와 함께 F4 종료 조건 검사 함수만 구현 |
| 기준 | minjcho, base 9de625e, 작업 후 dirty=true. 아직 구현 커밋·푸시 없음 |
| 코드 | 후보 확정·승인/반려·착수/결과 서비스, 주입형 FastAPI router/DTO, F2 테이블, Vue 패널/client, 종료 조건 검사 |
| 경계 | F0 공통 실행 앱·로그인·DB adapter·공유 상세 셸·migration head 중복 구현 안 함. F4 verification/case는 후속 |
| 검증 | 서버 72 PASS, PostgreSQL 13 SKIP, Web 17 PASS, Vue 타입/DDL 컴파일 PASS. 실제 앱·DB·F1 live 통합 NOT_RUN |
| 수정 | 폴링 시 입력/재시도 초기화 결함 수정, TypeScript/vue-tsc 호환 버전 고정, UUID 요청 키 타입 보완 |
| 사람 검토 | 계획의 담당/범위는 사용자 선택으로 확정. 구현 코드의 사람 검토·채택·실제 UI 확인은 아직 NOT_REVIEWED |
| 인계 | docs/16_F2_INTEGRATION.md의 F0 transaction/session/화면·F1 finalizer·F3 revision hook 연결 후 실제 통합 시험 |

실제 실행 명령과 미실행 제한은 TEST_RESULTS 4절에 기록한다. 기능 코드를 작성했다는 이유로 F2 전체를 DONE으로 바꾸지 않았다.

## F2-002 독립 데모 실행 (이후 F2-003에서 제거)

- 실제 요청: `F2 실행 ㄱ`, 이어 사용자가 `브라우저에서 독립 데모 확인 (권장)` 선택.
- 변경: 시험 경로에 loopback 메모리 preview 서버·Vue 진입 화면과 실행 명령을 추가했다. 실제 F2 router/service를 재사용하며 F0 인증·DB adapter는 만들지 않았다.
- 실행: Python API 127.0.0.1:8772, Vite 127.0.0.1:5173. 승인·착수·결과 제출을 실제 HTTP로 확인하고 초기 제안 상태로 되돌렸다.
- 검증: 서버 90 PASS(실제 PostgreSQL 13 포함), Web 17 PASS, preview 포함 타입 PASS. 실제 브라우저 조작은 도구 권한으로 NOT_RUN.
- DB 시험용 컨테이너는 종료했고 데모 서버 두 개는 사용자 확인을 위해 실행 상태로 유지했다. 데이터는 메모리 fixture이며 프로세스 재시작 시 사라진다.
- 사람의 화면 확인은 아직 기록되지 않았다. 미커밋·미푸시 상태이며 상세 검증 결과는 TEST_RESULTS 5절이다.


## F2-003 임시 데모 제거와 PR 준비

- 요청: 임시 화면 롤백, F2 PR 준비, 상세한 단위로 커밋 분리.
- 제거: 시험용 메모리 API 서버, Vue preview 진입 화면·설정·실행 스크립트, preview 전용 시험 5개, uvicorn 직접 의존성. 데모 서버 두 개 종료.
- 유지: F2 읽기/명령 계약, 승인 무결성, 종료 준비 검사, 후보 확정·승인·착수·완료 서비스, 주입형 HTTP API, PostgreSQL 테이블 제약, Vue 작업 패널과 독립 시험.
- 검증: 제거 후 Python 85 PASS(실제 PostgreSQL 13 포함), Web 17 PASS, Vue 타입 PASS. F0 DB adapter·세션·F1/F3·브라우저 E2E는 NOT_RUN.
- 커밋 분리: Python 시험 환경 → F2 계약·테스트 저장소 → F4 종료 준비 검사 → F2 업무 서비스·시험 → API·시험 → DB 제약·시험 → Web client·시험 환경 → 작업 패널·시험 → 인계·검증 문서.
- PR 범위: F0 연결 전 검토용 Draft. F2 전체 완료나 운영 배포로 표시하지 않는다. 임시 데모는 이전에 커밋되지 않아 삭제 파일이 PR diff에 나타나지 않으며 실행 이력은 보존한다.
