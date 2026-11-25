from hashlib import sha256
import json

from pydantic import ValidationError

from app.errors import Problem
from app.settings import settings
from domain.spec import ROW_MODEL, record_key, validate_rows


def normalize(rows: list[dict]) -> tuple[str, list[tuple[str, dict]]]:
    if not 1 <= len(rows) <= settings.max_rows:
        raise Problem(422, 'invalid_row_count', f'Provide 1 to {settings.max_rows} observations')
    validated = []
    for position, row in enumerate(rows, 1):
        try:
            validated.append(ROW_MODEL.model_validate(row))
        except ValidationError as exc:
            first = exc.errors()[0]
            field = '.'.join(map(str, first['loc'])) or 'row'
            raise Problem(422, 'invalid_row', f'Row {position}, {field}: {first["msg"]}') from None
    try:
        validate_rows(validated)
        pairs = [(record_key(row), row.model_dump(mode='json')) for row in validated]
        if any(not isinstance(key, str) or not key.strip() for key, _ in pairs):
            raise ValueError('Observation keys must be nonempty strings')
        keys = {key for key, _ in pairs}
        if len(keys) != len(pairs):
            raise ValueError('Duplicate observation key')
        pairs.sort(key=lambda pair: pair[0])
        canonical = json.dumps(pairs, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))
    except ValueError as exc:
        raise Problem(422, 'invalid_dataset', str(exc)) from None
    return sha256(canonical.encode()).hexdigest(), pairs
