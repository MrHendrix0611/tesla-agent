"""End-to-end mocked LLM tests, actual local MCP server protocol."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

from core.agent import Agent
from core.context import ContextManager
from core.executor import PlanExecutor
from core.plan_store import PlanStore
from core.permission_manager import PermissionManager
from tools.registry import ToolRegistry


DEMO = Path(__file__).resolve().parent.parent / 'examples' / 'mcp_echo_server.py'


class SequenceLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def generate(self, messages, tools=None, **kwargs):
        self.calls.append([t['function']['name'] for t in (tools or [])])
        return self.replies.pop(0)


class MCPAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        config = self.root / '.tesla'
        config.mkdir()
        (config / 'mcp_servers.json').write_text(json.dumps({
            'servers': {'demo': {'command': [sys.executable, '-u', str(DEMO)]}}
        }), encoding='utf-8')
        self.agent = Agent.__new__(Agent)
        self.agent.context = ContextManager()
        self.agent.active_skill = None
        self.agent.tools = ToolRegistry()
        self.agent.tools.set_workspace(self.root)
        self.agent.permissions = PermissionManager()
        self.agent.plan_allowed_tools = None
        self.agent.max_tool_calls = 6
        self.agent.max_plan_tool_calls = 6
        self.agent.max_plan_iterations = 6
        self.agent.system_prompt = 'Tesla MCP test agent.'
        self.agent.tools.mcp.connect('demo')
        self.addCleanup(self.agent.tools.mcp.disconnect_all)

    def _tool_reply(self):
        return {'content': '', 'tool_calls': [{
            'id': 'call1', 'name': 'mcp__demo__sum_numbers',
            'arguments': json.dumps({'a': 3, 'b': 4})
        }]}

    def test_model_mcp_call_requires_confirmation_and_executes(self):
        self.agent.llm = SequenceLLM([self._tool_reply(), {'content': '7', 'tool_calls': []}])
        confirmations = []
        self.agent.confirm_tool = lambda name, arguments: confirmations.append(name) or True
        reply = self.agent.run('Use MCP demo para somar 3 e 4')
        self.assertEqual(reply, '7')
        self.assertEqual(confirmations, ['mcp__demo__sum_numbers'])
        self.assertIn('mcp__demo__sum_numbers', self.agent.last_run_evidence['tools'])
        self.assertIn('mcp__demo__sum_numbers', self.agent.llm.calls[0])

    def test_model_mcp_call_denied_does_not_execute(self):
        self.agent.llm = SequenceLLM([self._tool_reply()])
        self.agent.confirm_tool = lambda name, arguments: False
        reply = self.agent.run('Use MCP demo para somar 3 e 4')
        self.assertIn('não autorizada', reply)
        self.assertEqual(self.agent.last_run_evidence['tools'], [])
        self.assertEqual(self.agent.last_run_evidence['denied'], ['mcp__demo__sum_numbers'])

    def test_plan_empty_project_does_not_inspect_nonexistent_commits(self):
        self.agent.llm = SequenceLLM([{'content': json.dumps({'steps': [
            {'description': 'Inspecionar commits de segurança do repositório', 'dependencies': []},
            {'description': 'Criar um arquivo util.py', 'dependencies': [1]},
        ]})}])
        executor = PlanExecutor(self.agent, PlanStore(self.root / '.tesla' / 'plan.json'))
        plan = executor.generate('Criar um arquivo util.py simples')
        self.assertIn('projeto vazio', plan.steps[0].description)
        self.assertNotIn('commits', plan.steps[0].description)


if __name__ == '__main__':
    unittest.main()
