"""Tesla local-only authenticated FastAPI server (v0.7)."""
from __future__ import annotations

import asyncio
import json
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel, Field

from web.service import TeslaService

STATIC = Path(__file__).parent / 'static'


class ProjectRequest(BaseModel):
    path: str = Field(min_length=1, max_length=1000)


class PromptRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)


class ObjectiveRequest(BaseModel):
    objective: str = Field(min_length=1, max_length=7000)


class ApprovalRequest(BaseModel):
    approved: bool


class ProviderRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=30)


class TestRequest(BaseModel):
    target: str = Field(default='all', max_length=100)


class RecallRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


def _host_ok(host: str) -> bool:
    """Reject DNS rebinding; only explicit loopback host headers accepted."""
    try:
        hostname = urlsplit('http://' + host).hostname
        return hostname in ('127.0.0.1', 'localhost', '::1')
    except ValueError:
        return False


def _origin_ok(origin: str | None, host: str) -> bool:
    if origin is None:
        return True  # Native clients must supply the bearer token.
    try:
        parsed = urlsplit(origin)
        return parsed.scheme == 'http' and parsed.netloc.lower() == host.lower()
    except ValueError:
        return False


def create_app(service: TeslaService | None = None, *, secret: str | None = None) -> FastAPI:
    app = FastAPI(title='Tesla Agent Local API', version='0.7.0', docs_url=None,
                  redoc_url=None, openapi_url=None)
    app.state.service = service or TeslaService()
    app.state.secret = secret or secrets.token_urlsafe(36)

    @app.middleware('http')
    async def local_security(request: Request, call_next):
        host = request.headers.get('host', '')
        if not _host_ok(host):
            return JSONResponse({'detail': 'Host não autorizado'}, status_code=403)
        if request.method != 'GET' or request.url.path.startswith('/api/'):
            if not _origin_ok(request.headers.get('origin'), host):
                return JSONResponse({'detail': 'Origem não autorizada'}, status_code=403)
        if request.url.path.startswith('/api/'):
            if not secrets.compare_digest(request.headers.get('x-tesla-token', ''), app.state.secret):
                return JSONResponse({'detail': 'Token inválido'}, status_code=401)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; connect-src 'self' ws://127.0.0.1:* ws://localhost:*; "
            "img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
        )
        return response

    @app.exception_handler((ValueError))
    async def user_error(request: Request, exc: ValueError):
        return JSONResponse({'detail': str(exc)[:400]}, status_code=400)

    @app.exception_handler((RuntimeError))
    async def runtime_error(request: Request, exc: RuntimeError):
        return JSONResponse({'detail': str(exc)[:500]}, status_code=409)

    @app.exception_handler((PermissionError))
    async def permission_error(request: Request, exc: PermissionError):
        return JSONResponse({'detail': 'Acesso negado: ' + str(exc)[:260]}, status_code=403)

    @app.get('/', response_class=HTMLResponse)
    def dashboard():
        source = (STATIC / 'index.html').read_text(encoding='utf-8')
        return source.replace('__TESLA_TOKEN_JSON__', json.dumps(app.state.secret))

    @app.get('/ui/{filename}')
    def static(filename: str):
        if filename not in ('app.js', 'styles.css', 'tesla-mark.png', 'tesla-favicon.png'):
            raise HTTPException(404)
        return FileResponse(STATIC / filename)

    @app.get('/api/status')
    def status():
        return app.state.service.status()

    @app.post('/api/project')
    def project(body: ProjectRequest):
        return app.state.service.select_project(body.path)

    @app.get('/api/files')
    def files():
        return {'files': app.state.service.files()}

    @app.get('/api/file')
    def read_file(path: str):
        return app.state.service.read_file(path)

    @app.get('/api/diff')
    def diff(path: str):
        return {'diff': app.state.service.diff(path)}

    @app.get('/api/team/report')
    def report():
        return app.state.service.team_report()

    @app.get('/api/jobs/history')
    def history():
        return {'jobs': app.state.service.job_history()}

    @app.get('/api/models')
    def models():
        return app.state.service.model_status()

    @app.post('/api/models')
    def choose_model(body: ProviderRequest):
        return app.state.service.select_model(body.provider)

    @app.post('/api/chat')
    def chat(body: PromptRequest):
        return app.state.service.chat(body.prompt)

    @app.post('/api/team/plan')
    def team_plan(body: ObjectiveRequest):
        return app.state.service.create_team(body.objective)

    @app.post('/api/team/run')
    def team_run():
        return app.state.service.run_team()

    @app.post('/api/team/retry/{step_id}')
    def team_retry(step_id: int):
        return app.state.service.retry_team(step_id)

    @app.post('/api/team/cancel')
    def team_cancel():
        return app.state.service.cancel_team_plan()

    @app.post('/api/team/rework')
    def team_rework():
        return app.state.service.rework_team()

    @app.post('/api/test')
    def run_tests(body: TestRequest):
        return app.state.service.test(body.target)

    @app.get('/api/memory')
    def memory():
        return {'notes': app.state.service.project_memory()}

    @app.post('/api/remember')
    def remember(body: RecallRequest):
        return app.state.service.remember(body.query)

    @app.post('/api/recall')
    def recall(body: RecallRequest):
        return app.state.service.recall(body.query)

    @app.get('/api/tools')
    def tools():
        return app.state.service.tools_status()

    @app.get('/api/events')
    def events(after: int = 0):
        if after < 0:
            raise ValueError('Sequência inválida')
        return {'events': app.state.service.events_after(after)}

    @app.post('/api/approvals/{request_id}')
    def approve(request_id: str, body: ApprovalRequest):
        if not app.state.service.approvals.answer(request_id, body.approved):
            raise HTTPException(status_code=404, detail='Aprovação expirada ou já utilizada')
        return {'accepted': True}

    @app.post('/api/jobs/{job_id}/cancel')
    def cancel(job_id: str):
        return app.state.service.request_cancel(job_id)

    @app.websocket('/ws')
    async def websocket(ws: WebSocket):
        host = ws.headers.get('host', '')
        origin = ws.headers.get('origin')
        token = ws.query_params.get('token', '')
        if (not _host_ok(host) or not _origin_ok(origin, host) or
                not secrets.compare_digest(token, app.state.secret)):
            await ws.close(code=1008)
            return
        await ws.accept()
        last_id = 0
        try:
            while True:
                events = app.state.service.events_after(last_id)
                for event in events:
                    await ws.send_json(event)
                    last_id = event['id']
                await asyncio.sleep(0.35)
        except (WebSocketDisconnect, RuntimeError, OSError):
            pass

    return app
