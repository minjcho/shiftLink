# F1 web

Vue 3 / TypeScript의 접수·조사·지정 질문 화면이다. 업무 결과는 `/api/v1`의 실제 응답으로 표시한다. 작업 승인, 인계 ACK, 해결 확인 조작은 이 앱의 F1 구현 범위에 포함하지 않는다.

## 실행

```sh
npm ci
npm run dev
```

기본 주소는 `http://127.0.0.1:5173`이다. Vite는 `/api`를 `http://127.0.0.1:8000`으로 전달한다. API 주소는 `SHIFTLINK_API_PROXY`, 폴링 간격은 `VITE_POLL_INTERVAL_MS`로 바꿀 수 있다. 서버의 `ALLOWED_ORIGINS`에 실제 브라우저 origin을 설정한다. 서버 비밀값은 web 환경변수에 넣지 않는다.

세션은 서버 HttpOnly 쿠키를 사용한다. 데모 계정 전환은 서버 응답 이후 적용하며 작성 중 입력과 미확정 요청을 명시적으로 정리한다. 접수 불확실성에는 원래 내용·키로 사람이 재시도한다. 버전 충돌 후 최신 조회만으로 명령을 자동 재전송하지 않는다.

## 확인

```sh
npm run build
npm run unit:ac -- 30
npm run unit:ac -- 31
```

단위·컴포넌트 확인은 네트워크 대역을 사용하므로 실제 HTTP/DB 결과와 구별한다.

AC-33은 저장소 루트의 `scripts/f1_browser.py`로 실행한다. 이 harness는 격리 PostgreSQL schema, 실제 API, 별도 fake Agent worker, Vite를 시작하고 아래 브라우저 명령을 호출한다.

```sh
npm run e2e:ac33
```

직접 실행에는 harness가 제공하는 `SHIFTLINK_E2E_BASE_URL` 및 `SHIFTLINK_RESTART_REQUEST`가 필요하다. 시험은 UI 접수, 실제 ID/원문, API와 worker 재시작, 같은 질문의 지정자 답변, 재조회와 새 Job/run을 확인한다. fake 모드이며 실제 모델 호출이나 F2/F3/F4 전주기 성공을 입증하지 않는다. 브라우저 아티팩트는 Git 제외된 `test-results/`에 생성한다.
