from enum import StrEnum

from pydantic import BaseModel, ConfigDict, StringConstraints
from typing import Annotated

from domain.spec import OPTIONS_MODEL


class RunStatus(StrEnum):
    queued = 'queued'
    completed = 'completed'
    failed = 'failed'


class Decision(StrEnum):
    approved = 'approved'
    rejected = 'rejected'


class RunRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    options: OPTIONS_MODEL = OPTIONS_MODEL()


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Decision
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=800)]


def describe_review(review):
    from app.clock import utc_iso

    if review is None:
        return None
    return {'decision': review.decision, 'note': review.note, 'reviewer': review.reviewer,
            'created_at': utc_iso(review.created_at)}
