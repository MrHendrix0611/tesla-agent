"""V0.7 dashboard API security/integration tests; never call a remote LLM."""
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from web.server import create_app
from web.service import ApprovalBroker, TeslaService


class FakeProvider:
    model = 'offline-test'


class FakeUsage:
    def summary(self):
        return {'requests': 0, 'test': True}


class FakeRouter:
    def __init__(self):
        self.providers = [('groq', FakeProvider()), ('gemini', FakeProvider())]
        self.auto = True
        self.last_decision = None
        self.paid_approval_callback = None
        self.usage = FakeUsage()

    def generate(self, messages, tools=None, task_hint=None):
        prompt = str(messages[-1].get('content', ''))
        if 'Retorne APENAS um JSON' in prompt:
            return {'content': json.dumps({'steps': [
                {'description': 'Criar um arquivo calculadora.py', 'dependencies': []},
                {'description': 'Criar testes unittest', 'dependencies': [1]}
            ]}), 'tool_calls': []}
        return {'content': 'Resposta local de teste, sem acesso a nenhum modelo remoto.',
                'tool_calls': []}


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'hello.py').write_text('def ola():\n    return "Olá"\n', encoding='utf-8')
        (self.root / '.env').write_text('GROQ_API_KEY=sk_fake_private_file', encoding='utf-8')
        with patch('core.agent.LLMRouter', FakeRouter):
            from core.agent import Agent
            self.service = TeslaService(agent=Agent(), approval_timeout=2)
        self.app = create_app(self.service, secret='test-token-do-not-share')
        self.client = TestClient(self.app, base_url='http://127.0.0.1:8765')
        self.auth = {'X-Tesla-Token': 'test-token-do-not-share'}

    def test_frontend_and_health_without_auth(self):
        page = self.client.get('/')
        self.assertEqual(page.status_code, 200)
        self.assertIn('Tesla Agent', page.text)
        self.assertIn('test-token-do-not-share', page.text)
        self.assertEqual(self.client.get('/ui/app.js').status_code, 200)
        self.assertEqual(self.client.get('/ui/styles.css').status_code, 200)
        self.assertEqual(self.client.get('/ui/../service.py').status_code, 404)

    def test_auth_origin_host(self):
        self.assertEqual(self.client.get('/api/status').status_code, 401)
        self.assertEqual(self.client.get('/api/status', headers=self.auth).status_code, 200)
        self.assertEqual(self.client.get('/api/status', headers={'X-Tesla-Token': 'wrong'}).status_code, 401)
        forbidden = dict(self.auth, Origin='https://malicious.example')
        self.assertEqual(self.client.post('/api/project', json={'path': str(self.root)}, headers=forbidden).status_code, 403)
        self.assertEqual(self.client.get('/', headers={'Host': 'attacker.example'}).status_code, 403)
        self.assertEqual(self.client.get('/', headers={'Host': '['}).status_code, 403)

    def test_select_project_and_files(self):
        result = self.client.post('/api/project', json={'path': str(self.root)}, headers=self.auth)
        self.assertEqual(result.status_code, 200, result.text)
        names = [x['path'] for x in self.client.get('/api/files', headers=self.auth).json()['files']]
        self.assertIn('hello.py', names)
        self.assertNotIn('.env', names)
        result = self.client.get('/api/file', params={'path': 'hello.py'}, headers=self.auth)
        self.assertIn('def ola', result.json()['content'])
        denied = self.client.get('/api/file', params={'path': '.env'}, headers=self.auth)
        self.assertEqual(denied.status_code, 403)
        outside = self.client.get('/api/file', params={'path': '../../etc/passwd'}, headers=self.auth)
        self.assertEqual(outside.status_code, 403)
        invalid = self.client.post('/api/project', json={'path': str(self.root / 'missing')}, headers=self.auth)
        self.assertEqual(invalid.status_code, 400)

    def test_model_selection(self):
        self.client.post('/api/project', json={'path': str(self.root)}, headers=self.auth)
        r = self.client.get('/api/models', headers=self.auth).json()
        self.assertEqual(r['selected'], 'auto')
        self.assertIn('gemini', r['available'])
        chosen = self.client.post('/api/models', json={'provider': 'gemini'}, headers=self.auth)
        self.assertEqual(chosen.status_code, 200)
        self.assertEqual(chosen.json()['selected'], 'gemini')
        self.assertEqual(self.client.post('/api/models', json={'provider': 'unknown'}, headers=self.auth).status_code, 400)
        self.client.post('/api/models', json={'provider': 'auto'}, headers=self.auth)
        self.assertEqual(self.service.model_status()['selected'], 'auto')

    def test_chat_background_and_events(self):
        self.client.post('/api/project', json={'path': str(self.root)}, headers=self.auth)
        answer = self.client.post('/api/chat', json={'prompt': 'explique hello.py'}, headers=self.auth)
        self.assertEqual(answer.status_code, 200, answer.text)
        for _ in range(100):
            status = self.client.get('/api/status', headers=self.auth).json()
            if not status['active_job']:
                break
            time.sleep(0.02)
        self.assertEqual(status['jobs'][-1]['status'], 'completed', status)
        self.assertIn('Resposta local', status['jobs'][-1]['result'])
        self.assertEqual(status['history'][-1]['role'], 'assistant')
        events = self.client.get('/api/events', params={'after': 0}, headers=self.auth).json()['events']
        self.assertTrue(any(e['type'] == 'job_finished' for e in events))
        self.assertEqual(self.client.get('/api/events', params={'after': events[-1]['id']}, headers=self.auth).json()['events'], [])

    def test_approval_single_use_and_default_deny(self):
        self.client.post('/api/project', json={'path': str(self.root)}, headers=self.auth)
        result = []
        thread = threading.Thread(target=lambda: result.append(
            self.service.approvals.ask('tool', {'tool': 'run_tests'}, timeout_cancel)), daemon=True)
        timeout_cancel = threading.Event()
        thread.start()
        for _ in range(100):
            pending = self.client.get('/api/status', headers=self.auth).json()['pending_approvals']
            if pending:
                break
            time.sleep(0.01)
        self.assertTrue(pending)
        request_id = pending[0]['id']
        response = self.client.post('/api/approvals/' + request_id, json={'approved': True}, headers=self.auth)
        self.assertEqual(response.status_code, 200)
        thread.join(timeout=3)
        self.assertEqual(result, [True])
        self.assertEqual(self.client.post('/api/approvals/' + request_id,
                                         json={'approved': True}, headers=self.auth).status_code, 404)
        self.assertFalse(ApprovalBroker(lambda *_: None, timeout=0.05).ask('tool', {'tool': 'danger'}))

    def test_websocket_token(self):
        from starlette.websockets import WebSocketDisconnect
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect('/ws?token=invalid'):
                pass
        self.service._publish('test_event', {'message': 'hello'})
        with self.client.websocket_connect('/ws?token=test-token-do-not-share', headers={'Host':'127.0.0.1:8765'}) as socket:
            item = socket.receive_json()
            self.assertEqual(item['type'], 'test_event')

    def test_team_plan_without_external_api(self):
        self.client.post('/api/project', json={'path': str(self.root)}, headers=self.auth)
        plan = self.client.post('/api/team/plan', json={'objective': 'Crie calculadora.py e testes'}, headers=self.auth)
        self.assertEqual(plan.status_code, 200, plan.text)
        for _ in range(100):
            status = self.client.get('/api/status', headers=self.auth).json()
            if not status['active_job']:
                break
            time.sleep(0.02)
        self.assertEqual(status['jobs'][-1]['status'], 'completed', status)
        self.assertTrue(status['team']['roles'])
        self.assertEqual(status['team']['roles'][0]['role'], 'architect')
        self.assertEqual(status['team']['roles'][-1]['role'], 'reviewer')


    def test_memory_and_recall_scoped(self):
        self.client.post('/api/project', json={'path': str(self.root)}, headers=self.auth)
        saved = self.client.post('/api/remember', json={'query': 'Projeto usa Python e unittest.'}, headers=self.auth)
        self.assertEqual(saved.status_code, 200, saved.text)
        notes = self.client.get('/api/memory', headers=self.auth)
        self.assertEqual(notes.status_code, 200)
        self.assertTrue(any('unittest' in x['text'] for x in notes.json()['notes']))
        recall = self.client.post('/api/recall', json={'query': 'Python'}, headers=self.auth)
        self.assertEqual(recall.status_code, 200)
        self.assertIn('notes', recall.json())
        self.assertIn('sources', recall.json())
        self.assertTrue((self.root / '.tesla' / 'plan.json').exists() is False)

    def test_team_cancel_is_persistent(self):
        self.client.post('/api/project', json={'path': str(self.root)}, headers=self.auth)
        self.client.post('/api/team/plan', json={'objective': 'Crie calculadora.py'}, headers=self.auth)
        for _ in range(100):
            if not self.service.active_job:
                break
            time.sleep(.01)
        cancelled = self.client.post('/api/team/cancel', headers=self.auth)
        self.assertEqual(cancelled.status_code, 200, cancelled.text)
        self.assertEqual(cancelled.json()['status'], 'cancelled')
        self.assertEqual(self.service.executor.store.load().status, 'cancelled')

    def test_busy_does_not_enqueue_another_chat(self):
        self.client.post('/api/project', json={'path': str(self.root)}, headers=self.auth)
        blocker = threading.Event()
        original = self.service.agent.run
        def waiting(prompt, **kwargs):
            blocker.wait(timeout=2)
            return original(prompt, **kwargs)
        self.service.agent.run = waiting
        accepted = self.client.post('/api/chat', json={'prompt': 'Primeira tarefa'}, headers=self.auth)
        self.assertEqual(accepted.status_code, 200)
        blocked = self.client.post('/api/chat', json={'prompt': 'Segunda tarefa'}, headers=self.auth)
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(sum(x['role']=='user' for x in self.service.chat_history), 1)
        blocker.set()
        for _ in range(100):
            if not self.service.active_job:
                break
            time.sleep(.01)
        self.assertIsNone(self.service.active_job)

    def test_denied_tests_do_not_count_as_passed(self):
        self.client.post('/api/project', json={'path': str(self.root)}, headers=self.auth)
        test_job = self.client.post('/api/test', json={'target': 'all'}, headers=self.auth)
        self.assertEqual(test_job.status_code, 200)
        for _ in range(100):
            pending = self.service.approvals.list_pending()
            if pending:
                break
            time.sleep(.01)
        self.assertTrue(pending)
        approval_id = pending[0]['id']
        response = self.client.post('/api/approvals/'+approval_id, json={'approved': False}, headers=self.auth)
        self.assertEqual(response.status_code, 200)
        for _ in range(100):
            if not self.service.active_job:
                break
            time.sleep(.01)
        state = self.service.status()['jobs'][-1]
        self.assertEqual(state['status'], 'failed')
        self.assertIn('não autorizada', state['error'])


if __name__ == '__main__':
    unittest.main()
