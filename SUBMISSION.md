# ShiftLink 제출 인덱스

상태: DRAFT / NOT_SUBMITTED. 아래는 실제 값을 기록할 양식이며 제출 증거가 아니다.

## 1. 제출 항목

| 항목 | 실제 값 | 상태 | 확인자·시각 |
|---|---|---|---|
| 등록 저장소 URL | 미확인 | NOT_VERIFIED | 미작성 |
| 평가 앱 전체 SHA | 미확인 | NOT_VERIFIED | 미작성 |
| Codex 기록 | [CODEX_WORKLOG](CODEX_WORKLOG.md), 최종 요구 형식 미확인 | DRAFT | 미작성 |
| 발표 PDF | 미생성 | NOT_CREATED | 미작성 |
| 데모 링크·접속 안내 | 미배포 | NOT_DEPLOYED | 미작성 |
| 사전·당일 구분 | [PREWORK](PREWORK.md) | DRAFT | 미작성 |
| 대상 권한의 링크 확인 | 미실행 | NOT_VERIFIED | 미작성 |
| 실제 접수 상태·식별자 | 미제출 | NOT_SUBMITTED | 미작성 |

## 2. 버전 대응

| 필드 | 실제 값 |
|---|---|
| evaluated_app_commit_sha | 미작성 |
| tested_app_commit_sha / working_tree_dirty | 미작성 / UNKNOWN |
| deployed_app_commit_sha | 미작성 |
| model_id / prompt_version / tool_schema_version | 미확인 |
| dataset_version / knowledge_version | 미작성 |
| AGENT_MODE / 비밀값 없는 설정 식별 | 미작성 |
| 실제 run·command·시험 결과 | NOT_RUN |
| presentation_revision / 영상 앱 버전 | 미작성 |
| 문서 전용 commit / 앱과의 차이 | 미작성 |

## 3. 현재 구현 범위

| 범위 | 상태 | 근거 |
|---|---|---|
| 개발 문서·환경 예시 | 작성·정적 검사 완료, 팀 검토 대기 | README 문서 지도와 TEST_RESULTS의 DOC/ENV 검사 |
| F0~F4 실행 앱 | NOT_IMPLEMENTED | 앱 구현 미수행 |
| 실제 OpenAI 실행·서버 시험 | NOT_RUN | TEST_RESULTS |
| 설비·SOP·교대·계정 | 합성 데이터 명세 | docs/10_FIXTURES.md, seed 실행 아님 |
| Phase 2/3 | NOT_IMPLEMENTED | 선택 범위 |
| 실제 센서·정비 시스템·설비 제어 | OUT_OF_SCOPE | 이번 제품 범위 아님 |

## 4. 일정과 미확정 안내

공식 [Luma 안내](https://luma.com/f7h7onav) 기준 17:00 KST 개발·제출 마감, 예선 발표·데모 4분이다. 제출 플랫폼·PDF 제한·Codex 원본 기록의 범위/전송 방식·심사자 접근 권한은 최종 참가 안내에서 확인해야 한다. 접수 확인을 마친 시각을 실제로 기록한다.

## 5. 체크리스트

- [ ] 등록 repo와 평가 SHA를 대상 권한으로 열었다.
- [ ] 시험·배포·영상·발표가 같은 구현 범위를 설명한다.
- [ ] 실제·합성 데이터·fake·replay·미구현을 구분했다.
- [ ] .env와 docs/history 원문이 Git·공개 첨부에 포함되지 않았다.
- [ ] 운영진 형식에 맞는 Codex 기록과 PREWORK를 준비했다.
- [ ] 실제 접수 완료를 확인했다.
