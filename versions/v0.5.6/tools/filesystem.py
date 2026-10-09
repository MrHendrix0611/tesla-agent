from pathlib import Path
import os
import re


def _path(value: str) -> Path:
    """Reconhece /C/Users/... como C:/Users/... somente no Windows."""
    if os.name == "nt" and re.match(r"^/[A-Za-z]/", value):
        value = value[1] + ":" + value[2:]
    return Path(value)


class FileSystemTool:

    def read_file(self, path: str) -> str:
        file_path = _path(path)

        if not file_path.exists():
            raise FileNotFoundError(
                f"Arquivo não encontrado: {path}"
            )

        if not file_path.is_file():
            raise ValueError(
                f"O caminho não é um arquivo: {path}"
            )

        return file_path.read_text(
            encoding="utf-8"
        )

    def write_file(self, path: str, content: str) -> str:
        file_path = _path(path)

        file_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        file_path.write_text(
            content,
            encoding="utf-8"
        )

        return f"Arquivo criado: {path}"

    def list_files(self, path: str = ".") -> list[str]:
        directory = _path(path)

        if not directory.exists():
            raise FileNotFoundError(
                f"Diretório não encontrado: {path}"
            )

        if not directory.is_dir():
            raise ValueError(
                f"O caminho não é um diretório: {path}"
            )

        return [
            str(item)
            for item in directory.iterdir()
        ]