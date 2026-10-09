"""Verificador local, conservador, para publicação de snapshots do Tesla.

Não imprime valores sensíveis; exibe somente arquivos e tipos de alerta.
Não substitui revisão manual nem scanner profissional de segredos.
"""
from __future__ import annotations
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = {
    "chave OpenRouter": re.compile(r"sk-or-[A-Za-z0-9_-]{12,}"),
    "chave Groq": re.compile(r"gsk_[A-Za-z0-9]{16,}"),
    "chave com prefixo sk": re.compile(r"sk-[A-Za-z0-9_-]{22,}"),
    "chave Google": re.compile(r"AIza[A-Za-z0-9_-]{25,}"),
    "token GitHub": re.compile(r"(?:github_pat_|ghp_|gho_|ghu_)[A-Za-z0-9_]{14,}"),
    "chave privada PEM": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
# Strings literalmente fictícias dos testes de segurança herdados.
TEST_FIXTURES = {"sk" + "-SuperSecretExample123456", "sk" + "-very-private-credential", "sk" + "-FakeCredentialxxxxxx"}
BANNED_DIRS = {".tesla", "__pycache__", ".venv", "venv", "data", "logs", ".pytest_cache", "workspace"}
BANNED_SUFFIXES = {".log", ".sqlite", ".sqlite3", ".db", ".msi", ".exe", ".pyc", ".pem", ".key", ".zip"}
issues = []
checked = 0
for path in ROOT.rglob("*"):
    if not path.is_file() or ".git" in path.parts:
        continue
    rel = path.relative_to(ROOT)
    checked += 1
    if path.name == ".env" or path.name.startswith(".env.") and path.name != ".env.example":
        issues.append((str(rel), "arquivo de ambiente privado"))
    if any(part in BANNED_DIRS for part in rel.parts[:-1]):
        issues.append((str(rel), "estado local ou cache"))
    if path.suffix.lower() in BANNED_SUFFIXES:
        issues.append((str(rel), "arquivo binário, temporário ou sensível"))
    try:
        text = path.read_text("utf-8")
    except (UnicodeError, OSError):
        continue
    if path.name == ".env.example":
        for line in text.splitlines():
            if "=" not in line or line.strip().startswith("#"):
                continue
            key, val = line.split("=", 1)
            if any(term in key.upper() for term in ["API_KEY", "PASSWORD", "SECRET", "ACCESS_TOKEN", "AUTH_TOKEN"]) and val.strip():
                issues.append((str(rel), "exemplo de credencial não vazio"))
    for kind, pat in SECRET_PATTERNS.items():
        for match in pat.finditer(text):
            if "tests/test_project_memory_rag.py" in str(rel).replace("\\", "/") and match.group() in TEST_FIXTURES:
                continue
            issues.append((str(rel), "possível " + kind))

if issues:
    print("ATENÇÃO: há arquivos que precisam de revisão antes da publicação:")
    for file, reason in issues:
        print(" -", file, "→", reason)
    sys.exit(1)
print(f"OK: {checked} arquivos examinados; nenhum segredo com padrões reconhecidos fora dos fixtures sintéticos.")
print("OBS: a revisão manual, a rotação de chaves antigas e a conferência de releases continuam necessárias.")
