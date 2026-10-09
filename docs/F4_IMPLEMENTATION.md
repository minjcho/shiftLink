# F4 사람 검증·해결 이력

2026-10-09 · F2 통합 `ff1fb4e` 위의 F4 구현. PR #5의 기존 이력·독립 패널 보존 커밋 `92cab3f`도 통합했다. 초기 실행 코드 검증 기준은 `978b12c`다. 리뷰 준비 시 최신 main `c726425`를 `e551304`에 반영하고 서버282개·빌드를 재검증했다. F1/F2의 공통 ORM·세션·명령 영수증·준비 검사·화면 슬롯을 사용한다. 별도 DB나 앱을 만들지 않는다. 이후 F3가 병합된 main `5edcef1`을 반영해 실제 기본 구성의 F2/F3/F4를 함께 연결했다.

## 동작과 책임 경계

- `POST /api/v1/incidents/{id}/verification`: 현재 owner supervisor·최신 Incident 버전·PENDING_VERIFICATION·비어 있지 않은 검토 사유를 요구한다. RESOLVE는 F2와 동일한 준비 검사를 다시 수행한다.
- RESOLVE는 Incident RESOLVED, Verification, 불변 ResolutionCase, 이벤트, 필요한 인계 revision, CommandReceipt를 같은 트랜잭션에 저장한다. Incident 버전은 한 번 증가한다. Action이나 Job 성공을 해결로 대체하지 않는다.
- RETURN은 완료 Action·결과·근거를 보존하고 INVESTIGATING + review_required + 검토 사유를 남긴다. 준비 조건이 깨져도 반려할 수 있다. 후속 작업·generation 2·검토 차단 해제 API는 없다.
- 같은 키의 완료 응답은 현재 owner·상태·버전 검사 전에 재사용한다. 인증·사업장/대상 범위는 replay 전에도 확인한다. 새 검증 요청은 현재 owner를 다시 검사한다.
- 사건 잠금 → Action/Request 잠금 → 인계 hook 순서. 준비 검사와 저장 사이에 다른 업무 입력이 끼어들지 않는다. 인계 hook 또는 case INSERT 실패는 전체 업무 변경과 receipt를 rollback한다.
- `evidence_refs=[]`가 가능하다. 완료 보고가 기본 종료 근거이며 추가 근거는 F2의 같은 사건·사업장·적용 범위·본문 해시·SOP 승인 검사로 검증한다.

## 읽기와 화면

상세 응답의 `resolution`은 `ready`, `unmet_requirements`, `checked_version`, `can_resolve`, `can_return`, `latest_verification`, `case`다. 사건을 읽는 동안 공유 잠금을 잡아 상세 버전과 준비 조건을 일치시킨다. 명령 시 서버는 이를 다시 검사한다. 준비 검사 미연결을 성공으로 표시하지 않는다.

기존 상세의 `resolution` 슬롯에 승인 범위·완료 기준·완료 보고·부족 조건·검토 사유·추가 근거·해결/반려·검증 이력을 표시한다. 입력 중 버전 변경에는 재검토가 필요하다. 불확실한 요청/503/잘못된 성공 응답에는 동일 body/key를 유지한다. 저장 성공 후 상세 재조회 실패에는 새 명령 대신 재조회만 제공한다. 계정/사건 전환 후 늦은 응답은 폐기한다. F4 재검토는 Incident 조회 성공을 기준으로 하며 보조 Job 진단 조회 실패는 별도로 표시한다. Incident 조회 실패·세션 변경·더 최신 조회에 밀린 응답은 재검토 성공으로 처리하지 않는다. F1 명령 재검토의 기존 Job 조회 조건은 유지한다.

`GET /api/v1/cases?incident_id=...&cursor=...&limit=20`은 같은 사업장의 해결 이력을 반환한다. cursor는 필터·사업장에 묶이며 생성 시각/id 내림차순이다. 수정 endpoint는 없다. seed의 명시적 합성 과거 사례는 사건·검증 연결이 null일 수 있다.

