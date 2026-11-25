# Import every model before applying the initial schema.
from app.analysis.models import AnalysisRun, Review
from app.auth.models import Account
from app.data.models import Dataset, Observation
from app.delivery.models import Delivery
from app.ops.audit import AuditEvent
from app.database import Base, engine


def initialize():
    Base.metadata.create_all(engine)
