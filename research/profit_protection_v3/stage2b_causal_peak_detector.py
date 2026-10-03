from __future__ import annotations

import argparse
import json
import math
import statistics
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from research.profit_protection_v3.stage2a_peak_continuation_anatomy import (
    DEFAULT_ARM_PCT,
    DEFAULT_CUTOFF_MS,
    DEFAULT_START_MS,
    FastObservation,
    PeakCandidate,
    _load_snapshot,
    record_local_peak_candidates,
)


@dataclass(frozen=True)
class DetectorConfig:
    hard_first: float | None
    hard_any: float | None
    soft_giveback: float
    recovery_max: float
    require_not_flow_aligned: bool


@dataclass(frozen=True)
class DetectorFire:
    observation_index: int
    step: int
    giveback_ratio: float
    recovery_fraction: float
    current_pnl_pct: float
    reason: str


def pct(numerator: float, denominator: float) -> float:
    return 100.0 * float(numerator) / float(denominator) if denominator else 0.0


def median(values: Iterable[float]) -> float | None:
    items = list(values)
    return statistics.median(items) if items else None


def replay_candidate(
    stream: list[FastObservation],
    candidate: PeakCandidate,
    config: DetectorConfig,
) -> DetectorFire | None:
    """
    Causal state-machine replay from a record-local peak.

    The candidate label is never read here. The detector only sees observations
    at or before the current evaluation point. A higher observed PnL than the
    candidate peak resolves the candidate as recovered and cancels the detector.
    """
    peak = float(candidate.peak_pct)
    trough = peak

    for step, index in enumerate(
        range(candidate.observation_index + 1, len(stream)),
        start=1,
    ):
        obs = stream[index]
        current = float(obs.current_pnl_pct)

        if current > peak:
            return None

        trough = min(trough, current)
        giveback = (peak - current) / peak if peak > 0.0 else 0.0
        recovery = (
            (current - trough) / (peak - trough)
            if peak > trough
            else 1.0
        )
        snapshot = obs.snapshot or {}

        if step == 1 and config.hard_first is not None:
            if giveback >= float(config.hard_first):
                return DetectorFire(
                    observation_index=index,
                    step=step,
                    giveback_ratio=giveback,
                    recovery_fraction=recovery,
                    current_pnl_pct=current,
                    reason="HARD_FIRST",
                )

        if config.hard_any is not None and giveback >= float(config.hard_any):
            return DetectorFire(
                observation_index=index,
                step=step,
                giveback_ratio=giveback,
                recovery_fraction=recovery,
                current_pnl_pct=current,
                reason="HARD_ANY",
            )

        if step >= 2 and giveback >= float(config.soft_giveback):
            recovery_failed = recovery <= float(config.recovery_max)
            flow_ok = (
                not config.require_not_flow_aligned
                or not bool(snapshot.get("flow_aligned"))
            )
            if recovery_failed and flow_ok:
                return DetectorFire(
                    observation_index=index,
                    step=step,
                    giveback_ratio=giveback,
                    recovery_fraction=recovery,
                    current_pnl_pct=current,
                    reason="RECOVERY_FAIL",
                )

    return None


def build_rule_configs() -> list[DetectorConfig]:
    configs: list[DetectorConfig] = []
    for hard_first in (None, 0.20, 0.25, 0.30):
        for hard_any in (0.25, 0.30, 0.35, None):
            for soft in (0.10, 0.15, 0.20):
                for recovery_max in (0.0, 0.25, 0.50):
                    configs.append(
                        DetectorConfig(
                            hard_first=hard_first,
                            hard_any=hard_any,
                            soft_giveback=soft,
                            recovery_max=recovery_max,
                            require_not_flow_aligned=False,
                        )
                    )

    for hard_first in (None, 0.25, 0.30):
        for hard_any in (0.30, 0.35, None):
            for recovery_max in (0.0, 0.25, 0.50):
                configs.append(
                    DetectorConfig(
                        hard_first=hard_first,
                        hard_any=hard_any,
                        soft_giveback=0.15,
                        recovery_max=recovery_max,
                        require_not_flow_aligned=True,
                    )
                )

    return configs


