import subprocess


class TerminalTool:

    def run_command(self, command: str) -> str:

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True
        )

        output = result.stdout

        if result.stderr:
            output += "\n" + result.stderr

        return output.strip()