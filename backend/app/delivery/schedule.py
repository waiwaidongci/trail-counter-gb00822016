from datetime import timedelta

from sqlalchemy import select

from app.analysis.repository import get_run
from app.auth.models import Account
from app.clock import now_utc
from app.database import Session
from app.delivery.models import Delivery
from app.delivery.report import approved_report
from app.errors import Problem
from app.ops.audit import audit
from app.ops.redis_bus import wake_worker


def schedule(run_id, recipient, due_at, actor):
    recipient = recipient.strip().lower()
    with Session.begin() as db:
        run = get_run(db, run_id, lock=True)
        report = approved_report(db, run)
        if db.get(Account, recipient) is None:
            raise Problem(422, 'unknown_recipient', 'Recipient must be a local account')
        previous = db.scalar(select(Delivery).where(
            Delivery.run_id == run_id, Delivery.recipient == recipient, Delivery.due_at == due_at))
        if previous:
            return previous, False
        delta = due_at - now_utc()
        if delta < -timedelta(days=7) or delta > timedelta(days=90):
            raise Problem(422, 'due_date_range', 'Due time may be up to 7 days past or 90 days ahead')
        delivery = Delivery(run_id=run_id, recipient=recipient, due_at=due_at,
                            scheduled_by=actor, report=report)
        db.add(delivery)
        db.flush()
        audit(db, actor, 'delivery_scheduled', f'delivery/{delivery.id}')
    wake_worker()
    return delivery, True


def deliver_next() -> bool:
    with Session.begin() as db:
        now = now_utc()
        query = (select(Delivery).where(Delivery.delivered_at.is_(None), Delivery.due_at <= now)
                 .order_by(Delivery.due_at, Delivery.id).limit(1).with_for_update(skip_locked=True))
        delivery = db.scalar(query)
        if delivery is None:
            return False
        delivery.delivered_at = now
        audit(db, 'worker', 'delivery_sent', f'delivery/{delivery.id}')
        return True
