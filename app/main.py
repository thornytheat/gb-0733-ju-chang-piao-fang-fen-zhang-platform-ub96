import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import runs, web
from app.config import PREVIEW, ROOT, SAMPLE_BOOK
from app.errors import Problem
from app.modules.m1_intake import handler as intake
from app.modules.m2_rights import handler as rights
from app.modules.m3_scans import handler as scans
from app.modules.m4_allocation import handler as allocation
from app.modules.m5_refunds import handler as refunds
from app.modules.m6_reconcile import handler as reconcile
from app.modules.m7_evidence import handler as evidence
from app.pipeline import compute
from app.reasons import REASONS
from app.sources import sample_sources
from app.store import Store


def create_app(db_path=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.store = Store(db_path or os.environ.get('THEATRE_DB_PATH', ROOT / 'data' / 'theatre.sqlite3'))
        app.state.store.initialize()
        app.state.preview = compute(SAMPLE_BOOK, PREVIEW, sample_sources())
        yield

    app = FastAPI(title='剧场票房分账台', lifespan=lifespan)
    app.mount('/static', StaticFiles(directory=ROOT / 'app' / 'static'), name='static')
    for module in (web, runs, intake, rights, scans, allocation, refunds, reconcile, evidence):
        app.include_router(module.router)

    @app.exception_handler(Problem)
    def domain_error(_: Request, exc: Problem):
        return JSONResponse({'code': exc.code, 'message': REASONS[exc.code], 'detail': exc.detail}, status_code=exc.status)

    @app.get('/healthz')
    def health():
        return {'status': 'ok'}

    return app


app = create_app()
