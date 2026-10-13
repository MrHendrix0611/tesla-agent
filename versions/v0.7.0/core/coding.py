"""Secure, bounded coding workspace with staged patches and reversible writes.

All tool paths resolve under the explicitly selected repository. A proposed edit
is only a preview until an approved apply_patch/write_file tool call executes.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone
from uuid import uuid4

MAX_FILE_BYTES = 1_000_000
MAX_DIFF_CHARS = 18_000
PROTECTED_FILES = {'.env', '.npmrc', '.pypirc', 'credentials.json', 'secrets.json', 'id_rsa', 'id_ed25519'}
PROTECTED_DIRS = {'.git', '.tesla', '.venv', 'venv', '__pycache__', 'node_modules'}
PROTECTED_SUFFIXES = {'.pem', '.key', '.p12', '.pfx', '.db', '.sqlite', '.zip', '.exe', '.dll', '.pyc'}


def digest(data: bytes | None) -> str | None:
    return hashlib.sha256(data).hexdigest() if data is not None else None


class CodingWorkspace:
    def __init__(self, root: str | Path):
        root = Path(root).expanduser().resolve()
        if not root.is_dir():
            raise ValueError(f'Diretório de projeto inexistente: {root}')
        self.root = root
        self.pending: dict[str, dict] = {}

    def path(self, value: str, *, allow_missing=True) -> Path:
        if not isinstance(value, str) or not value.strip():
            raise ValueError('Caminho de arquivo obrigatório')
        value = value.strip().strip('"')
        # On Windows, '/C/Users' is not a reliable native path; block it.
        if value.startswith(('/retry/', '/resume/', '/plan/')) or (
            os.name == 'nt' and len(value) > 3 and value[0] == '/' and value[2] == '/'
            and value[1].isalpha()
        ):
            raise ValueError('Caminho inválido. Use caminho relativo ao projeto ou absoluto nativo.')
        if os.name != 'nt' and len(value) > 2 and value[1] == ':' and value[0].isalpha():
            raise ValueError('Caminho Windows inválido neste sistema')
        proposed = Path(value).expanduser()
        candidate = (proposed if proposed.is_absolute() else self.root / proposed).resolve(strict=False)
        try:
            relative = candidate.relative_to(self.root)
        except ValueError as exc:
            raise PermissionError(f'Caminho fora do projeto selecionado: {value}') from exc
        if not relative.parts:
            raise ValueError('Selecione um arquivo dentro do projeto')
        lowered = [part.lower() for part in relative.parts]
        if any(part in PROTECTED_DIRS for part in lowered) or any(part in PROTECTED_FILES for part in lowered):
            raise PermissionError('Acesso bloqueado a arquivo ou diretório reservado/sensível')
        if candidate.suffix.lower() in PROTECTED_SUFFIXES or candidate.name.lower().startswith('.env.'):
            raise PermissionError('Tipo de arquivo reservado/sensível')
        if not allow_missing and not candidate.is_file():
            raise FileNotFoundError(f'Arquivo não encontrado: {value}')
        return candidate

    def _read(self, target: Path) -> bytes | None:
        if not target.exists():
            return None
        if not target.is_file():
            raise ValueError(f'Não é arquivo: {target}')
        if target.stat().st_size > MAX_FILE_BYTES:
            raise ValueError('Arquivo excede limite de 1 MB')
        data = target.read_bytes()
        if b'\x00' in data:
            raise ValueError('Arquivos binários não são suportados')
        return data

    def read(self, path: str) -> str:
        target = self.path(path, allow_missing=False)
        try:
            return (self._read(target) or b'').decode('utf-8-sig')
        except UnicodeError as exc:
            raise ValueError(f'Arquivo não está em UTF-8: {path}') from exc

    def _history_dir(self) -> Path:
        return self.root / '.tesla' / 'backups'

    def _load_history(self) -> list[dict]:
        index = self._history_dir() / 'index.json'
        if not index.exists():
            return []
        try:
            content = json.loads(index.read_text(encoding='utf-8'))
            return content if isinstance(content, list) else []
        except (OSError, ValueError):
            return []

    def _save_history(self, records: list[dict]) -> None:
        base = self._history_dir()
        base.mkdir(parents=True, exist_ok=True)
        (base / 'index.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')

    def _atomic_write(self, target: Path, content: bytes) -> None:
        if len(content) > MAX_FILE_BYTES:
            raise ValueError('Conteúdo excede 1 MB')
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, filename = tempfile.mkstemp(prefix='.tesla-', dir=str(target.parent))
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(content)
            os.replace(filename, target)
        finally:
            if os.path.exists(filename):
                os.unlink(filename)

    def write(self, path: str, content: str) -> str:
        if not isinstance(content, str):
            raise ValueError('Conteúdo deve ser texto')
        target = self.path(path)
        before = self._read(target)
        after = content.encode('utf-8')
        if len(after) > MAX_FILE_BYTES:
            raise ValueError('Conteúdo excede 1 MB')
        if before == after:
            return f'Arquivo sem alterações: {target.relative_to(self.root)}'
        event_id = uuid4().hex
        if before is not None:
            backup = self._history_dir() / f'{event_id}.bak'
            backup.parent.mkdir(parents=True, exist_ok=True)
            self._atomic_write(backup, before)
        self._atomic_write(target, after)
        history = self._load_history()
        history.append({
            'id': event_id,
            'path': target.relative_to(self.root).as_posix(),
            'before': digest(before), 'after': digest(after),
            'had_original': before is not None,
            'created_at': datetime.now(timezone.utc).isoformat()
        })
        self._save_history(history)
        return f'Arquivo salvo e versionado: {target.relative_to(self.root)} (backup {event_id[:8]})'

    def preview_patch(self, path: str, old_text: str, new_text: str) -> dict:
        if not isinstance(old_text, str) or not isinstance(new_text, str):
            raise ValueError('old_text/new_text devem ser strings')
        target = self.path(path)
        before = self._read(target)
        current = (before or b'').decode('utf-8-sig')
        if not old_text and before is not None:
            raise ValueError('Para criar arquivo, selecione um caminho que ainda não exista')
        if old_text:
            occurrences = current.count(old_text)
            if occurrences != 1:
                raise ValueError(f'Trecho esperado não aparece exatamente uma vez: {occurrences} ocorrências')
            updated = current.replace(old_text, new_text, 1)
        else:
            updated = new_text
        if len(updated.encode('utf-8')) > MAX_FILE_BYTES:
            raise ValueError('Conteúdo excede 1 MB')
        diff = ''.join(difflib.unified_diff(current.splitlines(True), updated.splitlines(True),
                                            fromfile=f'a/{target.name}', tofile=f'b/{target.name}'))
        proposal_id = uuid4().hex[:12]
        self.pending[proposal_id] = {
            'path': str(target), 'original_digest': digest(before), 'content': updated, 'diff': diff[:MAX_DIFF_CHARS]
        }
        return {'proposal_id': proposal_id, 'path': target.relative_to(self.root).as_posix(),
                'diff': diff[:MAX_DIFF_CHARS], 'truncated': len(diff) > MAX_DIFF_CHARS,
                'note': 'Prévia; nenhuma alteração aplicada. Use apply_patch com confirmação.'}

    def apply_patch(self, proposal_id: str) -> str:
        item = self.pending.get(proposal_id)
        if item is None:
            raise ValueError('Proposta inexistente ou expirada. Gere nova prévia.')
        target = self.path(item['path'])
        if digest(self._read(target)) != item['original_digest']:
            raise RuntimeError('Arquivo mudou após a prévia; refaça o patch.')
        outcome = self.write(str(target), item['content'])
        del self.pending[proposal_id]
        return outcome

    def diff_file(self, path: str) -> dict:
        target = self.path(path, allow_missing=False)
        relative = target.relative_to(self.root).as_posix()
        history = self._load_history()
        entry = next((e for e in reversed(history) if e['path'] == relative), None)
        if entry is None:
            return {'path': relative, 'diff': '', 'message': 'Sem backup anterior.'}
        before = (self._history_dir() / f"{entry['id']}.bak").read_text(encoding='utf-8') if entry['had_original'] else ''
        after = self.read(str(target))
        diff = ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                            fromfile=f'a/{relative}', tofile=f'b/{relative}'))
        return {'path': relative, 'diff': diff[:MAX_DIFF_CHARS], 'truncated': len(diff) > MAX_DIFF_CHARS}

    def rollback_file(self, path: str) -> str:
        target = self.path(path)
        relative = target.relative_to(self.root).as_posix()
        history = self._load_history()
        index = next((i for i in range(len(history)-1, -1, -1) if history[i]['path'] == relative), None)
        if index is None:
            raise ValueError('Arquivo não possui alterações com backup pelo Tesla')
        record = history[index]
        if digest(self._read(target)) != record['after']:
            raise RuntimeError('O arquivo mudou desde a última alteração; rollback bloqueado.')
        if record['had_original']:
            backup = self._history_dir() / f"{record['id']}.bak"
            previous = backup.read_bytes()
            if digest(previous) != record['before']:
                raise RuntimeError('Integridade do backup inválida')
            self._atomic_write(target, previous)
        else:
            if target.exists():
                target.unlink()
        del history[index]
        self._save_history(history)
        return f'Rollback concluído: {relative}'
