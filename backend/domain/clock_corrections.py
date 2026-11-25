from domain.intake.corrections import (  # noqa: F401
    CorrectionCollision as ClockCorrectionCollision,
)
from domain.intake.corrections import (
    plan_clock_correction,
    plan_correction,
)

apply_clock_correction = plan_correction
correct_clock = plan_correction

__all__ = [
    'plan_correction', 'plan_clock_correction', 'apply_clock_correction',
    'correct_clock', 'ClockCorrectionCollision',
]
