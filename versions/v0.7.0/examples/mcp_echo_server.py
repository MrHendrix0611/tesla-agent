"""Minimal local MCP stdio demo; no external packages or network access.

Run ONLY via `/mcp connect demo` after configuring this file as an executable
using the absolute path to your Python interpreter.
"""
import json
import sys


def reply(request_id, result):
    sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': request_id, 'result': result}) + '\n')
    sys.stdout.flush()


for raw in sys.stdin:
    try:
        item = json.loads(raw)
        method = item.get('method')
        if 'id' not in item:
            continue
        req_id = item['id']
        if method == 'initialize':
            reply(req_id, {'protocolVersion': '2025-03-26',
                           'capabilities': {'tools': {}},
                           'serverInfo': {'name': 'tesla-demo', 'version': '1.0'}})
        elif method == 'tools/list':
            reply(req_id, {'tools': [{'name': 'sum_numbers',
                'description': 'Soma dois números; não lê arquivos nem acessa a rede.',
                'inputSchema': {'type': 'object',
                    'properties': {'a': {'type': 'number'}, 'b': {'type': 'number'}},
                    'required': ['a', 'b']}}]})
        elif method == 'tools/call':
            data = item.get('params') or {}
            args = data.get('arguments') or {}
            if data.get('name') == 'sum_numbers' and all(isinstance(args.get(n), (float, int))
                                                       and not isinstance(args.get(n), bool)
                                                       for n in ('a', 'b')):
                reply(req_id, {'content': [{'type': 'text', 'text': str(args['a'] + args['b'])}]})
            else:
                sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': req_id, 'error':
                    {'code': -32602, 'message': 'Invalid arguments'}}) + '\n')
                sys.stdout.flush()
        else:
            sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': req_id, 'error':
                {'code': -32601, 'message': 'Method not found'}}) + '\n')
            sys.stdout.flush()
    except (ValueError, TypeError, KeyError):
        # Demo only; real servers should send appropriate JSON-RPC parse errors.
        pass