def _candidate_frontier_row(
    candidates: list[PeakCandidate],
    observations: dict[str, list[FastObservation]],
    config: DetectorConfig,
) -> dict[str, Any]:
    terminal_count = sum(item.label == "TERMINAL" for item in candidates)
    continued_count = sum(item.label == "CONTINUED" for item in candidates)

    terminal_fires = 0
    continued_fires = 0
    terminal_within20 = 0
    terminal_givebacks: list[float] = []
    reasons: dict[str, int] = {}

    for candidate in candidates:
        fire = replay_candidate(
            observations[candidate.position_id],
            candidate,
            config,
        )
        if fire is None:
            continue

        reasons[fire.reason] = reasons.get(fire.reason, 0) + 1
        if candidate.label == "TERMINAL":
            terminal_fires += 1
            terminal_givebacks.append(float(fire.giveback_ratio))
            if float(fire.giveback_ratio) <= 0.20:
                terminal_within20 += 1
        else:
            continued_fires += 1

    fired = terminal_fires + continued_fires
    return {
        "config": asdict(config),
        "fired": fired,
        "terminal_fires": terminal_fires,
        "continued_fires": continued_fires,
        "terminal_precision_pct": pct(terminal_fires, fired),
        "terminal_recall_pct": pct(terminal_fires, terminal_count),
        "terminal_within20_recall_pct": pct(terminal_within20, terminal_count),
        "continued_false_exit_pct": pct(continued_fires, continued_count),
        "terminal_median_giveback_pct": (
            100.0 * float(median(terminal_givebacks) or 0.0)
        ),
        "reasons": reasons,
    }


def build_stateful_frontier(
    candidates: list[PeakCandidate],
    observations: dict[str, list[FastObservation]],
) -> dict[str, Any]:
    rows = [
        _candidate_frontier_row(candidates, observations, config)
        for config in build_rule_configs()
    ]

    min_false = min(rows, key=lambda row: row["continued_false_exit_pct"])
    max_precision = max(rows, key=lambda row: row["terminal_precision_pct"])
    max_within20 = max(rows, key=lambda row: row["terminal_within20_recall_pct"])

    caps: dict[str, Any] = {}
    for cap in (10.0, 15.0, 20.0, 25.0, 30.0):
        eligible = [
            row
            for row in rows
            if float(row["continued_false_exit_pct"]) <= cap
        ]
        if not eligible:
            caps[str(int(cap))] = None
            continue
        caps[str(int(cap))] = max(
            eligible,
            key=lambda row: (
                row["terminal_within20_recall_pct"],
                row["terminal_recall_pct"],
                row["terminal_precision_pct"],
            ),
        )

    return {
        "configs_tested": len(rows),
        "min_continued_false_exit_pct": float(
            min_false["continued_false_exit_pct"]
        ),
        "minimum_false_exit_config": min_false,
        "max_precision_config": max_precision,
        "max_within20_recall_config": max_within20,
        "best_by_false_exit_cap": caps,
    }


def _first_poll_row(
    candidate: PeakCandidate,
    stream: list[FastObservation],
) -> dict[str, Any]:
    peak_obs = stream[candidate.observation_index]
    next_obs = stream[candidate.observation_index + 1]
    peak = float(candidate.peak_pct)
    current = float(next_obs.current_pnl_pct)
    giveback = (peak - current) / peak if peak > 0.0 else 0.0
    snapshot = next_obs.snapshot or {}
    elapsed_seconds = (
        int(next_obs.evaluated_at_ms) - int(peak_obs.evaluated_at_ms)
    ) / 1000.0

    return {
        "position_id": candidate.position_id,
        "label": 1 if candidate.label == "TERMINAL" else 0,
        "giveback": giveback,
        "elapsed_seconds": elapsed_seconds,
        "all_features": [
            giveback,
            peak,
            elapsed_seconds,
            float(bool(snapshot.get("flow_opposite"))),
            float(bool(snapshot.get("flow_aligned"))),
            float(bool(snapshot.get("opposite_micro_structure"))),
            float(bool(snapshot.get("positioning_opposite"))),
            float(snapshot.get("side_ret_1m_pct") or 0.0),
            float(snapshot.get("side_ret_3m_pct") or 0.0),
            float(next_obs.danger_score),
            float(len(snapshot.get("contradictions") or [])),
        ],
        "context_features": [
            peak,
            elapsed_seconds,
            float(bool(snapshot.get("flow_opposite"))),
            float(bool(snapshot.get("flow_aligned"))),
            float(bool(snapshot.get("opposite_micro_structure"))),
            float(bool(snapshot.get("positioning_opposite"))),
            float(snapshot.get("side_ret_1m_pct") or 0.0),
            float(snapshot.get("side_ret_3m_pct") or 0.0),
            float(next_obs.danger_score),
            float(len(snapshot.get("contradictions") or [])),
        ],
    }