case의 `snapshot_json`은 `schema_version=1`, `status=RESOLVED`, 사건·검토자·Verification·Action·Approval·Message·Request·Evidence의 해결 당시 값을 보존한다. 검토자 이름도 snapshot에서 읽는다. 가변 AI analysis·run 진단·인계 token은 복사하지 않는다. `evidence_refs`는 기본 completion report와 추가 종료 근거다. F1 `search_similar_incidents`는 이 사례를 `source_type=case`로 검색한다.

## 수정 파일 경계

- 서버: `apps/api/app/features/resolution/{schemas,service,router}.py`. 기존 `readiness.py`는 F2 구현을 그대로 재사용한다.
- 화면: `apps/web/src/features/resolution/`. 공통 API client·Command·오류 표시를 재사용한다.
- 공유 연결: `app/main.py`에 route·상세 기여, `App.vue`에 슬롯 조립, `IncidentDetail.vue`에 실패를 전파하는 refresh 계약과 해결 후 인수 대기 오표시 방지.
- 기존 `Verification`/`ResolutionCase` 모델과 `(incident_id, resolved_version)` 고유키를 사용한다. 신규 migration·enum 없음. F2의 0003 migration까지 적용한다.

## F3 통합

F3 PR #7이 병합된 main `5edcef1`을 통합했다. 공통 `production_ports()`의 `action_finalizer`·`readiness_evaluator`·`refresh_handover_items`와 F3/F4 route를 함께 유지한다. API와 worker는 같은 조립 함수를 사용한다. 상세 화면에는 F4 검증 패널과 F3 인수 요약/이동을 함께 연결하며, 해결 이후 F3는 과거 인계 조회만 제공한다.

초기 시험은 PR #7 `5486b8f`의 원본 패키지를 별도 export해 조립했으나, 현재 시험은 병합된 제품 코드와 기본 route/port만 사용한다. 별도 export·중복 route 등록·대체 ACK는 사용하지 않는다.

## 재현

기존 프로젝트 Python 의존성과 Web 의존성을 설치한 환경에서 수행한다. URL은 폐기 가능한 시험 PostgreSQL을 지정한다. 각 시험/harness는 고유 schema를 만들고 종료 시 삭제한다. 기존 데이터/volume은 건드리지 않는다. `.env`는 읽지 않는다.

```sh
F2_TEST_DATABASE_URL="$TEST_DATABASE_URL" python -m pytest -q tests/backend tests/handovers apps/api/tests/actions
npm --prefix apps/web test
npm --prefix apps/web run build
python scripts/export_contracts.py --check
PYTHONPATH=apps/api python scripts/f4_browser.py
```

`test_resolution_handover.py`는 기본 구성의 실제 F3/F2/F4 연결을 검사한다. F2 독립 DB 제약 13개는 F2_TEST_DATABASE_URL 없이는 SKIP하므로 반드시 시험 DB를 지정한다. SKIP을 PASS로 계산하지 않는다.

브라우저 harness는 실제 migration·세션·HTTP 제보, 결정론적 F1 도구/최종 확정, 실제 F2 승인/착수, 실제 F3 미완료 인수 ACK, F2 완료를 준비한다. 이후 Chromium에서 현재 owner의 RESOLVE/RETURN, case 조회, API 프로세스 재시작 후 조회를 실행한다. 선행 F2/F3 조작은 HTTP이며 해당 화면의 E2E는 아니다. 실제 모델 호출도 아니다.

전체 결과는 [TEST_RESULTS](../TEST_RESULTS.md). F1 질문/답변부터 모든 기능 화면으로 완주하는 전체 T8, 실제 모델 L1a/L1b/L2/L3, 배포/제출은 이번 F4 검증 범위 밖이며 NOT_RUN이다.

## MVP 후속 리뷰 범위

PR #12의 Job 재조회 결함은 이번 통합에서 수정했다. 나머지 P2(verification OpenAPI 필수 헤더 선언, 해결 후 snapshot 승인 내용 표시, case에 인수/ACK 이력 포함)는 후속 범위다. 현재 웹은 멱등 키를 전송하며 승인·ACK 원본 데이터는 보존된다. 이력 화면 보완 전에는 F4 전체 완료로 판정하지 않는다. case는 같은 사업장 조회, 인계 상세는 참여자 조회이므로 인수 정보를 case에 추가할 때 공개 범위를 함께 정해야 한다.
