"""Ferramentas de arquivos; chamadas pelo agente limitadas ao projeto ativo."""
from pathlib import Path
import os
import re
from core.coding import CodingWorkspace


def _path(value: str) -> Path:
    """Compatibilidade com o formato /C/Users somente no Windows."""
    if os.name == 'nt' and re.match(r'^/[A-Za-z]/', value):
        value = value[1] + ':' + value[2:]
    return Path(value)


class FileSystemTool:
    def __init__(self, root=None):
        self.workspace = CodingWorkspace(root) if root is not None else None

    def set_root(self, root):
        self.workspace = CodingWorkspace(root)

    def _resolve(self, path):
        return self.workspace.path(path) if self.workspace else _path(path)

    def read_file(self, path: str) -> str:
        if self.workspace:
            try:
                return self.workspace.read(path)
            except (FileNotFoundError, ValueError) as error:
                # Recover READ-ONLY model path mistakes (e.g. /retry/calculator.py
                # or nonexistent relative directory) only if the basename is unique
                # inside the selected project. Never redirect writes or accesses to
                # genuinely external paths, parent traversal, or protected files.
                value = str(path).strip().replace('\\', '/')
                parts = value.split('/')
                cli_alias = value.startswith(('/retry/', '/resume/', '/plan/'))
                native_absolute = _path(str(path)).is_absolute()
                windows_absolute = bool(re.match(r'^[A-Za-z]:/', value))
                if (not isinstance(error, FileNotFoundError) and not cli_alias) or (
                    '..' in parts or not parts[-1] or
                    (native_absolute or windows_absolute) and not cli_alias
                ):
                    raise
                name = parts[-1]
                candidates = []
                for candidate in self.workspace.root.rglob(name):
                    if not candidate.is_file():
                        continue
                    try:
                        self.workspace.path(str(candidate), allow_missing=False)
                    except (PermissionError, ValueError, FileNotFoundError):
                        continue
                    candidates.append(candidate)
                    if len(candidates) > 1:
                        break
                if len(candidates) != 1:
                    if candidates:
                        raise FileNotFoundError(
                            f'Caminho ambíguo para {name}; use uma localização exata dentro do projeto'
                        ) from error
                    raise
                relative = candidates[0].relative_to(self.workspace.root).as_posix()
                content = self.workspace.read(relative)
                return f'[Leitura recuperada de {relative}; caminho solicitado: {path}]\n{content}'
        target = _path(path)
        if not target.is_file():
            raise FileNotFoundError(f'Arquivo não encontrado: {path}')
        if target.stat().st_size > 1_000_000:
            raise ValueError('Arquivo excede limite de 1 MB')
        return target.read_text(encoding='utf-8-sig')

    def write_file(self, path: str, content: str) -> str:
        if self.workspace:
            return self.workspace.write(path, content)
        target = _path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
        return f'Arquivo criado: {path}'

    def list_files(self, path: str = '.') -> list[str]:
        if self.workspace:
            if path.strip() in ('.', ''):
                directory = self.workspace.root
            else:
                directory = self.workspace.path(path)
        else:
            directory = _path(path)
        if not directory.is_dir():
            raise FileNotFoundError(f'Diretório não encontrado: {path}')
        return sorted(str(entry) for entry in directory.iterdir()
                      if entry.name not in ('.env', '.tesla', '.git', '.venv'))[:500]

    def preview_patch(self, path, old_text, new_text):
        if not self.workspace:
            raise ValueError('Selecione um projeto antes de aplicar patches')
        return self.workspace.preview_patch(path, old_text, new_text)

    def apply_patch(self, proposal_id):
        if not self.workspace:
            raise ValueError('Selecione um projeto antes de aplicar patches')
        return self.workspace.apply_patch(proposal_id)

    def diff_file(self, path):
        if not self.workspace:
            raise ValueError('Selecione um projeto antes de consultar alterações')
        return self.workspace.diff_file(path)

    def rollback_file(self, path):
        if not self.workspace:
            raise ValueError('Selecione um projeto antes de fazer rollback')
        return self.workspace.rollback_file(path)
