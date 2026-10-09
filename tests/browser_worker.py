"""Deterministic model transport for the real browser/HTTP/PostgreSQL check only.

This source is not imported by the runtime worker. It does not implement F2/F4.
"""
from __future__ import annotations

import json
import time

from app.agent.runner import ModelReply, ScriptedTransport
from app.agent.worker import run_once
from app.core.config import Settings
from app.core.db import create_session_factory
from app.core.ports import FeaturePorts


def ask_for_source(kwargs):
    context = json.loads(kwargs['inputs'][1]['content'])
    return ModelReply(output=[{
        'type': 'function_call', 'name': 'get_equipment_context', 'call_id': 'browser-context',
        'arguments': json.dumps({'equipment_id': context['incident']['equipment_id']}),
    }])


def conclude(kwargs):
    context = json.loads(kwargs['inputs'][1]['content'])
    refs = [context['messages'][0]['source_ref']]
    answered = any(row['status'] == 'ANSWERED' for row in context['requests'])
    dto = {
        'facts': [{'text': context['messages'][0]['text'], 'kind': 'HUMAN_STATEMENT', 'source_refs': refs}],
        'hypotheses': [], 'missing_information': [] if answered else ['기록한 점검 범위'],
        'decision': 'BLOCKED' if answered else 'ASK_USER',
        'questions': [] if answered else [{
            'question': '기록한 점검의 범위를 알려 주세요.', 'purpose_code': 'VERIFY_SCOPE',
            'target_user_id': context['allowed_question_target_ids'][0], 'source_refs': refs,
        }],
        'selected_draft_id': None, 'existing_request_ids': [], 'existing_action_ids': [],
        'source_refs': refs,
        'reason': '시험용 답변 수신 확인. 실제 모델과 F2 통합은 별도입니다.' if answered else '시험용 지정 질문입니다.',
    }
    return ModelReply(output=[], text=json.dumps(dto, ensure_ascii=False))


def main():
    settings = Settings.from_env()
    if settings.agent_mode != 'fake':
        raise RuntimeError('The browser test worker requires explicit fake mode')
    sessions = create_session_factory(settings.database_url)
    while True:
        run_once(sessions, settings, FeaturePorts(), model_adapter=ScriptedTransport([ask_for_source, conclude]),
                 metadata={'verification_boundary': 'real-ui-http-postgresql', 'model_boundary': 'fake', 'run_group_id': 'ac33-browser'})
        time.sleep(0.05)


if __name__ == '__main__':
    main()
