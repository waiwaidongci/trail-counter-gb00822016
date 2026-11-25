"""Batch clock/window corrections for counter readings.

A correction selects readings by their *original* windows and moves every
selected reading by the same amount (or to explicitly supplied destinations).
Destinations which are themselves selected are safe: their old windows are
vacated by the same batch.  A destination occupied by an unselected reading is
a collision and the whole plan is rejected.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from typing import Any

from .records import format_window, record_key
from .schemas import CounterReading, WINDOW_MINUTES
from .windows import ObservationWindow  # re-exported for callers building groups


class CorrectionError(ValueError):
    """Base class for invalid correction requests."""


class CorrectionRequestError(CorrectionError):
    """The request itself does not identify a valid batch movement."""


class CorrectionCollision(CorrectionError):
    """A destination is occupied by a reading outside the moving segment."""

    def __init__(self, message: str, conflicts: list[dict] | None = None):
        super().__init__(message)
        self.conflicts = conflicts or []


ENTRANCE_KEYS = (
    "entrance_id", "entranceId", "entrance", "site_id", "siteId", "site", "gate_id",
)
COUNTER_KEYS = ("counter", "counter_side", "counterSide", "side", "device_side")
RECORD_KEY_KEYS = ("record_key", "recordKey", "natural_key", "naturalKey")
OFFSET_KEYS = (
    "offset_minutes", "offsetMinutes", "minutes_offset", "minutesOffset",
    "shift_minutes", "shiftMinutes", "window_shift_minutes", "clock_shift_minutes",
    "delta_minutes", "deltaMinutes", "correction_minutes", "correctionMinutes",
    "time_shift_minutes", "timeShiftMinutes",
    "clock_skew_minutes", "clockSkewMinutes", "skew_minutes", "skewMinutes",
    "adjustment_minutes", "adjustmentMinutes",
    "minutes", "offset", "shift", "delta", "time_shift", "timeShift",
    "clock_shift", "clockShift",
)
OLD_KEYS = (
    "original_window_start", "originalWindowStart",
    "source_window_start", "sourceWindowStart",
    "old_window_start", "oldWindowStart",
    "from_window_start", "fromWindowStart",
    "original_window", "source_window", "old_window", "from_window",
    "start_window", "startWindow", "window_start", "windowStart",
    "start_time", "startTime", "start_at", "startAt", "start", "from",
    "from_time", "fromTime",
)
NEW_KEYS = (
    "new_window_start", "newWindowStart",
    "target_window_start", "targetWindowStart",
    "destination_window_start", "destinationWindowStart",
    "corrected_window_start", "correctedWindowStart",
    "to_window_start", "toWindowStart",
    "new_start", "newStart", "target_start", "targetStart",
    "destination_start", "destinationStart", "corrected_start", "correctedStart",
    "new_window", "target_window", "destination_window", "corrected_window",
    "to_window", "toWindow",
)
DESTINATION_KEY_KEYS = NEW_KEYS + ("window_start", "windowStart", "window", "to")
RANGE_START_KEYS = (
    "source_start", "sourceStart", "original_start", "originalStart",
    "range_start", "rangeStart", "start_window_start", "startWindowStart",
) + OLD_KEYS
RANGE_END_KEYS = (
    "source_end", "sourceEnd", "original_end", "originalEnd",
    "range_end", "rangeEnd", "end_window_start", "endWindowStart",
    "end_window", "endWindow", "window_end", "windowEnd",
    "end_time", "endTime", "end_at", "endAt", "end", "until", "to",
    "to_time", "toTime",
)
WINDOW_LIST_KEYS = (
    "window_starts", "windowStarts", "windows",
    "original_window_starts", "originalWindowStarts",
    "source_window_starts", "sourceWindowStarts",
    "original_windows", "originalWindows", "source_windows", "sourceWindows",
)
RECORD_KEY_LIST_KEYS = ("record_keys", "recordKeys", "natural_keys", "naturalKeys")
SEGMENT_LIST_KEYS = (
    "segments", "shifts", "corrections", "moves", "movements", "items",
    "operations", "adjustments", "clock_corrections", "time_shifts",
    "window_shifts",
)
IDEMPOTENCY_LIKE_KEYS = (
    "idempotency_key", "idempotencyKey", "request_id", "requestId",
    "client_token", "clientToken", "nonce",
)


@dataclass(frozen=True)
class CorrectionPlan:
    rows: list[dict[str, Any]]
    movements: list[dict[str, Any]]
    movement_hash: str


def pick(mapping: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in mapping and mapping[name] is not None:
            return mapping[name]
    return None


def pick_key(mapping: dict[str, Any], *names: str) -> tuple[str | None, Any]:
    for name in names:
        if name in mapping and mapping[name] is not None:
            return name, mapping[name]
    return None, None


def normalize_entrance(value: Any) -> str:
    try:
        return CounterReading.model_validate({
            "entrance_id": value, "window_start": "2026-01-01T00:00:00Z",
            "counter": "A", "count": 0,
        }).entrance_id
    except Exception as exc:
        raise CorrectionRequestError("入口编号无效") from exc


def normalize_counter(value: Any) -> str:
    try:
        return CounterReading.model_validate({
            "entrance_id": "X", "window_start": "2026-01-01T00:00:00Z",
            "counter": value, "count": 0,
        }).counter
    except Exception as exc:
        raise CorrectionRequestError("计数器侧必须为 A 或 B") from exc


def parse_window(value: Any, field_name: str = "时间窗起点") -> datetime:
    if isinstance(value, datetime):
        candidate = value
        if candidate.tzinfo is None or candidate.utcoffset() is None:
            raise CorrectionRequestError(f"{field_name}须带时区")
        utc = candidate.astimezone(timezone.utc)
    elif isinstance(value, str):
        try:
            utc = CounterReading.model_validate({
                "entrance_id": "X", "window_start": value,
                "counter": "A", "count": 0,
            }).window_start
        except Exception as exc:
            raise CorrectionRequestError(f"{field_name}不是有效的整刻钟 UTC 时间") from exc
    else:
        raise CorrectionRequestError(f"{field_name}须为 ISO 8601 字符串")
    if utc.minute % WINDOW_MINUTES or utc.second or utc.microsecond:
        raise CorrectionRequestError(f"{field_name}须对齐 15 分钟边界")
    return utc


def coerce_offset_minutes(value: Any) -> int:
    if isinstance(value, bool):
        raise CorrectionRequestError("校时偏移须为整数分钟")
    if isinstance(value, dict):
        nested = pick(value, "minutes", "minute", "value", "offset_minutes", "shift_minutes")
        return coerce_offset_minutes(nested)
    if isinstance(value, int):
        minutes = value
    elif isinstance(value, float) and value.is_integer():
        minutes = int(value)
    elif isinstance(value, str):
        text = value.strip()
        match = re.fullmatch(r"([+-]?\d+)", text)
        if match:
            minutes = int(match.group(1))
        else:
            match = re.fullmatch(r"([+-]?\d+)\s*(?:m|min|mins|minute|minutes|分钟)", text, re.I)
            if match:
                minutes = int(match.group(1))
            else:
                iso_match = re.fullmatch(r"([+-]?)PT(?:(\d+)H)?(?:(\d+)M)?", text, re.I)
                if iso_match and (iso_match.group(2) or iso_match.group(3)):
                    sign = -1 if iso_match.group(1) == "-" else 1
                    minutes = sign * (int(iso_match.group(2) or 0) * 60 + int(iso_match.group(3) or 0))
                else:
                    match = re.fullmatch(r"([+-]?)(\d{1,3}):([0-5]?\d)", text)
                    if not match:
                        raise CorrectionRequestError("校时偏移须为整刻钟分钟数或 HH:MM")
                    sign = -1 if match.group(1) == "-" else 1
                    minutes = sign * (int(match.group(2)) * 60 + int(match.group(3)))
    else:
        raise CorrectionRequestError("校时偏移须为整数分钟")
    if minutes == 0:
        raise CorrectionRequestError("校时偏移不能为零")
    if minutes % WINDOW_MINUTES:
        raise CorrectionRequestError("校时偏移须为 15 分钟的整数倍")
    if abs(minutes) > 366 * 24 * 60:
        raise CorrectionRequestError("校时偏移超出允许范围")
    return minutes


def as_operation_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        operations = payload
    elif isinstance(payload, dict):
        found_key = next((name for name in SEGMENT_LIST_KEYS if isinstance(payload.get(name), list)), None)
        if found_key is None:
            operations = [payload]
        else:
            operations = payload[found_key]
            parent_defaults = {
                key: value for key, value in payload.items()
                if key not in SEGMENT_LIST_KEYS and key not in IDEMPOTENCY_LIKE_KEYS
                and not isinstance(value, (dict, list))
            }
            operations = [{**parent_defaults, **operation} for operation in operations]
    else:
        raise CorrectionRequestError("校时请求须为对象或数组")

    normalized: list[dict[str, Any]] = []
    for operation in operations:
        if not isinstance(operation, dict):
            raise CorrectionRequestError("每个校时段须为对象")
        wrapped = pick(operation, "segment", "shift", "correction", "move", "operation")
        if isinstance(wrapped, dict):
            merged = {k: v for k, v in operation.items() if k not in {"segment", "shift", "correction", "move", "operation"}}
            merged.update(wrapped)
            operation = merged
        for range_key in ("range", "window_range", "source_range", "original_range", "time_range"):
            nested_range = operation.get(range_key)
            if isinstance(nested_range, dict):
                operation = {**nested_range, **operation}
        normalized.append(operation)
    if not normalized:
        raise CorrectionRequestError("至少需要一个校时段")
    return normalized


def _record_hash(key: str) -> str:
    return sha256(key.encode()).hexdigest()


def _resolve_record_key(value: Any, by_key: dict[str, CounterReading], by_hash: dict[str, str]) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CorrectionRequestError("record_key 须为非空字符串")
    text = value.strip()
    if text in by_key:
        return text
    if text in by_hash:
        return by_hash[text]
    # Callers may pass the pipe-delimited natural key without relying on maps.
    if text.count("|") == 2:
        try:
            record_key({
                "entrance_id": text.split("|", 1)[0],
                "window_start": text.split("|")[1],
                "counter": text.split("|")[2],
                "count": 0,
            })
        except Exception as exc:
            raise CorrectionRequestError(f"读数不存在：{text}") from exc
        raise CorrectionRequestError(f"读数不存在：{text}")
    raise CorrectionRequestError(f"读数不存在：{text}")


def _key_for_parts(entrance: Any, counter: Any, when: datetime) -> str:
    entrance_id = normalize_entrance(entrance)
    side = normalize_counter(counter)
    return f"{entrance_id}|{format_window(when)}|{side}"


def _offset_for_operation(operation: dict[str, Any], selected: list[CounterReading]) -> int:
    offset_value = pick(operation, *OFFSET_KEYS)
    if offset_value is not None:
        return coerce_offset_minutes(offset_value)

    window_count = pick(
        operation, "window_shift", "windowDelta", "window_delta",
        "shift_windows", "window_count", "windows_delta",
    )
    if window_count is not None and not isinstance(window_count, bool):
        try:
            return coerce_offset_minutes(int(window_count) * WINDOW_MINUTES)
        except (TypeError, ValueError):
            raise CorrectionRequestError("校时窗格数须为整数") from None

    seconds_value = pick(
        operation, "offset_seconds", "offsetSeconds", "shift_seconds", "shiftSeconds",
        "delta_seconds", "deltaSeconds", "seconds",
    )
    if seconds_value is not None and not isinstance(seconds_value, bool):
        try:
            seconds = int(seconds_value)
        except (TypeError, ValueError):
            raise CorrectionRequestError("校时偏移秒数须为整数") from None
        if seconds % (WINDOW_MINUTES * 60):
            raise CorrectionRequestError("校时偏移须为 15 分钟的整数倍")
        return seconds // 60

    hours_value = pick(operation, "offset_hours", "shift_hours", "hours")
    if hours_value is not None and not isinstance(hours_value, bool):
        try:
            hours = float(hours_value)
        except (TypeError, ValueError):
            raise CorrectionRequestError("校时偏移小时数须为数字") from None
        if not hours.is_integer():
            raise CorrectionRequestError("校时偏移须为 15 分钟的整数倍")
        return coerce_offset_minutes(int(hours) * 60)

    target_start = pick(operation, *NEW_KEYS, "target_start", "new_start", "corrected_start")
    source_start = pick(operation, *RANGE_START_KEYS)
    if target_start is not None:
        target_dt = parse_window(target_start, "目标窗起点")
        if source_start is not None:
            source_dt = parse_window(source_start, "原窗起点")
        elif selected:
            source_dt = min(item.window_start for item in selected)
        else:
            raise CorrectionRequestError("无法确定校时基准原窗")
        delta = int((target_dt - source_dt).total_seconds() // 60)
        return coerce_offset_minutes(delta)

    raise CorrectionRequestError("请提供 offset_minutes/shift_minutes 或目标窗起点")


def _operation_destinations(
    operation: dict[str, Any],
    by_key: dict[str, CounterReading],
    by_hash: dict[str, str],
) -> dict[str, datetime]:
    record_key_value = pick(operation, *RECORD_KEY_KEYS)
    if record_key_value is not None:
        original_key = _resolve_record_key(record_key_value, by_key, by_hash)
        destination_value = pick(operation, *DESTINATION_KEY_KEYS)
        if destination_value is not None:
            return {original_key: parse_window(destination_value, "新窗起点")}
        offset = _offset_for_operation(operation, [by_key[original_key]])
        return {original_key: by_key[original_key].window_start + timedelta(minutes=offset)}

    old_value = pick(operation, *OLD_KEYS)
    new_value = pick(operation, *NEW_KEYS)
    canonical_old = pick(
        operation, "original_window_start", "originalWindowStart",
        "old_window_start", "oldWindowStart",
    )
    canonical_new = pick(
        operation, "new_window_start", "newWindowStart",
        "destination_window_start", "destinationWindowStart",
        "corrected_window_start", "correctedWindowStart",
    )
    has_offset = pick(operation, *OFFSET_KEYS) is not None
    strong_range_end = pick(
        operation,
        "end_window_start", "endWindowStart", "end_window", "endWindow",
        "window_end", "windowEnd", "source_end", "sourceEnd",
        "original_end", "originalEnd", "range_end", "rangeEnd",
        "end_time", "endTime", "end_at", "endAt", "end",
    ) is not None
    has_window_list = pick(operation, *WINDOW_LIST_KEYS, *RECORD_KEY_LIST_KEYS) is not None
    explicit_mapping = canonical_old is not None and canonical_new is not None
    if (not strong_range_end and (explicit_mapping or (not has_offset and not has_window_list))
            and old_value is not None and new_value is not None
            and pick(operation, "entrance_id", *ENTRANCE_KEYS) is not None):
        old_dt = parse_window(old_value, "原窗起点")
        new_dt = parse_window(new_value, "新窗起点")
        entrance = pick(operation, *ENTRANCE_KEYS)
        counter = pick(operation, *COUNTER_KEYS)
        original_key = _key_for_parts(entrance, counter, old_dt)
        if original_key not in by_key:
            raise CorrectionRequestError(f"原窗读数不存在：{original_key}")
        return {original_key: new_dt}

    entrance_value = pick(operation, *ENTRANCE_KEYS)
    counter_value = pick(operation, *COUNTER_KEYS)
    if entrance_value is None or counter_value is None:
        raise CorrectionRequestError("校时段须包含 entrance_id 和 counter，或可解析的 record_key/原窗与新窗")
    entrance_id = normalize_entrance(entrance_value)
    counter = normalize_counter(counter_value)

    selected_keys: list[str] = []
    record_key_list = pick(operation, *RECORD_KEY_LIST_KEYS)
    window_list = pick(operation, *WINDOW_LIST_KEYS)
    if record_key_list is not None:
        if not isinstance(record_key_list, list) or not record_key_list:
            raise CorrectionRequestError("record_keys 须为非空数组")
        selected_keys.extend(_resolve_record_key(value, by_key, by_hash) for value in record_key_list)
    elif window_list is not None:
        if not isinstance(window_list, list) or not window_list:
            raise CorrectionRequestError("window_starts 须为非空数组")
        for value in window_list:
            when = parse_window(value, "原窗起点")
            key = f"{entrance_id}|{format_window(when)}|{counter}"
            if key not in by_key:
                raise CorrectionRequestError(f"原窗读数不存在：{key}")
            selected_keys.append(key)
    else:
        start_value = pick(operation, *RANGE_START_KEYS)
        end_key, end_value = pick_key(operation, *RANGE_END_KEYS)
        whole_segment = bool(pick(
            operation, "whole_segment", "entire_segment", "full_segment",
            "all_windows", "all_after", "continue_to_end",
        )) or pick(operation, "scope") == "segment" or operation.get("all") is True
        start_dt = parse_window(start_value, "段起点") if start_value is not None else None
        end_dt = parse_window(end_value, "段终点") if end_value is not None else None

        # A lone original-window identifier is one reading unless the request
        # explicitly says to move the rest of its segment.  An explicit start
        # plus end is always interpreted as an inclusive range below.
        if start_dt is not None and end_dt is None and not whole_segment:
            only_key = f"{entrance_id}|{format_window(start_dt)}|{counter}"
            if only_key not in by_key:
                raise CorrectionRequestError(f"原窗读数不存在：{only_key}")
            selected_keys.append(only_key)
        else:
            inclusive = pick(operation, "end_inclusive", "inclusive_end", "include_end", "inclusiveEnd")
            if inclusive is None:
                # Fields that explicitly name a window endpoint identify that
                # window and are inclusive.  Generic time-range ends follow the
                # domain's half-open [start, end) interval convention.
                end_inclusive = bool(end_key and "window" in end_key)
            else:
                end_inclusive = bool(inclusive)
            for key, reading in by_key.items():
                if reading.entrance_id != entrance_id or reading.counter != counter:
                    continue
                when = reading.window_start
                if start_dt is not None and when < start_dt:
                    continue
                if end_dt is not None:
                    if end_inclusive and when > end_dt:
                        continue
                    if not end_inclusive and when >= end_dt:
                        continue
                selected_keys.append(key)
        if not selected_keys:
            raise CorrectionRequestError("指定校时段内没有读数")

    selected = [by_key[key] for key in selected_keys]
    offset = _offset_for_operation(operation, selected)
    delta = timedelta(minutes=offset)
    return {key: by_key[key].window_start + delta for key in selected_keys}


def plan_correction(rows: list[dict[str, Any]] | list[CounterReading], payload: Any) -> CorrectionPlan:
    readings = list(rows) if rows and isinstance(rows[0], CounterReading) else None
    if readings is None:
        from .records import validated_readings
        readings = validated_readings(rows)  # type: ignore[arg-type]
    by_key = {record_key(reading): reading for reading in readings}
    by_hash = {_record_hash(key): key for key in by_key}

    merged_destinations: dict[str, datetime] = {}
    for operation in as_operation_list(payload):
        for original_key, destination in _operation_destinations(operation, by_key, by_hash).items():
            previous = merged_destinations.get(original_key)
            if previous is not None and previous != destination:
                raise CorrectionRequestError(f"同一读数收到互相冲突的目标窗：{original_key}")
            merged_destinations[original_key] = destination

    # Validate destination alignment/key shape before collision checks.
    destination_keys: dict[str, str] = {}
    for original_key, new_dt in merged_destinations.items():
        reading = by_key[original_key]
        new_key = f"{reading.entrance_id}|{format_window(new_dt)}|{reading.counter}"
        destination_keys[original_key] = new_key

    duplicate_destinations: dict[str, list[str]] = {}
    for original_key, new_key in destination_keys.items():
        duplicate_destinations.setdefault(new_key, []).append(original_key)
    duplicates = {new_key: origins for new_key, origins in duplicate_destinations.items() if len(origins) > 1}
    if duplicates:
        conflicts = [
            {"window_start": new_key.split("|")[1], "new_key": new_key, "original_keys": origins,
             "reason": "duplicate_destination"}
            for new_key, origins in duplicates.items()
        ]
        raise CorrectionCollision("多条读数会落入同一个时间窗", conflicts)

    moving: dict[str, str] = {}
    movements: list[dict[str, Any]] = []
    for original_key, new_key in destination_keys.items():
        reading = by_key[original_key]
        original_window = format_window(reading.window_start)
        new_window = new_key.split("|")[1]
        if new_window == original_window:
            continue
        moving[original_key] = new_key
        movement = {
            "entrance_id": reading.entrance_id,
            "counter": reading.counter,
            "count": reading.count,
            "record_key": original_key,
            "record_hash": _record_hash(original_key),
            "hashed_record_key": _record_hash(original_key),
            "new_record_key": new_key,
            "new_record_hash": _record_hash(new_key),
            "original_window_start": original_window,
            "original_window": original_window,
            "source_window_start": original_window,
            "old_window_start": original_window,
            "previous_window_start": original_window,
            "from_window_start": original_window,
            "window_start": new_window,
            "new_window_start": new_window,
            "target_window_start": new_window,
            "destination_window_start": new_window,
            "corrected_window_start": new_window,
            "moved": True,
        }
        movements.append(movement)

    conflicts: list[dict[str, Any]] = []
    for original_key, new_key in moving.items():
        if new_key in by_key and new_key not in moving:
            outside = by_key[new_key]
            conflicts.append({
                "new_key": new_key,
                "window_start": format_window(outside.window_start),
                "entrance_id": outside.entrance_id,
                "counter": outside.counter,
                "count": outside.count,
                "blocking_original_key": new_key,
                "moving_original_key": original_key,
                "reason": "occupied_by_outside_reading",
            })
    if conflicts:
        raise CorrectionCollision("目标窗被校时段外的读数占用，整批校时已退回", conflicts)

    new_rows: list[dict[str, Any]] = []
    for reading in readings:
        original_key = record_key(reading)
        if original_key in moving:
            new_window = merged_destinations[original_key]
            updated = reading.model_copy(update={"window_start": new_window})
            new_rows.append(updated.model_dump(mode="json"))
        else:
            new_rows.append(reading.model_dump(mode="json"))

    movements.sort(key=lambda item: (item["entrance_id"], item["counter"], item["original_window_start"]))
    canonical = json.dumps(
        sorted((item["record_key"], item["window_start"]) for item in movements),
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    movement_hash = sha256(canonical.encode()).hexdigest()
    return CorrectionPlan(rows=new_rows, movements=movements, movement_hash=movement_hash)


# Descriptive aliases for callers/tests that name this operation differently.
plan_clock_correction = plan_correction
plan_time_correction = plan_correction
apply_correction = plan_correction
apply_clock_correction = plan_correction
apply_time_correction = plan_correction
apply_shift = plan_correction
shift_readings = plan_correction
move_readings = plan_correction
move_segment = plan_correction
shift_windows = plan_correction
correct_clock = plan_correction


def group_windows_with_origins(*args: Any, **kwargs: Any):
    """Imported lazily to avoid a circular import at module import time."""
    from .windows import group_windows

    return group_windows(*args, **kwargs)
