from ..correlation.biweight import biweight_midcorrelation
from ..correlation.pearson import PearsonMoments
from ..intake.schemas import ReviewOptions
from ..intake.windows import ObservationWindow
from .diagnostics import diagnose_windows

ISSUE_MESSAGES = {
    "insufficient_pairs": "完整样本窗不足",
    "missing_windows": "时间窗缺少一侧读数",
    "zero_mad_a": "A 侧绝对中位差为零",
    "zero_mad_b": "B 侧绝对中位差为零",
    "zero_mad_both": "两侧绝对中位差均为零",
    "insufficient_shared_support": "双侧权重同时为正的样本窗不足",
    "zero_weighted_norm": "稳健加权后序列的范数为零",
    "undefined_pearson": "至少一侧计数恒定，Pearson 无定义",
    "correlation_gap": "稳健相关与 Pearson 的差值达到复核门槛",
    "flagged_windows": "存在需要回查的完整时间窗",
}


def _review_entrance(
    entrance: str, windows: list[ObservationWindow], options: ReviewOptions,
) -> tuple[dict, list[dict]]:
    pairs = [counts for window in windows if (counts := window.counts()) is not None]
    paired = len(pairs)
    missing = len(windows) - paired
    robust = biweight_midcorrelation([a for a, _ in pairs], [b for _, b in pairs], options.min_pairs)
    moments = PearsonMoments.from_pairs(pairs)
    pearson = moments.coefficient() if paired >= options.min_pairs else None
    gap = abs(robust.coefficient - pearson) if robust.coefficient is not None and pearson is not None else None
    diagnostics = diagnose_windows(entrance, windows, robust, moments, pearson, options)
    flagged = sum(row["missing_counter"] is None and bool(row["flags"]) for row in diagnostics)

    blocking = []
    if missing:
        blocking.append("missing_windows")
    if robust.issue:
        blocking.append(robust.issue)
    if pearson is None and paired >= options.min_pairs:
        blocking.append("undefined_pearson")

    reasons = blocking.copy()
    if gap is not None and gap >= options.correlation_gap_threshold:
        reasons.append("correlation_gap")
    if flagged:
        reasons.append("flagged_windows")

    status = "blocked" if blocking else "review" if reasons else "ready"
    return {
        "entrance_id": entrance,
        "paired_windows": paired,
        "unpaired_windows": missing,
        "shared_support": robust.shared_support,
        "biweight_midcorrelation": robust.coefficient,
        "pearson": pearson,
        "correlation_gap": gap,
        "flagged_windows": flagged,
        "status": status,
        "reasons": reasons,
    }, diagnostics


def build_report(groups: dict[str, list[ObservationWindow]], options: ReviewOptions) -> dict:
    entrances, windows, warnings = [], [], []
    for entrance, observations in groups.items():
        review, diagnostics = _review_entrance(entrance, observations, options)
        entrances.append(review)
        windows.extend(diagnostics)
        warnings.extend(f"{entrance}：{ISSUE_MESSAGES[reason]}" for reason in review["reasons"])

    blocked = sum(row["status"] == "blocked" for row in entrances)
    return {
        "summary": {
            "entrance_count": len(entrances),
            "paired_windows": sum(row["paired_windows"] for row in entrances),
            "unpaired_windows": sum(row["unpaired_windows"] for row in entrances),
            "flagged_windows": sum(row["flagged_windows"] for row in entrances),
            "review_entrances": sum(row["status"] == "review" for row in entrances),
            "blocked_entrances": blocked,
        },
        "tables": {"entrances": entrances, "windows": windows},
        "warnings": warnings,
        "publishable": blocked == 0,
    }
