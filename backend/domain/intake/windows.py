from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from .schemas import CounterReading


@dataclass(frozen=True)
class ObservationWindow:
    start: datetime
    count_a: int | None
    count_b: int | None

    def counts(self) -> tuple[int, int] | None:
        if self.count_a is None or self.count_b is None:
            return None
        return self.count_a, self.count_b


def group_windows(readings: list[CounterReading]) -> dict[str, list[ObservationWindow]]:
    counts_by_window = defaultdict(dict)
    for reading in readings:
        counts_by_window[reading.entrance_id, reading.window_start][reading.counter] = reading.count

    entrances = defaultdict(list)
    for (entrance, start), counts in sorted(counts_by_window.items()):
        entrances[entrance].append(ObservationWindow(start, counts.get("A"), counts.get("B")))
    return dict(entrances)
