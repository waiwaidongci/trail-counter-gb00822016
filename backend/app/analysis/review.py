from app.analysis.contracts import Decision, RunStatus
from app.analysis.models import Review
from app.analysis.repository import get_run
from app.database import Session
from app.errors import Problem
from app.ops.audit import audit


def record_review(run_id, decision, note, actor):
    with Session.begin() as db:
        run = get_run(db, run_id, lock=True)
        if run.status != RunStatus.completed:
            raise Problem(409, 'run_not_completed', 'Only completed analysis runs can be reviewed')
        if db.get(Review, run_id) is not None:
            raise Problem(409, 'already_reviewed', 'This run already has a review')
        if decision == Decision.approved and not run.result['publishable']:
            raise Problem(409, 'publication_blocked', 'The analysis did not pass its publication checks')
        review = Review(run_id=run_id, decision=decision, note=note, reviewer=actor)
        db.add(review)
        audit(db, actor, f'review_{decision.value}', f'run/{run_id}')
        db.flush()
        return review
