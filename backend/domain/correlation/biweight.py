from dataclasses import dataclass
from math import fsum, sqrt
from statistics import median


@dataclass(frozen=True)
class BiweightResult:
    coefficient: float | None
    weights_a: tuple[float, ...] | None
    weights_b: tuple[float, ...] | None
    shared_support: int | None
    issue: str | None = None


def _weights(values: list[int]) -> tuple[tuple[float, ...] | None, tuple[float, ...]]:
    center = median(values)
    offsets = tuple(value - center for value in values)
    mad = median(abs(offset) for offset in offsets)
    if mad == 0:
        return None, offsets
    scaled = (offset / (9 * mad) for offset in offsets)
    weights = tuple((1 - ratio**2)**2 if abs(ratio) < 1 else 0.0 for ratio in scaled)
    return weights, offsets


def biweight_midcorrelation(
    values_a: list[int], values_b: list[int], min_pairs: int,
) -> BiweightResult:
    if len(values_a) < min_pairs:
        return BiweightResult(None, None, None, None, "insufficient_pairs")
    weights_a, offsets_a = _weights(values_a)
    weights_b, offsets_b = _weights(values_b)
    if weights_a is None and weights_b is None:
        return BiweightResult(None, None, None, None, "zero_mad_both")
    if weights_a is None or weights_b is None:
        issue = "zero_mad_a" if weights_a is None else "zero_mad_b"
        return BiweightResult(None, weights_a, weights_b, None, issue)

    support = sum(a > 0 and b > 0 for a, b in zip(weights_a, weights_b))
    if support < min_pairs:
        return BiweightResult(None, weights_a, weights_b, support, "insufficient_shared_support")
    weighted_a = [offset * weight for offset, weight in zip(offsets_a, weights_a)]
    weighted_b = [offset * weight for offset, weight in zip(offsets_b, weights_b)]
    norm = sqrt(fsum(a * a for a in weighted_a) * fsum(b * b for b in weighted_b))
    if norm == 0:
        return BiweightResult(None, weights_a, weights_b, support, "zero_weighted_norm")
    coefficient = fsum(a * b for a, b in zip(weighted_a, weighted_b)) / norm
    return BiweightResult(max(-1.0, min(1.0, coefficient)), weights_a, weights_b, support)
