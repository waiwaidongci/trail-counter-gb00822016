from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class Problem(Exception):
    def __init__(self, status: int, code: str, detail: str):
        super().__init__(detail)
        self.status = status
        self.code = code
        self.detail = detail


async def problem_handler(request: Request, exc: Problem):
    return JSONResponse(status_code=exc.status, content={
        'error': {'code': exc.code, 'detail': exc.detail},
        'request_id': getattr(request.state, 'request_id', None),
    })


async def validation_handler(request: Request, exc: RequestValidationError):
    parts = ['.'.join(map(str, error['loc'])) + ': ' + error['msg']
             for error in exc.errors()[:8]]
    return await problem_handler(request, Problem(422, 'invalid_request', '; '.join(parts)))
