"""Single-instance API. SQLite stays on the server's persistent disk, never on a share."""
from collections import deque
import time
import asyncio
import inspect
import json
import logging
import os
import tempfile
import sqlite3
import threading
import uuid
from contextlib import contextmanager, asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from app.database.connection import Database
from app.models.entities import Auditoria, Configuracao
from app.utils.clock import now
from app.services.agenda import AgendaService
from app.services.backup import BackupService
from app.utils.wire import encode, decode
from server.security import Security


class TransactionDatabase(Database):
    def __init__(self, path):
        self.local = threading.local()
        super().__init__(path)

    @contextmanager
    def session(self):
        current = getattr(self.local, 'session', None)
        if current is not None:
            yield current
        else:
            with super().session() as session:
                self.local.session = session
                try:
                    yield session
                finally:
                    self.local.session = None


class Login(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=256)


class Mutation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    method: str
    args: list = Field(default_factory=list, max_length=4)
    kwargs: dict = Field(default_factory=dict)
    revision: str
    request_id: uuid.UUID


class UserCreate(Login):
    role: str = 'editor'


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, max_length=256)
    active: bool | None = None


WRITES = {'save_condo','delete_condo','save_event','set_state','delete_event'}


def create_app(directory=None, admin_email=None, admin_password=None, run_scheduler=True):
    lock = threading.RLock()
    state = {}
    login_times = deque()

    def revision():
        return state['db'].get_setting('online_revision')

    def bump():
        value = str(uuid.uuid4())
        state['db'].set_setting('online_revision', value)
        return value

    def maintenance():
        with lock:
            db, service, backup = state['db'], state['service'], state['backup']
            today = now().date().isoformat()
            if db.get_setting('server_backup_day') != today:
                backup.create(db.path.parent / 'backups')
                db.set_setting('server_backup_day', today)

    @asynccontextmanager
    async def lifespan(app):
        location = Path(directory or os.environ.get('AGENDA_SERVER_DIR', '/var/data/agenda'))
        location.mkdir(parents=True, exist_ok=True)
        # OS file lock forbids accidental multiple uvicorn workers/processes.
        guard = open(location / 'server.lock', 'a+b')
        if os.name != 'nt':
            import fcntl
            fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        db = TransactionDatabase(location / 'agenda.sqlite3')
        state.update(db=db, service=AgendaService(db), backup=BackupService(db))
        state['security'] = Security(location / 'acessos.sqlite3',
            admin_email or os.environ.get('AGENDA_ADMIN_EMAIL', ''),
            admin_password or os.environ.get('AGENDA_ADMIN_PASSWORD', ''))
        if not revision():
            bump()
        async def schedule():
            while True:
                try:
                    await asyncio.to_thread(maintenance)
                except Exception:
                    logging.exception('Falha na manutenção diária')
                await asyncio.sleep(60)
        task = asyncio.create_task(schedule()) if run_scheduler else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            with lock:
                db.engine.dispose()
            guard.close()

    app = FastAPI(title='AgendaCondominial', version='1.0.0', lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.services = state

    @app.middleware('http')
    async def limits(request: Request, call_next):
        limit = 25 * 1024 * 1024 if request.url.path == '/v1/import' else 128 * 1024
        try:
            if int(request.headers.get('content-length', 0)) > limit:
                return Response('Arquivo muito grande.', status_code=413)
            total = 0
            parts = []
            async for chunk in request.stream():
                total += len(chunk)
                if total > limit:
                    return Response('Arquivo muito grande.', status_code=413)
                parts.append(chunk)
            request._body = b''.join(parts)
        except ValueError:
            return Response(status_code=400)
        result = await call_next(request)
        result.headers['Cache-Control'] = 'no-store'
        result.headers['X-Content-Type-Options'] = 'nosniff'
        return result

    def authenticated(authorization: str = Header(default='')):
        if not authorization.startswith('Bearer '):
            raise HTTPException(401, 'Entre com seu e-mail e senha.')
        user = state['security'].user(authorization[7:])
        if not user:
            raise HTTPException(401, 'Sessão expirada. Feche e abra o aplicativo para entrar novamente.')
        return user

    def admin(user=Depends(authenticated)):
        if user['role'] != 'admin':
            raise HTTPException(403, 'Somente administradores podem realizar esta operação.')
        return user

    @app.get('/health')
    def health():
        return {'status': 'ok', 'version': '1.0.0', 'application': 'AgendaCondominial'}

    @app.post('/v1/login')
    def login(body: Login):
        with lock:
            now = time.monotonic()
            while login_times and login_times[0] < now - 60:
                login_times.popleft()
            if len(login_times) >= 60:
                raise HTTPException(429, 'Muitas tentativas. Aguarde um minuto.')
            login_times.append(now)
            try:
                return state['security'].login(body.email, body.password)
            except ValueError as exc:
                raise HTTPException(401, str(exc)) from None

    @app.post('/v1/logout')
    def logout(user=Depends(authenticated), authorization: str = Header()):
        state['security'].logout(authorization[7:])
        return {'ok': True}

    @app.get('/v1/snapshot')
    def snapshot(user=Depends(authenticated)):
        with lock:
            f = state['service']
            return encode({'revision': revision(), **f.snapshot()})

    def validate_args(method, args, kwargs):
        fn = getattr(state['service'], method)
        inspect.signature(fn).bind(*args, **kwargs)
        return fn

    @app.post('/v1/mutate')
    def mutate(body: Mutation, user=Depends(authenticated)):
        if body.method not in WRITES:
            raise HTTPException(400, 'Operação não permitida.')
        with lock:
            db = state['db']
            receipt_key = 'request:' + str(body.request_id)
            try:
                with db.session() as s:
                    old = db.get_setting(receipt_key)
                    signature = json.dumps(body.model_dump(mode='json'), sort_keys=True)
                    if old:
                        saved = json.loads(old)
                        if saved['user'] != user['id'] or saved['signature'] != signature:
                            raise HTTPException(409, 'Identificador de operação já utilizado.')
                        return saved['response']
                    if body.revision != revision():
                        raise HTTPException(409, 'Outra pessoa alterou os dados. Volte à lista, atualize e abra o formulário novamente.')
                    args, kwargs = decode(body.args), decode(body.kwargs)
                    fn = validate_args(body.method, args, kwargs)
                    result = fn(*args, **kwargs)
                    s.add(Auditoria(acao='Operação online', detalhes=f"{user['email']} | {body.method} | {body.request_id}"))
                    response = encode({'result': result, 'revision': bump()})
                    db.set_setting(receipt_key, json.dumps({'user': user['id'], 'signature': signature, 'response': response}))
                    return response
            except HTTPException:
                raise
            except (ValueError, TypeError, KeyError) as exc:
                raise HTTPException(400, str(exc)) from None
            except Exception:
                logging.exception('Falha na operação da agenda')
                raise HTTPException(400, 'Não foi possível salvar. Confira os dados e atualize a lista.') from None

    @app.get('/v1/users')
    def users(user=Depends(admin)):
        return state['security'].users()

    @app.post('/v1/users')
    def create_user(body: UserCreate, user=Depends(admin)):
        with lock:
            try:
                state['security'].add_user(body.email, body.password, body.role)
                return {'ok': True}
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from None

    @app.patch('/v1/users/{user_id}')
    def update_user(user_id: int, body: UserUpdate, user=Depends(admin)):
        if user_id == user['id'] and body.active is not None:
            raise HTTPException(400, 'Não é possível desativar seu próprio acesso.')
        with lock:
            try:
                state['security'].update(user_id, body.password, body.active)
                return {'ok': True}
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from None

    @app.get('/v1/backup')
    def download_backup(user=Depends(admin)):
        with lock:
            path = state['backup'].create(state['db'].path.parent / 'backups')
            return Response(path.read_bytes(), media_type='application/octet-stream',
                headers={'Content-Disposition': 'attachment; filename="AgendaCondominial.sqlite3"'})

    @app.post('/v1/import')
    async def import_initial(request: Request, user=Depends(admin)):
        content = await request.body()
        with lock:
            f, db = state['service'], state['db']
            if f.events() or f.condos():
                raise HTTPException(409, 'A importação inicial exige um servidor sem cadastros. Não mistura nem substitui dados existentes.')
            fd, name = tempfile.mkstemp(suffix='.sqlite3', dir=db.path.parent)
            os.close(fd)
            try:
                Path(name).write_bytes(content)
                state['backup'].validate(name)
                safety = state['backup'].restore(name)
                # Discard local machine settings and idempotency receipts from imported file.
                with db.session() as s:
                    s.query(Configuracao).filter(Configuracao.chave != 'schema_version').delete()
                    bump()
                    s.add(Auditoria(acao='Importação inicial', detalhes=user['email']))
                return {'ok': True}
            except (ValueError, OSError, sqlite3.DatabaseError) as exc:
                raise HTTPException(400, str(exc)) from None
            finally:
                Path(name).unlink(missing_ok=True)

    return app


app = create_app()
