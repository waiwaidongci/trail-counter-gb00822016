from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select

from app.analysis.repository import get_run
from app.auth.dependencies import account, require
from app.auth.roles import Role
from app.database import Session
from app.delivery.contracts import DeliveryRequest, describe
from app.delivery.models import Delivery
from app.delivery.report import approved_report, export_table
from app.delivery.schedule import schedule


router = APIRouter(tags=['Reports and distribution'])
reviewer = require(Role.reviewer)


@router.get('/runs/{run_id}/report')
def report(run_id: int, user=Depends(account)):
    with Session() as db:
        return approved_report(db, get_run(db, run_id))


@router.get('/runs/{run_id}/report/csv')
def report_csv(run_id: int, table: Annotated[str, Query(min_length=1, max_length=120)], user=Depends(account)):
    with Session() as db:
        content = export_table(approved_report(db, get_run(db, run_id)), table)
    return Response(content, media_type='text/csv',
                    headers={'Content-Disposition': f'attachment; filename="run-{run_id}.csv"'})


@router.post('/runs/{run_id}/deliveries')
def plan(run_id: int, payload: DeliveryRequest, response: Response, user=Depends(reviewer)):
    delivery, created = schedule(run_id, payload.recipient, payload.due_at, user.email)
    response.status_code = 201 if created else 200
    return describe(delivery)


@router.get('/inbox')
def inbox(user=Depends(account), limit: Annotated[int, Query(ge=1, le=100)] = 25):
    with Session() as db:
        query = (select(Delivery).where(Delivery.recipient == user.email, Delivery.delivered_at.is_not(None))
                 .order_by(Delivery.id.desc()).limit(limit))
        return [describe(item, include_report=True) for item in db.scalars(query)]
