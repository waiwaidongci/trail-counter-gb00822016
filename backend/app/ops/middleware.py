import logging
from time import perf_counter
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware


class RequestContext(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.request_id = uuid4().hex
        response = await call_next(request)
        response.headers['X-Request-ID'] = request.state.request_id
        return response


class AccessTiming(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = perf_counter()
        response = await call_next(request)
        elapsed = 1000 * (perf_counter() - start)
        response.headers['Server-Timing'] = f'app;dur={elapsed:.1f}'
        logging.getLogger('analytics.access').info('%s %s %s %.1fms', request.method,
                                                  request.url.path, response.status_code, elapsed)
        return response
