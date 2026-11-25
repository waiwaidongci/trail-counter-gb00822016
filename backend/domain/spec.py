"""Public contract for the trail-counter domain."""

from collections.abc import Iterable, Mapping

from .demo.seed import SEED_NAME, seed
from .intake.records import ReadingInput, record_key, validate_rows, validated_readings
from .intake.schemas import CounterReading, ReviewOptions
from .intake.windows import group_windows
from .review.report import build_report

TITLE = "山地步道双计数器读数稳健相关"
METHOD = "biweight_midcorrelation"
ROW_MODEL = CounterReading
OPTIONS_MODEL = ReviewOptions

__all__ = [
    "TITLE", "METHOD", "SEED_NAME", "ROW_MODEL", "OPTIONS_MODEL",
    "record_key", "validate_rows", "analyze", "seed",
]


def analyze(
    rows: Iterable[ReadingInput], options: ReviewOptions | Mapping[str, object] | None = None,
) -> dict:
    configuration = OPTIONS_MODEL() if options is None else OPTIONS_MODEL.model_validate(options)
    return build_report(group_windows(validated_readings(rows)), configuration)
