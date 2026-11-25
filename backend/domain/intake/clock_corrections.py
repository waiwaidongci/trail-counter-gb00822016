from domain.intake.corrections import (  # noqa: F401
    CorrectionCollision,
    CorrectionPlan,
    plan_clock_correction,
    plan_correction,
)

apply_clock_correction = plan_correction

__all__ = [
    'CorrectionCollision', 'CorrectionPlan', 'plan_correction',
    'plan_clock_correction', 'apply_clock_correction',
]
