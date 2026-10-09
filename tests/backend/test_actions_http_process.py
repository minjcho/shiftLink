"""Real loopback HTTP and API process restart, using isolated PostgreSQL data."""
from contextlib import contextmanager
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import httpx
from sqlalchemy import text

from app.agent.finalizer import finalize
from app.core.ports import production_ports
from test_boundary_integration import execution, prepare, proposal


@contextmanager
def server(factory, settings):
    with factory() as tx:
        schema = tx.scalar(text('SELECT current_schema()'))
    url = factory.kw['bind'].url.update_query_dict({'options': f'-csearch_path={schema}'})
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    root = Path(__file__).resolve().parents[2]
    env = os.environ | {'PYTHONPATH': str(root / 'apps/api'),
        'DATABASE_URL': url.render_as_string(hide_password=False),
        'SESSION_SECRET': settings.session_secret, 'ALLOWED_ORIGINS': 'http://testserver',
        'APP_ENV': 'development', 'SESSION_COOKIE_SECURE': 'false', 'DEMO_ACCOUNT_SWITCH_ENABLED': 'true'}
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1',
            '--port', str(port), '--no-access-log'], cwd=root, env=env, stdout=log, stderr=log)
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=5,
                              headers={'Origin': 'http://testserver'}) as client:
                deadline = time.monotonic() + 10
                while True:
                    assert process.poll() is None, 'API exited before readiness'
                    try:
                        if client.get('/healthz').status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    assert time.monotonic() < deadline, 'API readiness timed out'
                    time.sleep(.05)
                yield client
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def test_real_http_completion_survives_api_restart(session_factory, settings, demo_ids):
    with server(session_factory, settings) as client:
        def login(account):
            response = client.post('/api/v1/demo/session', json={'account_key': account})
            assert response.status_code == 200

        def command(path, body, key=None):
            response = client.post('/api/v1' + path, json=body,
                headers={'Idempotency-Key': key or str(uuid4())})
            assert response.status_code in (200, 202), response.text
            return response

        login('reporter')
        incident = command('/incidents', {'equipment_id': demo_ids['equipment'], 'text': '실제 HTTP 제보'}).json()['data']['incident_id']
        ports = production_ports()
        context = prepare(session_factory, ports)
        dto = proposal(session_factory, context)
        result = finalize(session_factory, context.identity, execution(dto), ports)
        action = result['action_ids'][0]
        login('outgoing_supervisor')
        command(f'/actions/{action}/approval-decisions', {'decision': 'APPROVE', 'reason': '결과 기준 확인',
            'expected_version': 1, 'expected_incident_version': 3})
        login('maintainer')
        command(f'/actions/{action}/start', {'expected_version': 2, 'expected_incident_version': 4})
        key = str(uuid4())
        body = {'result': '결과 원문 보존', 'expected_version': 3, 'expected_incident_version': 5}
        completed = command(f'/actions/{action}/completion', body, key).json()
        assert completed['data']['verification_ready'] is True
        cookies = client.cookies
    with server(session_factory, settings) as client:
        client.cookies.update(cookies)
        detail = client.get(f'/api/v1/incidents/{incident}').json()['data']
        assert detail['status'] == 'PENDING_VERIFICATION' and detail['version'] == 6
        assert detail['actions'][0]['id'] == action
        replay = client.post(f'/api/v1/actions/{action}/completion', json=body,
                             headers={'Idempotency-Key': key})
        assert replay.status_code == 200 and replay.json() == completed
        assert replay.headers['Idempotent-Replayed'] == 'true'
