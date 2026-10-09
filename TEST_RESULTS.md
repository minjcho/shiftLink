# ShiftLink 검증 결과

## 1. 현재 결과

문서 검사와 앱 시험을 분리한다. 앱·DB·worker·실제 OpenAI 호출을 이번 문서 작업에서 실행하지 않았다.

| ID | 검사·시험 | 결과 | 근거·제한 |
|---|---|---|---|
| DOC-01 | 문서 구성·상대 링크·JSON 예시 | PASS | ZIP의 25개 경로 모두 존재. Markdown 28개에서 상대 링크 128개·JSON 예시 14개 검사. 파일 존재와 JSON 문법 검사이며 API 실행 아님 |
| DOC-02 | F0~F5 담당·상태·계약 교차 확인 | PASS | D01~D07·03/04/05/07/08/12 대조. F2 반환·질문 대기 run·최종 lease 만료 정리 규칙 정정. Mermaid 원문 두 파일 일치, 렌더 미수행 |
| ENV-01 | .env·변형 파일 제외 / .env.example 포함 | PASS | git check-ignore로 제외 경로 6개·허용 example 경로 2개 확인. 환경변수 26개 문서화·비밀값 빈 값 검사, 실제 .env 미생성 |
| DOC-03 | diff·신규 파일 공백·fence | PASS | git diff --check 통과. 신규 Markdown 개행·충돌 마커·fence·의도하지 않은 줄끝 공백 확인 |
| T1~T12 | 서버 권한·멱등·경합·복구·전주기 | NOT_RUN | 앱·시험 코드 미구현 |
| L1a/L1b/L2/L3 | 필수 실제 모델 4개 run | NOT_RUN | worker·모델 설정·실호출 미구현 |
| L4 | 충분한 입력 대조 | NOT_RUN | 선택 검증, 필수 통과 후 우선 권장 |
| E2E | 실제 UI·API·DB 전주기 | NOT_RUN | 앱 미구현 |
| DEPLOY | 다른 기기/세션의 외부 접근 | NOT_RUN | 배포 미수행 |

## 2. 새 실행 기록

위 문서 검사는 2026-10-09 Codex 문서 작성 중 Python 표준 라이브러리의 경로·정규식·JSON 검사와 Git 읽기 명령으로 수행했다. 검사 당시 문서 변경은 미커밋 상태였으며 앱 구현 commit은 없었다. 검사 범위는 본 문서 묶음이며 기존 `scripts/export_codex_history.py` 동작은 이번 범위에 포함하지 않았다. 문서 게시 이력은 Git commit과 PR에서 확인한다.

[시험 양식](templates/TEST_RESULTS.md)을 사용해 시각·전체 앱 SHA·dirty 여부·모드·모델·자료·명령·run ID·기대/실제·근거 경로를 기록한다. T-ID의 하위 사례를 따로 기록해 일부 성공을 전체 성공으로 묶지 않는다. 이전 FAIL은 지우지 않고 수정 후 결과를 추가한다.

## 3. 판정 규칙

NOT_RUN은 실행하지 않음, PASS는 명시된 조건을 실제 만족, FAIL은 실제 실행 후 기대 미충족, BLOCKED는 외부 조건으로 실행/완료할 수 없음을 뜻한다. 문서 검사 PASS는 앱이나 모델 시험 PASS가 아니다.


## F1 구현 중 직접 확인과 중단 — 2026-10-09T12:43:14.951726+09:00

다음은 구현 중 직접 실행 결과이며 Seal의 커밋 기준 완료 증거가 아니다. 이후의 미검증 변경을 포함한 최종 WIP 전체 통과를 의미하지 않는다.

| 경계 | 명령/방식 | 마지막 관측 | 한계 |
| --- | --- | --- | --- |
| 접수 API·DB | pytest tests/backend/test_intake.py | 12 PASS | real PostgreSQL, 모델 미실행 |
| 실제 다중 연결 경합·F3 계약 rollback | pytest tests/backend/test_concurrency.py | 4 PASS | F3는 시험용 port 대체 |
| Agent·도구·lease·finalizer | pytest tests/backend/test_agent.py | 변경 전 50 PASS | 마지막 timeout/fence/Approval/readiness 변경은 NOT_RUN |
| 화면 상태 | npm run unit:ac -- 30 | 13 PASS | 컴포넌트/계약 검증 |
| 입력·세션·폴링 | npm run unit:ac -- 31 | 17 PASS | 네트워크/화면 대체를 사용하는 단위 검증 |
| 웹 빌드 | npm run build | PASS | 실제 사용자 흐름과 구별 |
| 실제 migration | Alembic upgrade head + seed | PASS | 독립 schema, PostgreSQL 17 |
| 실제 UI→HTTP→DB·프로세스 재시작 | scripts/f1_browser.py | BLOCKED | macOS Chromium MachPortRendezvous Permission denied 1100, 사용자 흐름 시작 전 중단 |
| Seal AC-1~34 | ha baseline/check | NOT_RUN | 완료 기록 없음, start/input/block만 기록 |
| L1a/L1b/L2/L3·타 기능 전체 통합 | 실제 모델/제품 서비스 | NOT_RUN | 독립 F1 완료와 별도 조건 |

Chromium 설치 전 첫 시도는 실행 파일 부재로 실패했고 설치 후 native 실행은 권한 오류로 중단됐다. 이 권한 오류는 재시도하지 않았다. 실제 API·worker·Vue 검증용 프로세스는 harness의 finally에서 정리했고 시험 schema도 삭제했다. 시험용 PostgreSQL 컨테이너는 재개를 위해 보존했다.

상세한 미완료 항목과 최종 상태는 docs/specs/f1-intake-investigation/PROGRESS.md를 따른다. 비밀값·원본 모델 추론은 기록하지 않았다.

추가 중단 상태: 신규 tests/backend/test_boundary_integration.py 21개 사례는 NOT_RUN이다. F3 별도 구현 디렉터리는 이번 F1 검증과 커밋에서 제외했다.
