from domain.intake.corrections import *  # noqa: F403
from domain.intake.corrections import (  # noqa: F401
    CorrectionCollision,
    CorrectionPlan,
    plan_correction,
    shift_windows,
)

apply_window_correction = plan_correction
correct_windows = plan_correction

__all__ = ['CorrectionCollision', 'CorrectionPlan', 'plan_correction',
           'shift_windows', 'apply_window_correction', 'correct_windows']