def _sigmoid(value: float) -> float:
    clipped = max(-40.0, min(40.0, float(value)))
    return 1.0 / (1.0 + math.exp(-clipped))


def _standardize(
    train_x: list[list[float]],
    test_x: list[list[float]],
) -> tuple[list[list[float]], list[list[float]]]:
    width = len(train_x[0])
    means: list[float] = []
    stds: list[float] = []

    for column in range(width):
        values = [float(row[column]) for row in train_x]
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        std = math.sqrt(variance) or 1.0
        means.append(mean)
        stds.append(std)

    return (
        [
            [
                (float(row[column]) - means[column]) / stds[column]
                for column in range(width)
            ]
            for row in train_x
        ],
        [
            [
                (float(row[column]) - means[column]) / stds[column]
                for column in range(width)
            ]
            for row in test_x
        ],
    )


def _fit_logistic(
    features: list[list[float]],
    labels: list[int],
    *,
    learning_rate: float = 0.03,
    epochs: int = 900,
    l2: float = 0.02,
) -> list[float]:
    weights = [0.0] * (len(features[0]) + 1)
    count = len(features)

    for _ in range(int(epochs)):
        gradient = [0.0] * len(weights)
        for row, label in zip(features, labels):
            score = weights[0] + sum(
                weights[index + 1] * float(value)
                for index, value in enumerate(row)
            )
            error = _sigmoid(score) - int(label)
            gradient[0] += error
            for index, value in enumerate(row):
                gradient[index + 1] += error * float(value)

        for index in range(len(weights)):
            regularization = 0.0 if index == 0 else float(l2) * weights[index]
            weights[index] -= float(learning_rate) * (
                gradient[index] / count + regularization
            )

    return weights


def _model_scores(
    features: list[list[float]],
    weights: list[float],
) -> list[float]:
    return [
        _sigmoid(
            weights[0]
            + sum(
                weights[index + 1] * float(value)
                for index, value in enumerate(row)
            )
        )
        for row in features
    ]


def _auc(labels: list[int], scores: list[float]) -> float:
    order = sorted(range(len(scores)), key=lambda index: scores[index])
    ranks = [0.0] * len(scores)
    index = 0

    while index < len(order):
        end = index
        while (
            end + 1 < len(order)
            and scores[order[end + 1]] == scores[order[index]]
        ):
            end += 1
        average_rank = ((index + 1) + (end + 1)) / 2.0
        for offset in range(index, end + 1):
            ranks[order[offset]] = average_rank
        index = end + 1

    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        return 0.0

    positive_rank_sum = sum(
        ranks[index]
        for index, label in enumerate(labels)
        if int(label) == 1
    )
    return (
        positive_rank_sum - positives * (positives + 1) / 2.0
    ) / (positives * negatives)


def _threshold_for_fpr(
    labels: list[int],
    scores: list[float],
    *,
    max_fpr: float,
) -> float:
    positives = sum(labels)
    negatives = len(labels) - positives
    best_threshold = 1.1
    best_recall = -1.0

    for threshold in sorted(set(scores), reverse=True):
        true_positive = sum(
            label == 1 and score >= threshold
            for label, score in zip(labels, scores)
        )
        false_positive = sum(
            label == 0 and score >= threshold
            for label, score in zip(labels, scores)
        )
        false_rate = false_positive / negatives if negatives else 0.0
        recall = true_positive / positives if positives else 0.0

        if false_rate <= float(max_fpr) and recall >= best_recall:
            best_threshold = float(threshold)
            best_recall = recall

    return best_threshold


