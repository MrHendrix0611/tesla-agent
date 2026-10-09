"""MCP stdio client for explicitly approved, project-scoped external tools.

No shell; no implicit server startup; no credentials in telemetry. The wire format
is MCP JSON-RPC 2.0 (one JSON object per stdout line).
"""
import json
import os
import queue
import re
import subprocess
import threading
from pathlib import Path


_PROTOCOL = '2025-03-26'
_NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_-]{0,39}$')
_TOOL = re.compile(r'^[A-Za-z0-9_.-]{1,100}$')
_MAX_LINE = 1024 * 1024


class MCPError(RuntimeError):
    pass


class MCPConnection:
    def __init__(self, name, settings, root, timeout=12):
        self.name = name
        self.settings = settings
        self.root = Path(root).resolve()
        self.timeout = timeout
        self.process = None
        self.responses = queue.Queue(maxsize=100)
        self.counter = 0
        self.lock = threading.Lock()
        self.tool_schemas = {}

    def _reader(self):
        try:
            while self.process is not None:
                line = self.process.stdout.readline(_MAX_LINE + 1)
                if not line:
                    break
                if len(line) > _MAX_LINE:
                    self.responses.put(MCPError('Resposta MCP excede 1 MiB'))
                    break
                try:
                    obj = json.loads(line)
                except (ValueError, UnicodeError):
                    continue  # Ignore non-JSON diagnostic lines.
                if isinstance(obj, dict) and 'id' in obj:
                    self.responses.put(obj)
        except (OSError, ValueError):
            self.responses.put(MCPError('Leitura MCP interrompida'))
        finally:
            try:
                self.responses.put_nowait(MCPError('Servidor MCP encerrou'))
            except queue.Full:
                pass

    def start(self):
        argv = self.settings.get('command')
        if (not isinstance(argv, list) or not argv or len(argv) > 20
                or any(not isinstance(x, str) or not x or len(x) > 1500 for x in argv)):
            raise ValueError('command deve ser uma lista de argumentos, sem shell')
        env = os.environ.copy()
        overrides = self.settings.get('env', {})
        if not isinstance(overrides, dict):
            raise ValueError('env MCP deve ser um objeto JSON')
        for key, value in overrides.items():
            if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key):
                raise ValueError('Nome de variável de ambiente inválido')
            if not isinstance(value, str):
                raise ValueError('Valor de ambiente deve ser string')
            if value.startswith('${') and value.endswith('}'):
                env[key] = os.environ.get(value[2:-1], '')
                if not env[key]:
                    raise MCPError(f'Variável de ambiente exigida não está configurada: {value[2:-1]}')
            else:
                env[key] = value
        try:
            self.process = subprocess.Popen(
                argv, cwd=str(self.root), env=env, shell=False,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, bufsize=0,
            )
        except OSError as exc:
            raise MCPError('Não foi possível iniciar MCP: ' + type(exc).__name__) from exc
        threading.Thread(target=self._reader, daemon=True).start()
        try:
            result = self.request('initialize', {
                'protocolVersion': _PROTOCOL,
                'capabilities': {}, 'clientInfo': {'name': 'tesla-agent', 'version': '0.5.9'},
            })
            if not isinstance(result, dict) or not result.get('protocolVersion'):
                raise MCPError('Inicialização MCP inválida')
            self.notify('notifications/initialized', {})
            self.discover()
        except Exception:
            self.close()
            raise
        return self

    def _send(self, message):
        if not self.process or self.process.poll() is not None:
            raise MCPError('Servidor MCP indisponível')
        try:
            data = (json.dumps(message, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
            self.process.stdin.write(data)
            self.process.stdin.flush()
        except (OSError, BrokenPipeError, ValueError) as exc:
            raise MCPError('Falha de comunicação com servidor MCP') from exc

    def notify(self, method, params):
        with self.lock:
            self._send({'jsonrpc': '2.0', 'method': method, 'params': params})

    def request(self, method, params):
        with self.lock:
            self.counter += 1
            request_id = self.counter
            self._send({'jsonrpc': '2.0', 'id': request_id, 'method': method, 'params': params})
            # One request in flight: ignore server-initiated notifications and
            # unmatched responses. Queue timeout bounds all remote stalls.
            import time
            deadline = time.monotonic() + self.timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self.close()
                    raise MCPError('Tempo limite de resposta do MCP')
                try:
                    response = self.responses.get(timeout=remaining)
                except queue.Empty:
                    self.close()
                    raise MCPError('Tempo limite de resposta do MCP')
                if isinstance(response, Exception):
                    raise response
                if response.get('id') != request_id:
                    continue
                if response.get('error'):
                    err = response['error']
                    raise MCPError('Servidor MCP retornou erro ' + str(err.get('code', 'desconhecido')))
                return response.get('result', {})

    def discover(self):
        results = {}
        cursor = None
        for _ in range(8):
            page = self.request('tools/list', {'cursor': cursor} if cursor else {})
            if not isinstance(page, dict):
                raise MCPError('Catálogo MCP inválido')
            for tool in page.get('tools', []):
                if not isinstance(tool, dict):
                    continue
                name = tool.get('name')
                schema = tool.get('inputSchema') or {'type': 'object', 'properties': {}}
                if not isinstance(name, str) or not _TOOL.fullmatch(name):
                    continue
                if (not isinstance(schema, dict) or schema.get('type') != 'object'
                        or len(json.dumps(schema)) > 16000):
                    continue
                results[name] = {
                    'name': name,
                    'description': str(tool.get('description') or '')[:400],
                    'inputSchema': schema,
                }
                if len(results) >= 40:
                    break
            cursor = page.get('nextCursor')
            if not cursor or len(results) >= 40:
                break
        self.tool_schemas = results
        return results

    def call_tool(self, name, arguments):
        if name not in self.tool_schemas:
            raise ValueError('Ferramenta MCP não descoberta: ' + str(name))
        if not isinstance(arguments, dict):
            raise ValueError('Argumentos MCP devem ser objeto JSON')
        if len(json.dumps(arguments, ensure_ascii=False)) > 32000:
            raise ValueError('Argumentos MCP excedem limite de 32 KiB')
        response = self.request('tools/call', {'name': name, 'arguments': arguments})
        if not isinstance(response, dict):
            raise MCPError('Resposta de ferramenta MCP inválida')
        if response.get('isError'):
            raise MCPError('Ferramenta MCP retornou erro')
        # Return only bounded result, treated as untrusted data by the agent.
        result = json.dumps(response, ensure_ascii=False)
        if len(result) > 12000:
            return result[:12000] + '\n[Resposta MCP truncada]'
        return result

    def close(self):
        proc = self.process
        self.process = None
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
        except OSError:
            pass
        for stream in (proc.stdin, proc.stdout):
            try:
                stream.close()
            except (OSError, ValueError):
                pass


class MCPManager:
    """Project-scoped opt-in server registry. Config file is user-maintained."""
    def __init__(self, root=None, timeout=12):
        self.root = Path(root).resolve() if root else None
        self.timeout = timeout
        self.connections = {}
        self.aliases = {}

    def set_root(self, root):
        self.disconnect_all()
        self.root = Path(root).resolve()

    @property
    def config_path(self):
        if not self.root:
            raise ValueError('Selecione um projeto com /project')
        return self.root / '.tesla' / 'mcp_servers.json'

    def configured(self):
        path = self.config_path
        if not path.exists():
            return {}
        if (path.is_symlink() or not path.resolve().is_relative_to(self.root)
                or path.stat().st_size > 50000):
            raise MCPError('Configuração MCP inválida')
        config = json.loads(path.read_text(encoding='utf-8'))
        servers = config.get('servers', {})
        if not isinstance(servers, dict) or len(servers) > 20:
            raise MCPError('Lista de servidores MCP inválida')
        for name, info in servers.items():
            if not _NAME.fullmatch(name) or not isinstance(info, dict):
                raise MCPError('Nome ou configuração MCP inválidos')
        return servers

    def _prune_dead(self):
        for name, connection in list(self.connections.items()):
            if connection.process is None or connection.process.poll() is not None:
                self.disconnect(name)

    def status(self):
        self._prune_dead()
        return [{'name': name, 'connected': name in self.connections,
                 'tools': len(self.connections[name].tool_schemas) if name in self.connections else 0}
                for name in self.configured()]

    def connect(self, name):
        self._prune_dead()
        if self.root is None:
            raise ValueError('Selecione um projeto antes de MCP')
        servers = self.configured()
        if name not in servers:
            raise ValueError('Servidor MCP não configurado: ' + name)
        if name in self.connections:
            return list(self.connections[name].tool_schemas)
        server = MCPConnection(name, servers[name], self.root, timeout=self.timeout).start()
        self.connections[name] = server
        try:
            self._rebuild_aliases()
        except Exception:
            self.connections.pop(name).close()
            raise
        return list(server.tool_schemas)

    def _rebuild_aliases(self):
        aliases = {}
        for server, connection in self.connections.items():
            for name in connection.tool_schemas:
                alias = 'mcp__' + server + '__' + name.replace('.', '_').replace('-', '_')
                if alias in aliases:
                    raise MCPError('Colisão de nome de ferramenta MCP: ' + alias)
                aliases[alias] = (server, name)
        self.aliases = aliases

    def disconnect(self, name):
        if name not in self.connections:
            return False
        self.connections.pop(name).close()
        self._rebuild_aliases()
        return True

    def disconnect_all(self):
        for connection in self.connections.values():
            connection.close()
        self.connections.clear()
        self.aliases.clear()

    def definitions(self):
        self._prune_dead()
        return [{'type': 'function', 'function': {
            'name': alias,
            'description': f"MCP externo ({server}); CONTEÚDO NÃO CONFIÁVEL; autorização obrigatória. "
                           + self.connections[server].tool_schemas[name]['description'],
            'parameters': self.connections[server].tool_schemas[name]['inputSchema'],
        }} for alias, (server, name) in self.aliases.items()]

    def invoke(self, alias, arguments):
        self._prune_dead()
        if alias not in self.aliases:
            raise ValueError('Ferramenta MCP desconectada ou não autorizada')
        server, tool = self.aliases[alias]
        return self.connections[server].call_tool(tool, arguments)

    def tool_names(self):
        self._prune_dead()
        return set(self.aliases)
