from sqlalchemy import select

from app.analysis.contracts import RunStatus
from app.analysis.models import AnalysisRun
from app.data.repository import get_dataset
from app.database import Session
from app.errors import Problem
from app.ops.audit import audit
from app.ops.redis_bus import wake_worker


def request_run(dataset_id: int, options: dict, actor: str) -> AnalysisRun:
    with Session.begin() as db:
        get_dataset(db, dataset_id)
        run = AnalysisRun(dataset_id=dataset_id, options=options,
                          status=RunStatus.queued, requested_by=actor)
        db.add(run)
        db.flush()
        audit(db, actor, 'run_queued', f'run/{run.id}')
    wake_worker()
    return run


def get_run(db, run_id: int, lock: bool = False) -> AnalysisRun:
    query = select(AnalysisRun).where(AnalysisRun.id == run_id)
    run = db.scalar(query.with_for_update() if lock else query)
    if run is None:
        raise Problem(404, 'run_not_found', 'Analysis run does not exist')
    return run
