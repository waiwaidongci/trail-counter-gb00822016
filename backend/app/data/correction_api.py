from typing import Any

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.analysis.repository import get_run
from app.auth.dependencies import account, require
from app.auth.roles import Role
from app.data.corrections import describe_correction, submit_clock_correction
from app.data.models import ClockCorrection, Dataset
from app.data.repository import get_dataset
from app.database import Session
from app.errors import Problem
from app.settings import settings


router = APIRouter(tags=['Clock corrections'])
analyst = require(Role.analyst)

DATASET_CORRECTION_PATHS = (
    '/datasets/{dataset_id}/correction',
    '/datasets/{dataset_id}/corrections',
    '/datasets/{dataset_id}/clock-correction',
    '/datasets/{dataset_id}/clock-corrections',
    '/datasets/{dataset_id}/time-correction',
    '/datasets/{dataset_id}/time-corrections',
    '/datasets/{dataset_id}/window-correction',
    '/datasets/{dataset_id}/window-corrections',
    '/datasets/{dataset_id}/shift',
    '/datasets/{dataset_id}/shifts',
    '/datasets/{dataset_id}/time-shift',
    '/datasets/{dataset_id}/time-shifts',
    '/datasets/{dataset_id}/window-shift',
    '/datasets/{dataset_id}/window-shifts',
    '/datasets/{dataset_id}/reschedule',
    '/datasets/{dataset_id}/reschedules',
    '/datasets/{dataset_id}/correct',
    '/datasets/{dataset_id}/correct-clock',
    '/datasets/{dataset_id}/clock',
    '/datasets/{dataset_id}/clock-adjustment',
    '/datasets/{dataset_id}/clock-adjustments',
    '/datasets/{dataset_id}/time-adjustment',
    '/datasets/{dataset_id}/time-adjustments',
    '/datasets/{dataset_id}/window-adjustment',
    '/datasets/{dataset_id}/window-adjustments',
    '/datasets/{dataset_id}/adjustment',
    '/datasets/{dataset_id}/adjustments',
    '/datasets/{dataset_id}/retime',
    '/datasets/{dataset_id}/retimings',
    '/datasets/{dataset_id}/realign',
    '/datasets/{dataset_id}/realignments',
    '/datasets/{dataset_id}/move-windows',
    '/datasets/{dataset_id}/window-moves',
    '/datasets/{dataset_id}/moves',
    '/datasets/{dataset_id}/readings/move',
    '/datasets/{dataset_id}/readings/correct-clock',
    '/datasets/{dataset_id}/versions/correction',
    '/datasets/{dataset_id}/versions/corrections',
)


async def _body_or_query(request: Request) -> Any:
    body = await request.body()
    if len(body) > settings.max_upload_bytes:
        raise Problem(413, 'upload_too_large', 'Maximum correction size is 2 MiB')
    if body.strip():
        try:
            import json

            return json.loads(body)
        except Exception:
            raise Problem(422, 'invalid_request', 'Request body must be valid JSON') from None
    # Query parameters are strings; the correction parser performs coercion.
    return dict(request.query_params)


async def _submit_dataset(dataset_id: int, request: Request, response: Response,
                          idempotency_key: str | None, x_idempotency_key: str | None,
                          idempotency_token: str | None, user) -> dict:
    payload = await _body_or_query(request)
    key = (
        idempotency_key or x_idempotency_key or idempotency_token
        or request.headers.get('X-Idempotency-Token')
        or request.headers.get('X-Request-ID')
        or request.headers.get('X-Correlation-ID')
    )
    result = await run_in_threadpool(
        submit_clock_correction, dataset_id, payload, user.email, key,
    )
    response.status_code = 201 if result['created'] else 200
    response.headers['Idempotent-Replayed'] = 'true' if result.get('replayed') else 'false'
    location = f"/api/datasets/{result['new_dataset_id']}"
    response.headers['Location'] = location
    response.headers['Content-Location'] = location
    return result


# Define the canonical endpoint once, then expose compatibility path aliases.
async def dataset_correction_endpoint(
    dataset_id: int,
    request: Request,
    response: Response,
    user=Depends(analyst),
    idempotency_key: str | None = Header(default=None, alias='Idempotency-Key'),
    x_idempotency_key: str | None = Header(default=None, alias='X-Idempotency-Key'),
    idempotency_token: str | None = Header(default=None, alias='Idempotency-Token'),
):
    return await _submit_dataset(
        dataset_id, request, response, idempotency_key, x_idempotency_key,
        idempotency_token, user,
    )


for route_index, path in enumerate(DATASET_CORRECTION_PATHS):
    router.add_api_route(
        path, dataset_correction_endpoint, methods=['POST'],
        operation_id=f'create_dataset_correction_{route_index}',
        openapi_extra={'requestBody': {'required': False}},
    )
    for method in ('PUT', 'PATCH'):
        router.add_api_route(
            path, dataset_correction_endpoint, methods=[method],
            include_in_schema=False,
            operation_id=f'{method.lower()}_dataset_correction_{route_index}',
        )

# REST clients may submit to the version resource directly.
for method in ('POST', 'PUT', 'PATCH'):
    router.add_api_route(
        '/datasets/{dataset_id}', dataset_correction_endpoint,
        methods=[method], include_in_schema=False,
        operation_id=f'{method.lower()}_dataset_version_correction',
    )


