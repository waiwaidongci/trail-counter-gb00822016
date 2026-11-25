import logging
import signal
from threading import Event

from redis import RedisError
from sqlalchemy.exc import SQLAlchemyError

from app.analysis.runner import run_next
from app.delivery.schedule import deliver_next
from app.ops.redis_bus import HEARTBEAT, QUEUE, redis_client


LOG = logging.getLogger('analytics.worker')


def serve():
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    while not stop.is_set():
        try:
            redis_client.set(HEARTBEAT, 'ready', ex=45)
        except RedisError:
            LOG.warning('Worker could not update Redis heartbeat')
        try:
            sent = deliver_next()
            computed = run_next()
            if not sent and not computed:
                redis_client.blpop(QUEUE, timeout=1)
        except (SQLAlchemyError, RedisError):
            LOG.exception('Worker dependency failure')
            stop.wait(2)
    try:
        redis_client.delete(HEARTBEAT)
    except RedisError:
        LOG.warning('Worker heartbeat will expire')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    serve()
