from fastapi import APIRouter
from redis import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import Session
from app.errors import Problem
from app.ops.redis_bus import HEARTBEAT, redis_client


router = APIRouter(tags=['Operations'])


@router.get('/health')
def health():
    try:
        with Session() as db:
            db.execute(text('SELECT 1')).scalar_one()
        redis_client.ping()
    except (RedisError, SQLAlchemyError):
        raise Problem(503, 'dependency_unavailable', 'Database or Redis unavailable') from None
    return {'status': 'ok', 'database': 'ok', 'redis': 'ok'}


@router.get('/health/worker')
def worker_health():
    try:
        alive = redis_client.exists(HEARTBEAT)
    except RedisError:
        alive = False
    if not alive:
        raise Problem(503, 'worker_unavailable', 'Worker heartbeat is missing')
    return {'status': 'ok'}
