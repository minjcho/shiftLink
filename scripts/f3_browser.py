"""Verify F3 against real HTTP/Vue/PostgreSQL with synthetic business inputs.

Never reads .env, starts a model, or mutates a shared schema. Files used to request
API restart and database failure belong only to this local verification process.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = "postgresql+psycopg://f1_test:f1_test_local_only@127.0.0.1:55432/f1_test"


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_http(url, process):
    end = time.monotonic() + 30
    while time.monotonic() < end:
        if process.poll() is not None:
            raise RuntimeError(f"Verification server exited ({process.returncode})")
        try:
            with urlopen(url, timeout=1):
                return
        except HTTPError as exc:
            if exc.code == 401:
                return
        except (URLError, TimeoutError, OSError):
            pass
        time.sleep(0.1)
    raise RuntimeError("Verification server readiness timed out")


def stop(process):
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main():
    criterion = sys.argv[1] if len(sys.argv) == 2 else ""
    if criterion not in {"AC-1", "AC-16", "AC-17"}:
        print("usage: f3_browser.py AC-1|AC-16|AC-17")
        return 64
    sys.path[:0] = [str(ROOT / "apps/api"), str(ROOT / "tests")]
    from sqlalchemy import create_engine, select, text
    from sqlalchemy.engine import make_url
    from app.core.db import create_session_factory
    from app.core.models import Handover, HandoverAck, Incident
    from app.core.seed import SEED_IDS, seed_demo
    from handovers.helpers import seed_waits

    identity = uuid4().hex
    schema = "f3_browser_" + identity
    admin = create_engine(os.environ.get("F3_TEST_DATABASE_URL", TEST_DB))
    with admin.begin() as tx:
        tx.execute(text(f'CREATE SCHEMA "{schema}"'))
    url = make_url(os.environ.get("F3_TEST_DATABASE_URL", TEST_DB)).update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
    sessions = create_session_factory(url)
    logs = ROOT / ".cache/f3-browser" / identity
    logs.mkdir(parents=True)
    controls = logs / "controls"
    controls.mkdir()
    api_port, web_port = free_port(), free_port()
    env = os.environ.copy()
    env.update({"PYTHONPATH": str(ROOT / "apps/api"), "DATABASE_URL": url,
        "SESSION_SECRET": secrets.token_urlsafe(48), "AGENT_MODE": "fake",
        "ALLOWED_ORIGINS": f"http://127.0.0.1:{web_port}",
        "SHIFTLINK_API_PROXY": f"http://127.0.0.1:{api_port}",
        "SHIFTLINK_E2E_BASE_URL": f"http://127.0.0.1:{web_port}",
        "F3_BROWSER_CONTROLS": str(controls), "F3_BROWSER_FIXTURE": str(logs / "fixture.json"),
        "VITE_POLL_INTERVAL_MS": "1200"})
    python = str(ROOT / ".venv/bin/python")
    api = web = browser = None
    api_log = web_log = None
    try:
        subprocess.run([python, "-m", "alembic", "-c", "apps/api/alembic.ini", "upgrade", "head"], cwd=ROOT, env=env, check=True)
        with sessions.begin() as tx:
            seed_demo(tx)
        fixtures = {} if criterion == "AC-17" else seed_waits(sessions)
        (logs / "fixture.json").write_text(json.dumps({"cases": fixtures, "ids": SEED_IDS}))
        api_log = (logs / "api.log").open("w")
        web_log = (logs / "web.log").open("w")

        def start_api():
            child = subprocess.Popen([python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(api_port)], cwd=ROOT, env=env, stdout=api_log, stderr=subprocess.STDOUT)
            wait_http(f"http://127.0.0.1:{api_port}/api/v1/me", child)
            return child

        api = start_api()
        web = subprocess.Popen(["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", str(web_port), "--strictPort"], cwd=ROOT / "apps/web", env=env, stdout=web_log, stderr=subprocess.STDOUT)
        wait_http(env["SHIFTLINK_E2E_BASE_URL"], web)
        browser = subprocess.Popen(["npx", "playwright", "test", "tests/handovers.spec.ts", "--grep", f"\\b{criterion}\\b", "--output", str(logs / "ui"), "--reporter=line"], cwd=ROOT / "apps/web", env=env)
        completed = set()
        end = time.monotonic() + 210
        while browser.poll() is None:
            if time.monotonic() > end:
                raise RuntimeError("F3 browser verification timed out")
            for operation in ("restart", "seed", "db-fail", "db-restore"):
                request = controls / operation
                if not request.exists() or operation in completed:
                    continue
                if operation == "restart":
                    stop(api)
                    api = start_api()
                elif operation == "seed":
                    assert not fixtures, "Only the empty AC-17 input may be seeded"
                    fixtures = seed_waits(sessions)
                    (logs / "fixture.json").write_text(json.dumps({"cases": fixtures, "ids": SEED_IDS}))
                else:
                    with sessions.begin() as tx:
                        if operation == "db-fail":
                            tx.execute(text("ALTER TABLE handovers RENAME TO f3_unavailable_handovers"))
                        else:
                            tx.execute(text("ALTER TABLE f3_unavailable_handovers RENAME TO handovers"))
                completed.add(operation)
                (controls / (operation + ".done")).write_text("done")
            time.sleep(0.05)
        if browser.returncode != 0:
            return browser.returncode
        if criterion == "AC-1" and "restart" not in completed:
            raise AssertionError("AC-1 did not exercise API restart")
        if criterion == "AC-17" and not {"db-fail", "db-restore"}.issubset(completed):
            raise AssertionError("AC-17 did not exercise actual PostgreSQL read failure")
        with sessions() as tx:
            handovers = list(tx.scalars(select(Handover)))
            acks = list(tx.scalars(select(HandoverAck)))
            assert len(handovers) == 1
            if criterion in {"AC-1", "AC-16"}:
                assert acks
                assert tx.get(Incident, fixtures["work"]["incident"]).owner_id == SEED_IDS["incoming_supervisor"]
        result = {"criterion": criterion, "mode": "synthetic-input/real-F3-HTTP-PostgreSQL-Vue",
            "handover_ids": [h.id for h in handovers], "ack_ids": [a.id for a in acks],
            "incident_id": fixtures["work"]["incident"], "action_id": fixtures["work"]["action"],
            "controls": sorted(completed), "result": "PASS"}
        (logs / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"PASS {criterion}: evidence {logs.relative_to(ROOT)}/result.json")
        return 0
    finally:
        for child in (browser, web, api):
            stop(child)
        for handle in (api_log, web_log):
            if handle:
                handle.close()
        sessions.kw["bind"].dispose()
        with admin.begin() as tx:
            tx.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
