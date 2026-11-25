from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.clock import from_aware, utc_iso


class DeliveryRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    recipient: str = Field(min_length=1, max_length=120)
    due_at: datetime

    @field_validator('due_at', mode='before')
    @classmethod
    def require_iso_string(cls, value):
        if not isinstance(value, str) or 'T' not in value:
            raise ValueError('Use an ISO timestamp with a time-zone offset')
        return value

    @field_validator('due_at')
    @classmethod
    def require_offset(cls, value):
        return from_aware(value).replace(microsecond=0)


def describe(delivery, include_report=False):
    data = {'id': delivery.id, 'run_id': delivery.run_id, 'recipient': delivery.recipient,
            'scheduled_by': delivery.scheduled_by, 'due_at': utc_iso(delivery.due_at),
            'created_at': utc_iso(delivery.created_at),
            'status': 'delivered' if delivery.delivered_at else 'scheduled',
            'delivered_at': utc_iso(delivery.delivered_at) if delivery.delivered_at else None}
    if include_report:
        data['report'] = delivery.report
    return data