def _classification_metrics(
    rows: list[dict[str, Any]],
    scores: list[float],
    threshold: float,
) -> dict[str, Any]:
    selected = [
        index
        for index, score in enumerate(scores)
        if float(score) >= float(threshold)
    ]
    total_terminal = sum(int(row["label"]) for row in rows)
    total_continued = len(rows) - total_terminal
    terminal_selected = sum(
        int(rows[index]["label"]) == 1 for index in selected
    )
    continued_selected = len(selected) - terminal_selected
    within20_selected = sum(
        int(rows[index]["label"]) == 1
        and float(rows[index]["giveback"]) <= 0.20
        for index in selected
    )
    terminal_givebacks = [
        float(rows[index]["giveback"])
        for index in selected
        if int(rows[index]["label"]) == 1
    ]

    return {
        "fired": len(selected),
        "terminal_precision_pct": pct(terminal_selected, len(selected)),
        "terminal_recall_pct": pct(terminal_selected, total_terminal),
        "continued_false_exit_pct": pct(continued_selected, total_continued),
        "terminal_within20_recall_pct": pct(
            within20_selected,
            total_terminal,
        ),
        "terminal_median_giveback_pct": (
            100.0 * float(median(terminal_givebacks) or 0.0)
        ),
    }


def _fit_holdout_model(
    train_rows: list[dict[str, Any]],
    test_rows: list[dict[str, Any]],
    *,
    feature_key: str,
    max_fpr: float = 0.10,
) -> dict[str, Any]:
    train_x = [list(row[feature_key]) for row in train_rows]
    test_x = [list(row[feature_key]) for row in test_rows]
    train_y = [int(row["label"]) for row in train_rows]
    test_y = [int(row["label"]) for row in test_rows]

    train_z, test_z = _standardize(train_x, test_x)
    weights = _fit_logistic(train_z, train_y)
    train_scores = _model_scores(train_z, weights)
    test_scores = _model_scores(test_z, weights)
    threshold = _threshold_for_fpr(
        train_y,
        train_scores,
        max_fpr=max_fpr,
    )

    return {
        "feature_set": feature_key,
        "max_train_fpr": float(max_fpr),
        "train_n": len(train_rows),
        "train_terminal": sum(train_y),
        "test_n": len(test_rows),
        "test_terminal": sum(test_y),
        "train_auc": _auc(train_y, train_scores),
        "test_auc": _auc(test_y, test_scores),
        "threshold": threshold,
        "train_metrics": _classification_metrics(
            train_rows,
            train_scores,
            threshold,
        ),
        "test_metrics": _classification_metrics(
            test_rows,
            test_scores,
            threshold,
        ),
    }


