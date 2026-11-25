import logging

from redis import Redis, RedisError

from app.settings import settings


redis_client = Redis.from_url(settings.redis_url, decode_responses=True,
                              socket_connect_timeout=2, socket_timeout=4)
QUEUE = 'analysis:wakeup'
HEARTBEAT = 'worker:heartbeat'


def wake_worker():
    try:
        with redis_client.pipeline() as pipe:
            pipe.lpush(QUEUE, 'work').ltrim(QUEUE, 0, 31).execute()
    except RedisError:
        logging.getLogger(__name__).warning('Wake-up unavailable; queued work remains in the database')
