"""Verify actual RAG context is passed to a simulated LLM and auto-refreshes."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from core.agent import Agent
from core.context import ContextManager
from core.executor import PlanExecutor
from core.plan_store import PlanStore
from core.permission_manager import PermissionManager
from tools.registry import ToolRegistry


class InspectLLM:
    def __init__(self):
        self.messages = []

    def generate(self, messages, tools=None, **kwargs):
        self.messages.append(json.loads(json.dumps(messages)))
        return {'content': 'Resposta simulada de testes.', 'tool_calls': []}


def make_agent(root):
    agent = Agent.__new__(Agent)
    agent.llm = InspectLLM()
    agent.context = ContextManager()
    agent.active_skill = None
    agent.tools = ToolRegistry()
    agent.tools.set_workspace(root)
    agent.permissions = PermissionManager()
    agent.max_tool_calls = 8
    agent.max_plan_tool_calls = 12
    agent.max_plan_iterations = 14
    agent.plan_allowed_tools = None
    agent.system_prompt = 'Tesla é agente de engenharia de software.'
    agent.confirm_tool = lambda name, arguments: False
    return agent


class RagAgentIntegrationTests(unittest.TestCase):
    def test_retrieval_is_attached_with_source_not_invented(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'calc.py').write_text('def calcular_media_de_vendas(): return 21\n')
            agent = make_agent(root)
            agent.tools.get_project_memory().add('A arquitetura usa unittest para testes.')
            response = agent.run('Explique calcular_media_de_vendas e unittest')
            self.assertIn('Resposta simulada', response)
            sent = agent.llm.messages[-1]
            context = '\n'.join(str(m.get('content')) for m in sent)
            self.assertIn('Fonte calc.py linhas 1-1', context)
            self.assertIn('Nota do usuário', context)
            self.assertEqual(agent.last_run_evidence['rag_sources'], ['calc.py:1-1'])
            self.assertEqual(agent.last_run_evidence['memory_matches'], 1)

    def test_refresh_updates_response_context_after_external_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            file = root / 'calc.py'
            file.write_text('def total_antigo(): pass\n')
            agent = make_agent(root)
            agent.run('Explique total_antigo')
            file.write_text('def total_novo_recalculado(): return 42\n')
            agent.run('Explique total_novo_recalculado')
            context = '\n'.join(str(m.get('content')) for m in agent.llm.messages[-1])
            self.assertIn('total_novo_recalculado', context)
            # Old content is not exposed through the retrieval block.
            retrieved = next(m['content'] for m in agent.llm.messages[-1]
                             if 'CONTEXTO LOCAL RECUPERADO' in str(m.get('content')))
            self.assertNotIn('total_antigo', retrieved)

    def test_project_isolation_during_switching(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            agent = make_agent(first)
            (Path(first) / 'first.py').write_text('def funcao_primeiro_projeto(): pass')
            (Path(second) / 'second.py').write_text('def funcao_segundo_projeto(): pass')
            agent.run('funcao_primeiro_projeto')
            agent.tools.set_workspace(second)
            agent.run('funcao_segundo_projeto')
            retrieved = next(m['content'] for m in agent.llm.messages[-1]
                             if 'CONTEXTO LOCAL RECUPERADO' in str(m.get('content')))
            self.assertIn('second.py', retrieved)
            self.assertNotIn('first.py', retrieved)
            # Conversation can still mention old requests: avoid claiming full
            # transcript isolation; RAG document retrieval is project-scoped.

    def test_planner_receives_real_project_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'existing.py').write_text('def soma(a,b): return a+b\n')
            agent = make_agent(root)
            prompts = []
            def simulate(messages, tools=None, **kwargs):
                prompts.append(messages[-1]['content'])
                return {'content': '{"steps": [{"description": "Inspecionar existing.py", "dependencies": []}, '
                                   '{"description": "Executar testes unittest", "dependencies": [1]}]}'}
            agent.llm.generate = simulate
            plans = PlanExecutor(agent, PlanStore(root / '.tesla' / 'plan.json'))
            plans.generate('Avaliar soma em existing.py')
            self.assertIn('existing.py', prompts[-1])
            self.assertIn('DADOS LOCAIS', prompts[-1])


if __name__ == '__main__':
    unittest.main()
