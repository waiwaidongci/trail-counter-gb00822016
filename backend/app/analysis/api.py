from fastapi import APIRouter, Depends

from app.analysis.contracts import ReviewRequest, RunRequest, describe_review
from app.analysis.models import Review
from app.analysis.repository import get_run, request_run
from app.analysis.review import record_review
from app.auth.dependencies import account, require
from app.auth.roles import Role
from app.clock import utc_iso
from app.database import Session


router = APIRouter(tags=['Analysis and review'])
analyst = require(Role.analyst)
reviewer = require(Role.reviewer)


def describe(run, review=None):
    return {'id': run.id, 'dataset_id': run.dataset_id, 'status': run.status,
            'options': run.options, 'result': run.result, 'error': run.error,
            'requested_by': run.requested_by, 'created_at': utc_iso(run.created_at),
            'finished_at': utc_iso(run.finished_at) if run.finished_at else None,
            'review': describe_review(review)}


@router.post('/datasets/{dataset_id}/runs', status_code=202)
def start(dataset_id: int, payload: RunRequest, user=Depends(analyst)):
    return describe(request_run(dataset_id, payload.options.model_dump(mode='json'), user.email))


@router.get('/runs/{run_id}')
def status(run_id: int, user=Depends(account)):
    with Session() as db:
        return describe(get_run(db, run_id), db.get(Review, run_id))


@router.post('/runs/{run_id}/review', status_code=201)
def review(run_id: int, payload: ReviewRequest, user=Depends(reviewer)):
    return describe_review(record_review(run_id, payload.decision, payload.note, user.email))