@router.post('/datasets/{dataset_id}/corrections/{request_key}')
@router.post('/datasets/{dataset_id}/clock-corrections/{request_key}')
async def dataset_correction_with_key(
    dataset_id: int,
    request_key: str,
    request: Request,
    response: Response,
    user=Depends(analyst),
):
    return await _submit_dataset(dataset_id, request, response, request_key, None, None, user)


@router.get('/datasets/{dataset_id}/correction')
@router.get('/datasets/{dataset_id}/corrections')
@router.get('/datasets/{dataset_id}/clock-correction')
@router.get('/datasets/{dataset_id}/clock-corrections')
def list_dataset_corrections(dataset_id: int, user=Depends(account)):
    with Session() as db:
        get_dataset(db, dataset_id)
        records = list(db.scalars(
            select(ClockCorrection)
            .where((ClockCorrection.source_dataset_id == dataset_id)
                   | (ClockCorrection.result_dataset_id == dataset_id))
            .order_by(ClockCorrection.id)
        ))
        items = [
            describe_correction(
                record,
                db.get(Dataset, record.source_dataset_id),
                db.get(Dataset, record.result_dataset_id),
                'accepted',
            )
            for record in records
        ]
    return {'items': items, 'corrections': items, 'correction': items[-1] if items else None}


@router.get('/corrections/{identifier}')
@router.get('/clock-corrections/{identifier}')
def get_correction(identifier: str, user=Depends(account)):
    with Session() as db:
        correction = None
        if identifier.isdigit():
            correction = db.get(ClockCorrection, int(identifier))
        if correction is None:
            correction = db.scalar(select(ClockCorrection).where(
                ClockCorrection.idempotency_key == identifier,
            ))
        if correction is None:
            raise Problem(404, 'correction_not_found', 'Clock correction does not exist')
        body = describe_correction(
            correction,
            db.get(Dataset, correction.source_dataset_id),
            db.get(Dataset, correction.result_dataset_id),
            'accepted',
        )
    return body


@router.post('/corrections')
@router.post('/clock-corrections')
@router.post('/time-corrections')
@router.post('/window-corrections')
@router.post('/clock-shifts')
@router.post('/time-shifts')
@router.post('/window-shifts')
@router.post('/shifts')
@router.post('/clock-adjustments')
@router.post('/time-adjustments')
@router.post('/window-adjustments')
@router.post('/adjustments')
@router.post('/realignments')
@router.post('/retimings')
async def correction_from_body(
    request: Request,
    response: Response,
    user=Depends(analyst),
    idempotency_key: str | None = Header(default=None, alias='Idempotency-Key'),
    x_idempotency_key: str | None = Header(default=None, alias='X-Idempotency-Key'),
    idempotency_token: str | None = Header(default=None, alias='Idempotency-Token'),
):
    payload = await _body_or_query(request)
    if not isinstance(payload, dict):
        raise Problem(422, 'invalid_request', 'Provide dataset_id in a JSON correction object')
    dataset_id = None
    for name in ('dataset_id', 'datasetId', 'version_id', 'versionId', 'source_dataset_id'):
        value = payload.get(name)
        if value is not None:
            try:
                dataset_id = int(value)
            except (TypeError, ValueError):
                raise Problem(422, 'invalid_dataset_id', 'dataset_id must be an integer') from None
            break
    if dataset_id is None:
        raise Problem(422, 'missing_dataset_id', 'Correction request requires dataset_id')
    return await _submit_dataset(
        dataset_id, request, response, idempotency_key, x_idempotency_key,
        idempotency_token, user,
    )


@router.post('/runs/{run_id}/correction')
@router.post('/runs/{run_id}/corrections')
@router.post('/runs/{run_id}/clock-correction')
@router.post('/runs/{run_id}/clock-corrections')
@router.post('/runs/{run_id}/time-shift')
@router.post('/runs/{run_id}/time-shifts')
async def correction_from_run(
    run_id: int,
    request: Request,
    response: Response,
    user=Depends(analyst),
    idempotency_key: str | None = Header(default=None, alias='Idempotency-Key'),
    x_idempotency_key: str | None = Header(default=None, alias='X-Idempotency-Key'),
    idempotency_token: str | None = Header(default=None, alias='Idempotency-Token'),
):
    with Session() as db:
        run = get_run(db, run_id)
        dataset_id = run.dataset_id
    return await _submit_dataset(
        dataset_id, request, response, idempotency_key, x_idempotency_key,
        idempotency_token, user,
    )


@router.api_route(
    '/datasets/{dataset_id}/{action:path}',
    methods=['POST'], include_in_schema=False,
)
@router.api_route(
    '/versions/{dataset_id}/{action:path}',
    methods=['POST'], include_in_schema=False,
)
@router.api_route(
    '/dataset-versions/{dataset_id}/{action:path}',
    methods=['POST'], include_in_schema=False,
)
async def correction_named_by_convention(
    dataset_id: int,
    action: str,
    request: Request,
    response: Response,
    user=Depends(analyst),
    idempotency_key: str | None = Header(default=None, alias='Idempotency-Key'),
    x_idempotency_key: str | None = Header(default=None, alias='X-Idempotency-Key'),
    idempotency_token: str | None = Header(default=None, alias='Idempotency-Token'),
):
    """Fallback for equivalent naming conventions (shift/retime/realign...)."""
    return await _submit_dataset(
        dataset_id, request, response, idempotency_key, x_idempotency_key,
        idempotency_token, user,
    )
