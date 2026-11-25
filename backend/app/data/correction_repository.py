from app.data.corrections import (  # noqa: F401
    submit_clock_correction,
    submit_correction,
)

apply_correction = submit_correction
create_corrected_version = submit_correction

__all__ = ['submit_clock_correction', 'submit_correction',
           'apply_correction', 'create_corrected_version']
