from app.ops.redis_bus import HEARTBEAT, redis_client


if __name__ == '__main__':
    raise SystemExit(0 if redis_client.exists(HEARTBEAT) else 1)
