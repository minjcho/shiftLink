"""Real PostgreSQL/migrations + HTTP prerequisite commands + F4 browser verification.

F1 proposal uses its real tool/finalizer with a deterministic decision (no model).
F3 ACK uses the merged production router/service before F2 completion and F4 review.
"""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from uuid import uuid4

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from f1_browser import ROOT, TEST_DB, port, wait_http, stop
from app.core.db import create_session_factory
from app.core.seed import SEED_IDS, seed_demo
from app.agent.finalizer import finalize

sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'tests/backend'))
from f4_browser_app import make_ports
from test_boundary_integration import prepare, proposal, execution


def main():
    base_url = os.environ.get('TEST_DATABASE_URL', TEST_DB)
    schema = 'f4_browser_' + uuid4().hex
    engine = create_engine(base_url)
    with engine.begin() as tx:
        tx.execute(text(f'CREATE SCHEMA "{schema}"'))
    database_url = make_url(base_url).update_query_dict({'options': f'-csearch_path={schema}'}).render_as_string(hide_password=False)
    sessions = create_session_factory(database_url)
    api_port, web_port = port(), port()
    env = os.environ | {'PYTHONPATH': os.pathsep.join([str(ROOT / 'apps/api'), str(ROOT / 'tests')]),
        'DATABASE_URL': database_url, 'SESSION_SECRET': secrets.token_urlsafe(48), 'AGENT_MODE': 'fake',
        'ALLOWED_ORIGINS': f'http://127.0.0.1:{web_port}', 'APP_ENV': 'development',
        'SESSION_COOKIE_SECURE': 'false', 'DEMO_ACCOUNT_SWITCH_ENABLED': 'true',
        'SHIFTLINK_API_PROXY': f'http://127.0.0.1:{api_port}',
        'SHIFTLINK_E2E_BASE_URL': f'http://127.0.0.1:{web_port}'}
    logs = ROOT / '.cache/f4-browser'
    logs.mkdir(parents=True, exist_ok=True)
    restart = logs / f'{schema}.restart'
    env['SHIFTLINK_F4_RESTART'] = str(restart)
    api = web = browser = None
    try:
        subprocess.run([sys.executable, '-m', 'alembic', '-c', 'apps/api/alembic.ini', 'upgrade', 'head'], cwd=ROOT, env=env, check=True)
        with sessions.begin() as tx: seed_demo(tx)
        with (logs / 'api.log').open('w') as api_log, (logs / 'web.log').open('w') as web_log:
            def start_api():
                process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'f4_browser_app:build', '--factory',
                    '--host', '127.0.0.1', '--port', str(api_port)], cwd=ROOT, env=env, stdout=api_log, stderr=api_log)
                wait_http(f'http://127.0.0.1:{api_port}/healthz', process)
                return process
            api = start_api()
            with httpx.Client(base_url=f'http://127.0.0.1:{api_port}', headers={'Origin': env['ALLOWED_ORIGINS']}, timeout=10) as http:
                def login(account):
                    assert http.post('/api/v1/demo/session', json={'account_key': account}).status_code == 200
                def post(route, body):
                    response = http.post('/api/v1' + route, json=body, headers={'Idempotency-Key': str(uuid4())})
                    assert response.status_code in (200, 201, 202), response.text
                    return response.json()['data']
                targets = []
                ports = make_ports()
                for intent in ('resolve', 'return'):
                    login('reporter')
                    incident = post('/incidents', {'equipment_id': SEED_IDS['equipment'], 'text': f'F4 {intent} 브라우저 검증 원문'})['incident_id']
                    context = prepare(sessions, ports)
                    result = finalize(sessions, context.identity, execution(proposal(sessions, context)), ports)
                    action = result['action_ids'][0]
                    login('outgoing_supervisor')
                    post(f'/actions/{action}/approval-decisions', {'decision': 'APPROVE', 'reason': '확인한 범위와 결과 기준 승인',
                        'expected_version': 1, 'expected_incident_version': 3})
                    login('maintainer')
                    post(f'/actions/{action}/start', {'expected_version': 2, 'expected_incident_version': 4})
                    login('outgoing_supervisor')
                    handover = post('/handovers', {'from_shift_occurrence_id': SEED_IDS['outgoing_shift'], 'to_shift_occurrence_id': SEED_IDS['incoming_shift']})
                    item = next(x for x in handover['items'] if x['incident_id'] == incident)
                    login('incoming_supervisor')
                    ack = post(f'/handovers/{handover["id"]}/items/{item["id"]}/ack', {
                        'revision': item['revision'], 'snapshot_token': item['snapshot_token'], 'expected_version': item['snapshot_version']})
                    expected_version = ack['incident_version']
                    login('maintainer')
                    completed = post(f'/actions/{action}/completion', {'result': '지정 범위 확인 완료. 결과와 남은 사항을 보고합니다.',
                        'expected_version': 3, 'expected_incident_version': expected_version})
                    assert completed['verification_ready']
                    targets.append({'incident_id': incident, 'action_id': action, 'version': completed['incident_version']})
                env['SHIFTLINK_F4_TARGETS'] = json.dumps(targets)
                env['SHIFTLINK_F4_OWNER'] = 'incoming_supervisor'
            web = subprocess.Popen(['npm', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', str(web_port), '--strictPort'], cwd=ROOT / 'apps/web', env=env, stdout=web_log, stderr=web_log)
            wait_http(env['SHIFTLINK_E2E_BASE_URL'], web)
            browser = subprocess.Popen(['npx', 'playwright', 'test', 'tests/resolution.spec.ts'], cwd=ROOT / 'apps/web', env=env)
            deadline = time.monotonic() + 180
            restarted = False
            while browser.poll() is None:
                if time.monotonic() > deadline: raise RuntimeError('F4 browser timed out')
                if restart.exists() and not restarted:
                    stop(api); api = start_api(); restarted = True
                    Path(str(restart) + '.done').write_text('API restarted against the same PostgreSQL schema')
                time.sleep(.05)
            assert restarted or browser.returncode != 0, 'Required API restart did not occur'
            return browser.returncode
    finally:
        for child in (browser, web, api): stop(child)
        sessions.kw['bind'].dispose()
        with engine.begin() as tx: tx.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
