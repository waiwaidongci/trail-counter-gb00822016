from datetime import datetime, timezone


def now_utc() -> datetime:
    """Store UTC without tzinfo to use the same SQL type on both databases."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def from_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Include an explicit time zone offset')
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def utc_iso(value: datetime) -> str:
    return value.replace(tzinfo=timezone.utc).isoformat()