def build_stage2b(
    *,
    start_ms: int = DEFAULT_START_MS,
    cutoff_ms: int = DEFAULT_CUTOFF_MS,
    arm_pct: float = DEFAULT_ARM_PCT,
) -> dict[str, Any]:
    positions, observations = _load_snapshot(
        start_ms=start_ms,
        cutoff_ms=cutoff_ms,
    )
    positions = sorted(
        positions,
        key=lambda item: int(item["opened_at_ms"]),
    )

    eligible = [
        position
        for position in positions
        if float(position["true_mfe_pct"]) >= float(arm_pct)
        and max(
            (
                float(item.current_pnl_pct)
                for item in observations[str(position["position_id"])]
            ),
            default=float("-inf"),
        )
        >= float(arm_pct)
    ]

    candidates: list[PeakCandidate] = []
    for position in eligible:
        pid = str(position["position_id"])
        candidates.extend(
            record_local_peak_candidates(
                pid,
                observations[pid],
                arm_pct=arm_pct,
            )
        )

    first_poll_rows = [
        _first_poll_row(
            candidate,
            observations[candidate.position_id],
        )
        for candidate in candidates
    ]
    terminal_rows = [
        row for row in first_poll_rows if int(row["label"]) == 1
    ]
    continued_rows = [
        row for row in first_poll_rows if int(row["label"]) == 0
    ]

    eligible_ids = [str(item["position_id"]) for item in eligible]
    train_cut = 2 * len(eligible_ids) // 3
    train_ids = set(eligible_ids[:train_cut])
    test_ids = set(eligible_ids[train_cut:])

    chronological: dict[str, Any] = {}
    third = len(eligible_ids) // 3
    groups = {
        "EARLY": set(eligible_ids[:third]),
        "MID": set(eligible_ids[third : 2 * third]),
        "LATE": set(eligible_ids[2 * third :]),
    }
    for label, ids in groups.items():
        rows = [
            row
            for row in first_poll_rows
            if str(row["position_id"]) in ids
        ]
        terminals = [row for row in rows if int(row["label"]) == 1]
        chronological[label] = {
            "candidates": len(rows),
            "terminal": len(terminals),
            "terminal_rate_pct": pct(len(terminals), len(rows)),
            "terminal_within20_pct": pct(
                sum(float(row["giveback"]) <= 0.20 for row in terminals),
                len(terminals),
            ),
            "terminal_median_first_poll_giveback_pct": (
                100.0
                * float(
                    median(
                        float(row["giveback"])
                        for row in terminals
                    )
                    or 0.0
                )
            ),
        }

    train_full = [
        row for row in first_poll_rows
        if str(row["position_id"]) in train_ids
    ]
    test_full = [
        row for row in first_poll_rows
        if str(row["position_id"]) in test_ids
    ]
    train_safe = [
        row for row in train_full
        if float(row["giveback"]) <= 0.20
    ]
    test_safe = [
        row for row in test_full
        if float(row["giveback"]) <= 0.20
    ]

    first_poll = {
        "candidates": len(first_poll_rows),
        "terminal": len(terminal_rows),
        "continued": len(continued_rows),
        "terminal_median_giveback_pct": (
            100.0
            * float(
                median(float(row["giveback"]) for row in terminal_rows)
                or 0.0
            )
        ),
        "continued_median_giveback_pct": (
            100.0
            * float(
                median(float(row["giveback"]) for row in continued_rows)
                or 0.0
            )
        ),
        "terminal_within20_pct": pct(
            sum(float(row["giveback"]) <= 0.20 for row in terminal_rows),
            len(terminal_rows),
        ),
        "terminal_already_beyond20_pct": pct(
            sum(float(row["giveback"]) > 0.20 for row in terminal_rows),
            len(terminal_rows),
        ),
    }

    holdout = {
        "train_position_count": len(train_ids),
        "test_position_count": len(test_ids),
        "full_window": {
            "all_features": _fit_holdout_model(
                train_full,
                test_full,
                feature_key="all_features",
                max_fpr=0.10,
            ),
            "context_only": _fit_holdout_model(
                train_full,
                test_full,
                feature_key="context_features",
                max_fpr=0.10,
            ),
        },
        "safe_window_giveback_le_20": {
            "train_rows": len(train_safe),
            "test_rows": len(test_safe),
            "train_terminal": sum(int(row["label"]) for row in train_safe),
            "test_terminal": sum(int(row["label"]) for row in test_safe),
            "all_features": _fit_holdout_model(
                train_safe,
                test_safe,
                feature_key="all_features",
                max_fpr=0.10,
            ),
            "context_only": _fit_holdout_model(
                train_safe,
                test_safe,
                feature_key="context_features",
                max_fpr=0.10,
            ),
        },
    }

    return {
        "stage": "PP-DECISION-V3-STAGE2B-CAUSAL-PEAK-DETECTOR-REPLAY",
        "status": "COMPLETE_RESEARCH_NO_PROMOTION",
        "start_ms": int(start_ms),
        "cutoff_ms": int(cutoff_ms),
        "arm_pct": float(arm_pct),
        "observable_arm_trades": len(eligible),
        "record_local_peak_candidates": len(candidates),
        "terminal_candidates": len(terminal_rows),
        "continued_candidates": len(continued_rows),
        "first_post_peak_poll": first_poll,
        "chronological_first_poll": chronological,
        "stateful_rule_frontier": build_stateful_frontier(
            candidates,
            observations,
        ),
        "chronological_holdout": holdout,
        "conclusion": {
            "production_promotion": False,
            "stage2c_partial_protect_unblocked": False,
            "primary_findings": [
                "A material share of terminal peaks are already beyond the 20% giveback boundary at the first post-peak poll.",
                "Stateful recovery rules cannot keep continued false exits below 25% in the tested causal grid.",
                "Within the <=20% safe window, context-only late-cohort discrimination is approximately random.",
                "Adding giveback improves discrimination only modestly and still yields low recall at controlled false-exit rates.",
            ],
            "next_required_research": (
                "Improve peak observability/cadence and/or add richer sub-poll causal evidence "
                "before testing partial-protect quantity as a production candidate."
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-ms", type=int, default=DEFAULT_START_MS)
    parser.add_argument("--cutoff-ms", type=int, default=DEFAULT_CUTOFF_MS)
    parser.add_argument("--arm-pct", type=float, default=DEFAULT_ARM_PCT)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    result = build_stage2b(
        start_ms=args.start_ms,
        cutoff_ms=args.cutoff_ms,
        arm_pct=args.arm_pct,
    )
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
    print(payload)


if __name__ == "__main__":
    main()
