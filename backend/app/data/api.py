import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import ValidationError
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import account, require
from app.auth.roles import Role
from app.clock import utc_iso
from app.data.contracts import DatasetImport
from app.data.csv_input import parse_csv
from app.data.models import ClockCorrection, Dataset
from app.data.repository import get_dataset, import_dataset, observation_query
from app.database import Session
from app.errors import Problem
from app.settings import settings


router = APIRouter(prefix='/datasets', tags=['Data intake'])
analyst = require(Role.analyst)


def describe(dataset):
    return {'id': dataset.id, 'name': dataset.name, 'checksum': dataset.checksum,
            'row_count': dataset.row_count, 'created_by': dataset.created_by,
            'created_at': utc_iso(dataset.created_at)}


async def bounded_upload(request: Request) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > settings.max_upload_bytes:
            raise Problem(413, 'upload_too_large', 'Maximum upload size is 2 MiB')
        body.extend(chunk)
    return bytes(body)


@router.get('')
def list_datasets(user=Depends(account), limit: Annotated[int, Query(ge=1, le=100)] = 25):
    with Session() as db:
        datasets = db.scalars(select(Dataset).order_by(Dataset.id.desc()).limit(limit))
        return [describe(dataset) for dataset in datasets]


@router.get('/{dataset_id}')
def dataset_detail(dataset_id: int, user=Depends(account)):
    with Session() as db:
        return describe(get_dataset(db, dataset_id))


@router.get('/{dataset_id}/rows')
def rows(dataset_id: int, user=Depends(account),
         offset: Annotated[int, Query(ge=0)] = 0, limit: Annotated[int, Query(ge=1, le=250)] = 50):
    with Session() as db:
        dataset = get_dataset(db, dataset_id)
        records = list(db.scalars(observation_query(dataset_id).offset(offset).limit(limit)))
        correction = db.scalar(select(ClockCorrection).where(
            ClockCorrection.result_dataset_id == dataset_id,
        ).order_by(ClockCorrection.id.desc()))
    response = {'dataset': describe(dataset), 'offset': offset, 'rows': records}
    if correction is not None:
        response['correction_id'] = correction.id
        response['source_dataset_id'] = correction.source_dataset_id
        response['movements'] = correction.movements
        response['moved_readings'] = correction.movements
        response['original_windows'] = correction.movements
    return response


@router.post('', openapi_extra={'requestBody': {'required': True, 'content': {
    'application/json': {'schema': DatasetImport.model_json_schema()},
    'text/csv': {'schema': {'type': 'string'}},
}}})
async def ingest(request: Request, response: Response, user=Depends(analyst),
                 name: Annotated[str | None, Query(max_length=120)] = None):
    media = request.headers.get('content-type', '').split(';', 1)[0].strip().lower()
    if media not in {'application/json', 'text/csv'}:
        raise Problem(415, 'unsupported_media_type', 'Use application/json or text/csv')
    body = await bounded_upload(request)
    if media == 'text/csv':
        if name is None:
            raise Problem(422, 'missing_name', 'Provide the CSV dataset name as a query parameter')
        records = await run_in_threadpool(parse_csv, body)
    else:
        try:
            payload = DatasetImport.model_validate_json(body)
        except (ValidationError, json.JSONDecodeError):
            raise Problem(422, 'invalid_request', 'Provide a JSON name and a nonempty rows array') from None
        name, records = payload.name, payload.rows
    dataset, created = await run_in_threadpool(import_dataset, name, records, user.email)
    response.status_code = 201 if created else 200
    return {**describe(dataset), 'created': created}
