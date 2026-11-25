from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.concurrency import run_in_threadpool

from app.analysis.api import router as analysis_api
from app.auth.api import router as auth_api
from app.data.api import router as data_api
from app.delivery.api import router as delivery_api
from app.errors import Problem, problem_handler, validation_handler
from app.ops.admin_api import router as admin_api
from app.ops.health import router as health_api
from app.ops.middleware import AccessTiming, RequestContext
from app.settings import settings
from domain.spec import METHOD, TITLE
from scripts.init_db import initialize
from scripts.seed_demo import load_demo


@asynccontextmanager
async def lifespan(app):
    await run_in_threadpool(initialize)
    if settings.seed_demo:
        try:
            await run_in_threadpool(load_demo)
        except Exception:
            logging.getLogger(__name__).exception('Demo data initialization failed')
    yield


app = FastAPI(title=TITLE, description=METHOD, lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_exception_handler(Problem, problem_handler)
app.add_exception_handler(RequestValidationError, validation_handler)
app.add_middleware(AccessTiming)
app.add_middleware(RequestContext)
for router in (auth_api, data_api, analysis_api, delivery_api, admin_api):
    app.include_router(router, prefix='/api')
app.include_router(health_api)
