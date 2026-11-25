from ..correlation.biweight import BiweightResult
from ..correlation.pearson import PearsonMoments
from ..intake.records import format_window
from ..intake.schemas import ReviewOptions
from ..intake.windows import ObservationWindow


def diagnose_windows(
    entrance: str,
    windows: list[ObservationWindow],
    robust: BiweightResult,
    moments: PearsonMoments,
    pearson: float | None,
    options: ReviewOptions,
) -> list[dict]:
    diagnostics = []
    paired_index = 0
    for window in windows:
        counts = window.counts()
        weight_a = weight_b = deleted_pearson = change = None
        flags = []
        if counts is None:
            flags.append("missing_counter")
        else:
            if robust.weights_a is not None:
                weight_a = robust.weights_a[paired_index]
                if weight_a == 0:
                    flags.append("zero_biweight_a")
            if robust.weights_b is not None:
                weight_b = robust.weights_b[paired_index]
                if weight_b == 0:
                    flags.append("zero_biweight_b")
            if pearson is not None:
                deleted_pearson = moments.without(*counts).coefficient()
                if deleted_pearson is None:
                    flags.append("pearson_deletion_undefined")
                else:
                    change = abs(pearson - deleted_pearson)
                    if change >= options.pearson_influence_threshold:
                        flags.append("pearson_influence")
            paired_index += 1
        diagnostics.append({
            "entrance_id": entrance,
            "window_start": format_window(window.start),
            "count_a": window.count_a,
            "count_b": window.count_b,
            "missing_counter": (
                ("A" if window.count_a is None else "B") if counts is None else None
            ),
            "weight_a": weight_a,
            "weight_b": weight_b,
            "pearson_without_window": deleted_pearson,
            "pearson_change": change,
            "flags": flags,
        })
    return diagnostics
