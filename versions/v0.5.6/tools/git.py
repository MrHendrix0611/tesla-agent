import subprocess


class GitTool:

    def _run_git(self, arguments: list[str]) -> str:

        result = subprocess.run(
            ["git"] + arguments,
            capture_output=True,
            text=True
        )

        output = result.stdout

        if result.stderr:
            output += "\n" + result.stderr

        return output.strip()

    def status(self) -> str:
        return self._run_git(["status"])

    def diff(self) -> str:
        return self._run_git(["diff"])

    def log(self) -> str:
        return self._run_git([
            "log",
            "--oneline",
            "-10"
        ])