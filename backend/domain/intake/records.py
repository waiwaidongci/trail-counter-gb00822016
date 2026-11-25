from collections.abc import Iterable, Mapping
from datetime import datetime

from .schemas import CounterReading

ReadingInput = CounterReading | Mapping[str, object]


def format_window(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def record_key(row: ReadingInput) -> str:
    reading = CounterReading.model_validate(row)
    return f"{reading.entrance_id}|{format_window(reading.window_start)}|{reading.counter}"


def validated_readings(rows: Iterable[ReadingInput]) -> list[CounterReading]:
    if not isinstance(rows, Iterable) or isinstance(rows, (Mapping, str, bytes)):
        raise ValueError("读数须以记录序列提供")
    readings = []
    seen = set()
    for line, row in enumerate(rows, start=1):
        try:
            reading = CounterReading.model_validate(row)
        except ValueError as error:
            raise ValueError(f"第 {line} 条记录无效：{error}") from error
        key = record_key(reading)
        if key in seen:
            raise ValueError(f"第 {line} 条记录重复：{key}")
        seen.add(key)
        readings.append(reading)
    if not readings:
        raise ValueError("至少需要一条计数器读数")
    return readings


def validate_rows(rows: Iterable[ReadingInput]) -> None:
    validated_readings(rows)
