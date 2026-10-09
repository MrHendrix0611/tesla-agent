"""Execução real de comandos e testes sem construir shell para suites Python."""
from pathlib import Path
import os
import re
import subprocess
import sys


class TerminalTool:
    def __init__(self, root=None):
        self.root = Path(root).resolve() if root is not None else Path.cwd().resolve()

    def set_root(self, root):
        root = Path(root).resolve()
        if not root.is_dir():
            raise ValueError('Projeto não encontrado')
        self.root = root

    @staticmethod
    def _report(result):
        out = result.stdout.strip() if result.stdout else ''
        err = result.stderr.strip() if result.stderr else ''
        report = f'exit_code: {result.returncode}\nstdout:\n{out or "(vazio)"}\nstderr:\n{err or "(vazio)"}'
        if result.returncode:
            raise RuntimeError('Comando falhou. ' + report[:5000])
        return report[:12000]

    def run_command(self, command: str) -> str:
        if not isinstance(command, str) or not command.strip():
            raise ValueError('Comando vazio')
        # Running tests or diagnostics must stay in the chosen workspace.
        # A shell `cd` can silently redirect all subsequent operations to the
        # Tesla installation directory (or another unrelated location).
        if re.search(r'(?i)(?:^|[&|;\r\n])\s*(?:cd|chdir|pushd|popd)\b', command):
            raise PermissionError(
                'Mudança de diretório por shell bloqueada. '
                'Selecione o projeto com /project e execute o comando sem cd.'
            )
        # Explicit shell commands remain possible with user confirmation, but reject
        # hallucinated paths and direct secret extraction attempts.
        if re.search(r'(?i)(?:\.env\b|/retry/|/resume/|/plan/|\.tesla[/\\]backups)', command):
            raise PermissionError('Comando contém caminho sensível ou inválido')
        try:
            result = subprocess.run(command, shell=True, cwd=str(self.root),
                                    capture_output=True, text=True, errors='replace', timeout=90)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('Comando excedeu 90 segundos') from exc
        return self._report(result)

    def run_tests(self, target: str = 'all') -> str:
        """Execute unittest without shell, in the selected project root."""
        if not isinstance(target, str):
            raise ValueError('target inválido')
        target = target.strip()
        if target == 'discover':
            args = [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v']
        elif target == 'all':
            args = [sys.executable, '-m', 'unittest', 'discover', '-s', '.', '-p', 'test*.py', '-v']
        elif re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*){0,5}', target):
            args = [sys.executable, '-m', 'unittest', target, '-v']
        else:
            raise ValueError('target permitido: discover, all ou nome do módulo de testes')
        try:
            result = subprocess.run(args, cwd=str(self.root), capture_output=True,
                                    text=True, errors='replace', timeout=90)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('Testes excederam 90 segundos') from exc
        report = self._report(result)
        match = re.search(r'Ran (\d+) tests?', report)
        if not match or int(match.group(1)) == 0:
            raise RuntimeError('Nenhum teste unittest foi executado; verifique target e descoberta.')
        return report
