from app.data.corrections import (  # noqa: F401
    submit_clock_correction,
    submit_correction,
)

apply_clock_correction = submit_clock_correction

__all__ = ['submit_clock_correction', 'submit_correction', 'apply_clock_correction']
