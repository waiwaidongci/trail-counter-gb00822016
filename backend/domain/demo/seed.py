from datetime import datetime, timedelta, timezone

from ..intake.records import format_window
from ..intake.schemas import WINDOW_MINUTES

SEED_NAME = "青岚山步道双计数器_20261121.csv"


def seed() -> list[dict]:
    start = datetime(2026, 11, 21, 0, 0, tzinfo=timezone.utc)
    north = ((12, 12), (18, 18), (24, 24), (30, 30), (36, 36), (42, 42), (48, 48), (54, 420))
    creek = tuple((count, 2 * count + 4) for count in (7, 10, 13, 16, 19, 22, 25, 28))
    return [
        {
            "entrance_id": entrance,
            "window_start": format_window(start + timedelta(minutes=WINDOW_MINUTES * index)),
            "counter": counter,
            "count": count,
        }
        for entrance, pairs in (("QL-NORTH", north), ("QL-CREEK", creek))
        for index, counts in enumerate(pairs)
        for counter, count in zip(("A", "B"), counts)
    ]
