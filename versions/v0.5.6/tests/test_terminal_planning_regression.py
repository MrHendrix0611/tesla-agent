import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from tools.terminal import TerminalTool
from tools.filesystem import _path
from core.executor import PlanExecutor
from core.plan_store import PlanStore
import tempfile


class TerminalRegressions(unittest.TestCase):
    def test_success_has_exit_code(self):
        result = TerminalTool().run_command(f'"{sys.executable}" -c "print(42)"')
        self.assertIn("exit_code: 0", result)
        self.assertIn("42", result)

    def test_failure_not_reported_as_success(self):
        with self.assertRaisesRegex(RuntimeError, "exit_code: 7"):
            TerminalTool().run_command(f'"{sys.executable}" -c "import sys; sys.exit(7)"')

    def test_drive_path_only_converted_on_windows(self):
        with patch('tools.filesystem.os.name', 'nt'):
            # On POSIX pathlib.Path still uses POSIX path syntax; check on Windows only.
            if os.name == 'nt':
                self.assertEqual(str(_path('/C/Users/Test/test.py')).lower(),
                                 str(Path('C:/Users/Test/test.py')).lower())

    def test_plan_prompt_scope_and_commands(self):
        class A:
            def __init__(self): self.last_run_evidence={}; self.prompts=[]
            def run(self,prompt,plan_step=False):
                self.prompts.append(prompt)
                self.last_run_evidence={'finished':True, 'tools':['read_file'], 'tool_errors':[], 'denied':[]}
                return 'Conferido'
        with tempfile.TemporaryDirectory() as d:
            a=A(); ex=PlanExecutor(a,PlanStore(Path(d)/'plan.json'))
            ex.create('Criar aplicativo', [{'description':'Inspecionar projeto','dependencies':[]}])
            ex.run(lambda _: True)
            self.assertIn('py -m unittest',a.prompts[0])
            self.assertIn('NÃO EXECUTAR AGORA',a.prompts[0])

if __name__ == '__main__': unittest.main()
