from dataclasses import dataclass
from math import sqrt


@dataclass(frozen=True)
class PearsonMoments:
    size: int
    sum_a: int
    sum_b: int
    squares_a: int
    squares_b: int
    products: int

    @classmethod
    def from_pairs(cls, pairs: list[tuple[int, int]]) -> "PearsonMoments":
        return cls(
            len(pairs),
            sum(a for a, _ in pairs),
            sum(b for _, b in pairs),
            sum(a * a for a, _ in pairs),
            sum(b * b for _, b in pairs),
            sum(a * b for a, b in pairs),
        )

    def without(self, a: int, b: int) -> "PearsonMoments":
        return PearsonMoments(
            self.size - 1, self.sum_a - a, self.sum_b - b,
            self.squares_a - a * a, self.squares_b - b * b, self.products - a * b,
        )

    def coefficient(self) -> float | None:
        if self.size < 2:
            return None
        # Integer moments preserve the variance of nearly constant large counts.
        variance_a = self.size * self.squares_a - self.sum_a**2
        variance_b = self.size * self.squares_b - self.sum_b**2
        if variance_a == 0 or variance_b == 0:
            return None
        numerator = self.size * self.products - self.sum_a * self.sum_b
        coefficient = numerator / sqrt(variance_a * variance_b)
        return max(-1.0, min(1.0, coefficient))
