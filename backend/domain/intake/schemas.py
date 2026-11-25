from datetime import datetime, timezone
import re
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

WINDOW_MINUTES = 15


class CounterReading(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)

    entrance_id: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{0,31}$")
    window_start: AwareDatetime
    counter: Literal["A", "B"]
    count: int = Field(ge=0, le=1_000_000)

    @field_validator("entrance_id", "counter", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("window_start", mode="before")
    @classmethod
    def require_timestamp(cls, value: object) -> object:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:Z|[+-][0-9]{2}:[0-9]{2})",
            value,
        ):
            return value
        raise ValueError("时间窗起点须用带时区的 ISO 8601 日期时间，精确到秒")

    @field_validator("window_start")
    @classmethod
    def normalize_window(cls, value: datetime) -> datetime:
        try:
            utc = value.astimezone(timezone.utc)
        except OverflowError as error:
            raise ValueError("换算后的 UTC 时间超出支持范围") from error
        if utc.minute % WINDOW_MINUTES or utc.second or utc.microsecond:
            raise ValueError("时间窗起点须对齐 UTC 15 分钟边界")
        return utc

    @field_validator("count", mode="before")
    @classmethod
    def require_integer_count(cls, value: object) -> object:
        if type(value) is int or (isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip())):
            return value.strip() if isinstance(value, str) else value
        raise ValueError("计数须为非负整数或只含十进制数字的 CSV 单元格")


class ReviewOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)

    min_pairs: int = Field(default=5, ge=3)
    correlation_gap_threshold: float = Field(default=0.20, gt=0, le=2)
    pearson_influence_threshold: float = Field(default=0.20, gt=0, le=2)

    @field_validator("*", mode="before")
    @classmethod
    def reject_boolean(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("复核参数须使用数值")
        return value
