"""Execução de comandos com código de saída verificável."""
import subprocess


class TerminalTool:
    def run_command(self, command: str) -> str:
        if not isinstance(command, str) or not command.strip():
            raise ValueError("Comando vazio")
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                errors="replace", timeout=90
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Comando excedeu 90 segundos") from exc
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        report = (f"exit_code: {result.returncode}\n"
                  f"stdout:\n{stdout or '(vazio)'}\n"
                  f"stderr:\n{stderr or '(vazio)'}")
        if result.returncode != 0:
            raise RuntimeError("Comando falhou. " + report[:3500])
        return report[:12000]
