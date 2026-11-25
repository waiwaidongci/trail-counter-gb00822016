import csv
from io import StringIO

from app.errors import Problem
from app.settings import settings
from domain.spec import ROW_MODEL


def parse_csv(body: bytes) -> list[dict]:
    try:
        reader = csv.DictReader(StringIO(body.decode('utf-8-sig'), newline=''), strict=True)
        fields = reader.fieldnames or []
        known = ROW_MODEL.model_fields
        required = {name for name, field in known.items() if field.is_required()}
        if (not required.issubset(fields) or not set(fields).issubset(known)
                or len(fields) != len(set(fields))):
            raise ValueError(f'CSV columns must use schema names. Required: {sorted(required)}')
        result = []
        for index, row in enumerate(reader, 1):
            if None in row or None in row.values():
                raise ValueError(f'CSV row {index} has a different number of columns')
            if index > settings.max_rows:
                raise ValueError(f'At most {settings.max_rows} rows are accepted')
            result.append({key: value for key, value in row.items()
                           if value != '' or known[key].is_required()})
        return result
    except (UnicodeError, csv.Error, ValueError) as exc:
        raise Problem(422, 'invalid_csv', str(exc)) from None
