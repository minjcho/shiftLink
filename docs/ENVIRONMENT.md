# 환경 설정과 실행 준비

v0.3 구현 문서 · 2026-10-09

F0 설정 로더·Compose·마이그레이션·기본 seed를 구현했다. 로컬 실행은 [F0 실행 문서](17_F0_FOUNDATION.md)를 따른다. 생성기는 세션/DB 비밀값을 무작위로 만들며 기존 파일을 덮어쓰지 않는다.

```sh
python3 scripts/setup_env.py
docker compose up --build -d
```

기존 `.env`가 있으면 덮어쓰지 말고 누락된 키만 로컬에서 보완한다. API 키·세션 비밀값은 `.env`에만 채우고 로그·작업 기록·브라우저 번들에 노출하지 않는다.

## 1. 변수 계약

| 변수 | 예시·기본값 | 읽을 구성요소와 검증 |
|---|---|---|
| APP_ENV | development | API/worker. development 또는 production |
| WEB_PORT | 5173 | 로컬 Compose의 Web 공개 포트. 변경 시 ALLOWED_ORIGINS도 함께 수정 |
| APP_HOST / APP_PORT | 0.0.0.0 / 8000 | API 바인딩. 포트 1~65535 |
| APP_TIMEZONE | Asia/Seoul | 표시·교대 계산. DB 시각은 UTC |
| ALLOWED_ORIGINS | http://localhost:5173 | API의 쉼표 구분 정확한 origin 목록. 쿠키 인증에서 wildcard 금지 |
| SESSION_SECRET | 빈 값 | API. 실행 전 최소 32바이트 무작위 비밀값 필요 |
| SESSION_COOKIE_SECURE | false | localhost HTTP 예시. 공개 HTTPS 배포에서는 true |
| DEMO_ACCOUNT_SWITCH_ENABLED | true | 개발용 계정 전환. 공개 배포는 false, 별도 접근 제한 세션 필요 |
| POSTGRES_DB / POSTGRES_USER | shiftlink / shiftlink | DB 컨테이너 로컬 초기화 |
| POSTGRES_PASSWORD | replace_for_local_development | 실제 사용 전 로컬에서 교체. 공개 배포에서 예시값 거부 |
| DATABASE_URL | postgresql+psycopg://…@db:5432/shiftlink | API/worker. Compose에서는 db, 호스트에서 실행하면 localhost. 비밀번호 변경 시 URL도 함께 수정 |
| OPENAI_API_KEY | 빈 값 | worker만 사용. live 모드 시작 전 필수, 브라우저 전달 금지 |
| OPENAI_AGENT_MODEL | 빈 값 | 함수 호출·구조화 출력·한국어·지연을 실제 계정에서 확인 후 고정 |
| AGENT_MODE | live | live/fake/replay. fake는 자동 시험 전용, replay는 실제 실행 재생으로 표시 |
| AGENT_RUN_DEADLINE_SECONDS | 60 | run 전체 시간. 개별 호출·재시도도 남은 시간 안에서 종료 |
| AGENT_MAX_MODEL_CALLS | 7 | 재시도·형식 보정 포함 run 전체 호출 한도 |
| AGENT_MAX_TOOL_CALLS | 6 | run 전체 도구 실행 한도 |
| AGENT_MAX_OUTPUT_TOKENS | 2000 | 모델 호출당 출력 토큰 상한. 실제 모델 지원 확인 |
| SEARCH_MAX_CHUNKS | 5 | 검색 결과당 최대 chunk 수 |
| SEARCH_MAX_CHUNK_CHARS | 2000 | 모델에 전달할 chunk별 본문 상한. 원문 저장은 자르지 않음 |
| WORKER_POLL_INTERVAL_SECONDS | 2 | 미처리 DB Job 탐색 간격 |
| JOB_LEASE_SECONDS | 90 | claim 유효시간. 초기값은 run deadline보다 길게 설정 |
| JOB_MAX_ATTEMPTS | 3 | 최초 실행 포함 Job 전체 실행 시도 상한 |
| VITE_API_BASE_URL | /api/v1 | 브라우저의 동일 출처 API 경로 |
| VITE_POLL_INTERVAL_MS | 2000 | 실행 중 UI polling 간격 |

환경변수는 F0 설정 로더가 타입과 범위를 검사한다. 숫자는 양수여야 하며 `JOB_LEASE_SECONDS > AGENT_RUN_DEADLINE_SECONDS`가 아니면 시작 오류로 처리한다. live worker는 빈 API 키·모델을 허용하지 않는다. fake로 자동 전환하지 않는다. API는 모델 장애와 별개로 접수 원문을 저장할 수 있어야 한다.

## 2. 기능 연결 시 확인할 일

1. F0가 위 변수 이름으로 설정 로더와 Compose를 제공한다. 비밀값이 없는 공개 설정만 Web에 전달한다.
2. API와 worker는 같은 DB·도메인 코드·마이그레이션을 사용한다. 마이그레이션 실행 주체는 하나로 둔다.
3. Web 개발 서버와 배포 프록시는 `/api/v1`을 API로 전달한다. 환경에 따라 쿠키·Origin 검사를 실제 확인한다.
4. F1이 실제 계정의 모델 smoke test를 실행하고 `TEST_RESULTS.md`에 모델·소요 시간·결과를 남긴다. 모델 이름을 임의로 사용 가능하다고 가정하지 않는다.
5. README와 F0 인계 문서에 실제 설치·부팅·시험 명령을 기록했다. 현재 worker는 만료 복구만 수행하며 F1 live handler 등록 전 모델 호출/Job claim을 하지 않는다.

## 3. Git 제외 확인

```sh
git check-ignore -v .env .env.local apps/api/.env apps/web/.env.local
git check-ignore .env.example
git ls-files -- .env .env.local
```

첫 명령은 ignore 규칙을 보여야 한다. 두 번째 명령은 출력 없이 종료 코드 1이어야 하며 이는 `.env.example`이 무시되지 않는다는 뜻이다. 세 번째는 비어 있어야 한다. `.gitignore`는 이미 추적 중인 파일을 자동으로 제거하지 않으므로, 이후 추적 비밀값이 발견되면 노출 범위부터 확인한다.

## 4. 비용과 배포 상태

모델 호출 수·시간·출력·검색 길이 제한은 비용 폭증을 줄이기 위한 초기 설계값이다. 금액 한도 보장을 의미하지 않는다. 실제 모델과 계정 가격·usage를 기준으로 예상 비용을 측정하고 반복 시험 횟수를 결정한다. 배포 위치와 공개 데모 인증 방식은 아직 미정이며 [제출 인덱스](../SUBMISSION.md)에 기록한다.
