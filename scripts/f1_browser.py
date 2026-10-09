"""Run AC-33 with isolated PostgreSQL, real HTTP, Vue and separate fake worker.

Never loads .env. The model double lives under tests and is identified as fake.
The browser requests a process restart through a local test-only file, not an API.
"""
from __future__ import annotations

import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
TEST_DB = "postgresql+psycopg://f1_test:f1_test_local_only@127.0.0.1:55432/f1_test"


def port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_http(url: str, process: subprocess.Popen, timeout: float = 25) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if process.poll() is not None:
            raise RuntimeError(f"Server exited before readiness ({process.returncode})")
        try:
            with urlopen(url, timeout=1):
                return
        except HTTPError as exc:
            if exc.code in (401, 403):
                return
        except (URLError, TimeoutError, OSError):
            pass
        time.sleep(0.1)
    raise RuntimeError("Server readiness timed out")


def stop(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> int:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from app.core.db import create_session_factory
    from app.core.seed import seed_demo

    base_url = os.environ.get("TEST_DATABASE_URL", TEST_DB)
    schema = "f1_browser_" + uuid4().hex
    engine = create_engine(base_url)
    with engine.begin() as tx:
        tx.execute(text(f'CREATE SCHEMA "{schema}"'))
    database_url = make_url(base_url).update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
    sessions = create_session_factory(database_url)
    api_port, web_port = port(), port()
    python = ROOT / ".venv/bin/python"
    env = os.environ.copy()
    env.update({"PYTHONPATH": str(ROOT / "apps/api"), "DATABASE_URL": database_url,
                "SESSION_SECRET": secrets.token_urlsafe(48), "AGENT_MODE": "fake",
                "DEMO_NOW": "2026-10-09T03:00:00+00:00",
                "ALLOWED_ORIGINS": f"http://127.0.0.1:{web_port}",
                "SHIFTLINK_API_PROXY": f"http://127.0.0.1:{api_port}",
                "SHIFTLINK_E2E_BASE_URL": f"http://127.0.0.1:{web_port}",
                "SHIFTLINK_REQUIRE_RESTART": "1"})
    api = worker = web = browser = None
    logs = ROOT / ".cache/f1-browser"
    logs.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run([str(python), "-m", "alembic", "-c", "apps/api/alembic.ini", "upgrade", "head"],
                       cwd=ROOT, env=env, check=True)
        with sessions.begin() as tx:
            seed_demo(tx)
        with tempfile.TemporaryDirectory(prefix="shiftlink-f1-") as directory, \
             (logs / "api.log").open("w") as api_log, \
             (logs / "worker.log").open("w") as worker_log, \
             (logs / "web.log").open("w") as web_log:
            restart = Path(directory) / "restart.request"
            env["SHIFTLINK_RESTART_REQUEST"] = str(restart)

            def start_backend():
                api = subprocess.Popen([str(python), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(api_port)], cwd=ROOT, env=env, stdout=api_log, stderr=subprocess.STDOUT)
                worker = subprocess.Popen([str(python), "tests/browser_worker.py"], cwd=ROOT, env=env, stdout=worker_log, stderr=subprocess.STDOUT)
                wait_http(f"http://127.0.0.1:{api_port}/api/v1/me", api)
                return api, worker

            api, worker = start_backend()
            web = subprocess.Popen(["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", str(web_port), "--strictPort"], cwd=ROOT / "apps/web", env=env, stdout=web_log, stderr=subprocess.STDOUT)
            wait_http(env["SHIFTLINK_E2E_BASE_URL"], web)
            browser = subprocess.Popen(["npm", "run", "e2e:ac33"], cwd=ROOT / "apps/web", env=env)
            restarted = False
            end = time.monotonic() + 180
            while browser.poll() is None:
                if time.monotonic() > end:
                    raise RuntimeError("AC-33 browser execution timed out")
                if worker.poll() is not None:
                    raise RuntimeError("The separate F1 worker exited unexpectedly")
                if restart.exists() and not restarted:
                    stop(worker)
                    stop(api)
                    api, worker = start_backend()
                    Path(str(restart) + ".done").write_text("API and worker restarted; same PostgreSQL schema")
                    restarted = True
                time.sleep(0.05)
            if browser.returncode == 0 and not restarted:
                print("FAIL: browser did not request the required API/worker restart")
                return 1
            return browser.returncode
    finally:
        for child in (browser, web, worker, api):
            stop(child)
        sessions.kw["bind"].dispose()
        with engine.begin() as tx:
            tx.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
