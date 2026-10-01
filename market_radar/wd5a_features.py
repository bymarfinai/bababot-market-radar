from __future__ import annotations

import csv
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2.extras

from .persistence import _postgres_connect
from .wd2_anatomy import WD2_CUTOFF_MS


WD5A_VERSION = "wd5a-causal-entry-features-v1"
WD4_RESULT_PATH = Path("/app/data/wd4_resolution_results.json")
CSV_OUTPUT_PATH = Path("/app/data/wd5a_causal_entry_features.csv")
JSONL_OUTPUT_PATH = Path("/app/data/wd5a_causal_entry_features.jsonl")
MANIFEST_OUTPUT_PATH = Path("/app/data/wd5a_feature_manifest.json")
EXPECTED_ROWS = 849

TARGET_COLUMNS = (
    "target_strict_1_to_1",
    "target_extended_stop",
    "target_robust_1_to_1",
)

META_COLUMNS = (
    "meta_position_id",
    "meta_signal_id",
    "meta_symbol",
    "meta_original_side",
    "meta_opened_at_ms",
)

LEAKAGE_DENYLIST = {
    "closed_at_ms",
    "realized_pnl",
    "realized_pnl_pct",
    "exit_price",
    "mfe_pct",
    "mae_pct",
    "outcome_label",
    "wd4_best_net",
    "wd4_first_target_at",
}


def _j(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        obj = json.loads(value or "{}")
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _f(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _b(value: Any) -> int | None:
    if value is None:
        return None
    return int(bool(value))


def _safe_delta_ms(later: Any, earlier: Any) -> float | None:
    if later is None or earlier is None:
        return None
    return (int(later) - int(earlier)) / 1000.0


def _load_targets() -> dict[str, dict[str, Any]]:
    payload = json.loads(WD4_RESULT_PATH.read_text())
    rows = payload.get("primary_mapping") or []
    targets: dict[str, dict[str, Any]] = {}
    for row in rows:
        pid = str(row["position_id"])
        targets[pid] = {
            "target_strict_1_to_1": row.get("strict_1_to_1_target"),
            "target_extended_stop": row.get("extended_stop_target"),
            "target_robust_1_to_1": row.get("robust_1_to_1_target"),
        }
    if len(targets) != EXPECTED_ROWS:
        raise RuntimeError(
            f"WD5A expected {EXPECTED_ROWS} WD4 target rows, got {len(targets)}"
        )
    return targets


def _load_source_rows() -> list[dict[str, Any]]:
    query = """
        select
            w.position_id, w.signal_id, w.symbol, w.side, w.opened_at_ms,
            s.signal_time_ms, s.stage, s.long_score, s.short_score,
            s.score_edge, s.volume_ratio, s.structure_status,
            s.taker_bias, s.raw_oi_change_pct, s.funding_rate,
            s.market_regime, s.decision_context_balance,
            s.snapshot_json as signal_snapshot_json,
            e.candle_close_at_ms, e.signal_created_at_ms,
            e.ai_queued_at_ms, e.ai_started_at_ms, e.ai_finished_at_ms,
            e.stage11c_started_at_ms, e.stage11c_finished_at_ms,
            e.order_created_at_ms, e.position_opened_at_ms,
            r.checked_at_ms as gate_checked_at_ms,
            r.reasons_json as gate_reasons_json,
            r.snapshot_json as gate_snapshot_json
        from wd1_trade_labels w
        join signals s on s.signal_id=w.signal_id
        join entry_latency e on e.signal_id=w.signal_id
        join lateral (
            select checked_at_ms, reasons_json, snapshot_json
            from entry_revalidations x
            where x.signal_id=w.signal_id
              and x.verdict='ENTER'
              and x.checked_at_ms <= w.opened_at_ms
            order by x.checked_at_ms desc
            limit 1
        ) r on true
        where w.outcome_label='TRUE_WRONG_DIRECTION'
          and w.closed_at_ms <= %s
        order by w.opened_at_ms, w.position_id
    """
    with _postgres_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (WD2_CUTOFF_MS,))
            rows = [dict(row) for row in cur.fetchall()]
    if len(rows) != EXPECTED_ROWS:
        raise RuntimeError(
            f"WD5A expected {EXPECTED_ROWS} source rows, got {len(rows)}"
        )
    return rows


def _score_components(
    signal: dict[str, Any],
    side: str,
) -> dict[str, float | None]:
    long_components = signal.get("long_score_components") or {}
    short_components = signal.get("short_score_components") or {}
    if not isinstance(long_components, dict):
        long_components = {}
    if not isinstance(short_components, dict):
        short_components = {}
    selected = long_components if side == "LONG" else short_components
    opposite = short_components if side == "LONG" else long_components
    out: dict[str, float | None] = {}
    for key in ("activity", "momentum", "persistence", "timeframe_consistency"):
        sel = _f(selected.get(key))
        opp = _f(opposite.get(key))
        out[f"f_score_component_selected_{key}"] = sel
        out[f"f_score_component_opposite_{key}"] = opp
        out[f"f_score_component_delta_{key}"] = (
            None if sel is None or opp is None else sel - opp
        )
    return out


def _gate_reason_flags(raw: Any) -> dict[str, int]:
    try:
        reasons = json.loads(raw or "[]")
    except Exception:
        reasons = []
    if not isinstance(reasons, list):
        reasons = []
    values = {str(x) for x in reasons}
    known = (
        "family:price_structure_aligned",
        "family:flow_aligned",
        "family:flow_neutral",
        "family:flow_opposite",
        "family:positioning_aligned",
        "family:positioning_neutral",
        "family:positioning_supportive",
        "positioning_unwind_supportive_not_fresh",
        "family:regime_aligned",
        "family:regime_neutral",
        "family:regime_opposite",
        "counter_regime_entry",
    )
    return {
        "f_gate_reason_" + reason.replace(":", "_"): int(reason in values)
        for reason in known
    }


def reconstruct_row(
    source: dict[str, Any],
    targets: dict[str, Any],
) -> dict[str, Any]:
    side = str(source.get("side") or "").upper()
    sign = 1.0 if side == "LONG" else -1.0
    signal = _j(source.get("signal_snapshot_json"))
    gate = _j(source.get("gate_snapshot_json"))
    context = signal.get("market_context") or {}
    if not isinstance(context, dict):
        context = {}
    positioning = gate.get("positioning_detail") or {}
    if not isinstance(positioning, dict):
        positioning = {}
    families = gate.get("evidence_families") or {}
    if not isinstance(families, dict):
        families = {}

    long_score = _f(signal.get("long_score"))
    short_score = _f(signal.get("short_score"))
    selected_score = long_score if side == "LONG" else short_score
    opposite_score = short_score if side == "LONG" else long_score

    opened_at_ms = int(source["opened_at_ms"])
    gate_checked_at_ms = int(source["gate_checked_at_ms"])
    dt = datetime.fromtimestamp(gate_checked_at_ms / 1000.0, tz=timezone.utc)
    hour = dt.hour + dt.minute / 60.0 + dt.second / 3600.0

    row: dict[str, Any] = {
        "meta_position_id": str(source["position_id"]),
        "meta_signal_id": str(source["signal_id"]),
        "meta_symbol": str(source["symbol"]),
        "meta_original_side": side,
        "meta_opened_at_ms": opened_at_ms,
        **targets,

        "f_side_is_long": int(side == "LONG"),
        "f_decision_hour_utc": hour,
        "f_decision_hour_sin": math.sin(2.0 * math.pi * hour / 24.0),
        "f_decision_hour_cos": math.cos(2.0 * math.pi * hour / 24.0),
        "f_decision_weekday_utc": dt.weekday(),

        "f_long_score": long_score,
        "f_short_score": short_score,
        "f_selected_score": selected_score,
        "f_opposite_score": opposite_score,
        "f_score_edge_selected_minus_opposite": (
            None
            if selected_score is None or opposite_score is None
            else selected_score - opposite_score
        ),
        "f_score_edge_snapshot": _f(signal.get("score_edge")),
        "f_score_gap_snapshot": _f(signal.get("score_gap")),
        "f_decision_context_balance": _f(signal.get("decision_context_balance")),
        "f_decision_context_confirmations": _f(signal.get("decision_context_confirmations")),
        "f_decision_context_conflicts": _f(signal.get("decision_context_conflicts")),
        "f_evidence_count": _f(signal.get("evidence_count")),

        "f_ret_5m_pct_raw": _f(signal.get("ret_5m_pct")),
        "f_ret_15m_pct_raw": _f(signal.get("ret_15m_pct")),
        "f_ret_1h_pct_raw": _f(signal.get("ret_1h_pct")),
        "f_ret_24h_pct_raw": _f(signal.get("ret_24h_pct")),
        "f_ret_5m_pct_for_selected": (
            None if _f(signal.get("ret_5m_pct")) is None
            else float(signal["ret_5m_pct"]) * sign
        ),
        "f_ret_15m_pct_for_selected": (
            None if _f(signal.get("ret_15m_pct")) is None
            else float(signal["ret_15m_pct"]) * sign
        ),
        "f_ret_1h_pct_for_selected": (
            None if _f(signal.get("ret_1h_pct")) is None
            else float(signal["ret_1h_pct"]) * sign
        ),
        "f_ret_24h_pct_for_selected": (
            None if _f(signal.get("ret_24h_pct")) is None
            else float(signal["ret_24h_pct"]) * sign
        ),
        "f_median_abs_ret_5m_pct": _f(signal.get("median_abs_ret_5m_pct")),
        "f_return_expansion_ratio": _f(signal.get("return_expansion_ratio")),
        "f_range_ratio": _f(signal.get("range_ratio")),
        "f_trades_ratio": _f(signal.get("trades_ratio")),
        "f_volume_ratio_signal": _f(signal.get("volume_ratio")),
        "f_directional_persistence": _b(signal.get("directional_persistence")),
        "f_is_moving": _b(signal.get("is_moving")),

        "f_stage": str(signal.get("stage") or "MISSING").upper(),
        "f_movement_state": str(signal.get("movement_state") or "MISSING").upper(),
        "f_direction_hint": str(signal.get("direction_hint") or "MISSING").upper(),
        "f_decision_side_candidate": str(
            signal.get("decision_side_candidate") or "MISSING"
        ).upper(),

        "f_context_breakout": _b(context.get("breakout")),
        "f_context_breakdown": _b(context.get("breakdown")),
        "f_context_failed_breakout": _b(context.get("failed_breakout")),
        "f_context_failed_breakdown": _b(context.get("failed_breakdown")),
        "f_context_breakout_up_pct": _f(context.get("breakout_up_pct")),
        "f_context_breakdown_down_pct": _f(context.get("breakdown_down_pct")),
        "f_context_volume_confirmed": _b(context.get("volume_confirmed")),
        "f_context_volume_ratio": _f(context.get("volume_ratio")),
        "f_context_taker_buy_share": _f(context.get("taker_buy_share")),
        "f_context_taker_buy_sell_ratio": _f(context.get("taker_buy_sell_ratio")),
        "f_context_taker_share_for_selected": (
            _f(context.get("taker_buy_share"))
            if side == "LONG"
            else (
                None
                if _f(context.get("taker_buy_share")) is None
                else 1.0 - float(context["taker_buy_share"])
            )
        ),
        "f_context_raw_oi_change_pct": _f(context.get("raw_oi_change_pct")),
        "f_context_funding_rate": _f(context.get("funding_rate")),
        "f_context_regime_atr14": _f(context.get("regime_atr14")),
        "f_context_regime_ema7": _f(context.get("regime_ema7")),
        "f_context_regime_ema20": _f(context.get("regime_ema20")),
        "f_context_regime_hh": _f(context.get("regime_hh")),
        "f_context_regime_hl": _f(context.get("regime_hl")),
        "f_context_regime_lh": _f(context.get("regime_lh")),
        "f_context_regime_ll": _f(context.get("regime_ll")),
        "f_context_quote_volume_5m": _f(context.get("quote_volume_5m")),
        "f_context_quote_volume_24h": _f(context.get("quote_volume_24h")),
        "f_context_structure_status": str(
            context.get("structure_status") or "MISSING"
        ).upper(),
        "f_context_taker_bias": str(context.get("taker_bias") or "MISSING").upper(),
        "f_context_oi_interpretation": str(
            context.get("oi_interpretation") or "MISSING"
        ).upper(),
        "f_context_market_regime": str(
            context.get("market_regime") or "MISSING"
        ).upper(),

        "f_gate_side_ret_1m_pct": _f(gate.get("side_ret_1m_pct")),
        "f_gate_side_ret_3m_pct": _f(gate.get("side_ret_3m_pct")),
        "f_gate_ret_1m_pct_raw": _f(gate.get("ret_1m_pct")),
        "f_gate_ret_3m_pct_raw": _f(gate.get("ret_3m_pct")),
        "f_gate_price_drift_pct": _f(gate.get("price_drift_pct")),
        "f_gate_side_adjusted_drift_pct": _f(gate.get("side_adjusted_drift_pct")),
        "f_gate_impulse_concentration_ratio": _f(
            gate.get("impulse_concentration_ratio")
        ),
        "f_gate_taker_buy_share_1m": _f(gate.get("taker_buy_share_1m")),
        "f_gate_taker_share_for_selected": (
            _f(gate.get("taker_buy_share_1m"))
            if side == "LONG"
            else (
                None
                if _f(gate.get("taker_buy_share_1m")) is None
                else 1.0 - float(gate["taker_buy_share_1m"])
            )
        ),
        "f_gate_positioning_oi_change_pct": _f(positioning.get("oi_change_pct")),
        "f_gate_aligned_family_count": _f(gate.get("aligned_family_count")),
        "f_gate_opposing_family_count": _f(gate.get("opposing_family_count")),
        "f_gate_closed_1m_count": _f(gate.get("closed_1m_count")),
        "f_gate_soft_chase_threshold_pct": _f(
            gate.get("soft_chase_threshold_pct")
        ),
        "f_gate_signal_age_s": (
            None
            if _f(gate.get("signal_age_ms")) is None
            else float(gate["signal_age_ms"]) / 1000.0
        ),
        "f_gate_approval_age_s": (
            None
            if _f(gate.get("approval_age_ms")) is None
            else float(gate["approval_age_ms"]) / 1000.0
        ),
        "f_gate_ret1_aligned": _b(gate.get("ret1_aligned")),
        "f_gate_ret1_opposite": _b(gate.get("ret1_opposite")),
        "f_gate_ret3_aligned": _b(gate.get("ret3_aligned")),
        "f_gate_ret3_opposite": _b(gate.get("ret3_opposite")),
        "f_gate_taker_aligned": _b(gate.get("taker_aligned")),
        "f_gate_taker_opposite": _b(gate.get("taker_opposite")),
        "f_gate_aligned_micro_structure": _b(gate.get("aligned_micro_structure")),
        "f_gate_opposite_micro_structure": _b(gate.get("opposite_micro_structure")),
        "f_gate_near_entry_support": _b(gate.get("near_entry_support")),
        "f_gate_soft_chase": _b(gate.get("soft_chase")),
        "f_gate_concentrated_impulse": _b(gate.get("concentrated_impulse")),
        "f_gate_price_family": str(
            families.get("PRICE_STRUCTURE") or "MISSING"
        ).upper(),
        "f_gate_flow_family": str(families.get("FLOW") or "MISSING").upper(),
        "f_gate_positioning_family": str(
            families.get("POSITIONING") or "MISSING"
        ).upper(),
        "f_gate_regime_family": str(families.get("REGIME") or "MISSING").upper(),
        "f_gate_family_combo": "|".join(
            str(families.get(k) or "MISSING").upper()
            for k in ("PRICE_STRUCTURE", "FLOW", "POSITIONING", "REGIME")
        ),
        "f_gate_positioning_interpretation": str(
            positioning.get("interpretation") or "MISSING"
        ).upper(),

        "f_latency_ai_queue_s": _safe_delta_ms(
            source.get("ai_started_at_ms"), source.get("ai_queued_at_ms")
        ),
        "f_latency_ai_execution_s": _safe_delta_ms(
            source.get("ai_finished_at_ms"), source.get("ai_started_at_ms")
        ),
        "f_latency_stage11c_s": _safe_delta_ms(
            source.get("stage11c_finished_at_ms"),
            source.get("stage11c_started_at_ms"),
        ),
    }

    row.update(_score_components(signal, side))
    row.update(_gate_reason_flags(source.get("gate_reasons_json")))
    return row


def causal_audit(source_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Audit feature availability at the Stage11C ENTER decision timestamp."""
    violations: Counter[str] = Counter()
    excluded_post_gate: Counter[str] = Counter()
    for row in source_rows:
        opened = int(row["opened_at_ms"])
        gate_checked = int(row["gate_checked_at_ms"])

        if gate_checked > opened:
            violations["gate_checked_after_fill"] += 1

        candidate_feature_times = {
            "candle_close": row.get("candle_close_at_ms"),
            "signal_created": row.get("signal_created_at_ms"),
            "ai_queued": row.get("ai_queued_at_ms"),
            "ai_started": row.get("ai_started_at_ms"),
            "ai_finished": row.get("ai_finished_at_ms"),
            "stage11c_started": row.get("stage11c_started_at_ms"),
            "stage11c_finished": row.get("stage11c_finished_at_ms"),
        }
        for label, ts in candidate_feature_times.items():
            if ts is not None and int(ts) > gate_checked:
                violations[label + "_after_decision_cutoff"] += 1

        # These fields are intentionally not model features. Record their
        # post-gate nature so the manifest proves why they were excluded.
        for label in ("order_created_at_ms", "position_opened_at_ms"):
            ts = row.get(label)
            if ts is not None and int(ts) > gate_checked:
                excluded_post_gate[label] += 1

        if row.get("position_opened_at_ms") is not None and (
            int(row["position_opened_at_ms"]) != opened
        ):
            violations["position_opened_timestamp_mismatch"] += 1

    return {
        "rows": len(source_rows),
        "decision_cutoff": "latest causal Stage11C ENTER checked_at_ms <= fill",
        "violation_counts": dict(violations),
        "excluded_post_gate_counts": dict(excluded_post_gate),
        "causal_pass": not bool(violations),
    }


def _column_type(values: list[Any]) -> str:
    nonnull = [x for x in values if x is not None and x != ""]
    if not nonnull:
        return "empty"
    if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in nonnull):
        return "numeric"
    return "categorical"


def build_dataset() -> dict[str, Any]:
    targets = _load_targets()
    sources = _load_source_rows()
    audit = causal_audit(sources)
    if not audit["causal_pass"]:
        raise RuntimeError(f"WD5A causal audit failed: {audit}")

    rows: list[dict[str, Any]] = []
    for source in sources:
        pid = str(source["position_id"])
        if pid not in targets:
            raise RuntimeError(f"missing WD4 targets for {pid}")
        rows.append(reconstruct_row(source, targets[pid]))

    if len(rows) != EXPECTED_ROWS:
        raise RuntimeError(f"WD5A row mismatch: {len(rows)}")

    columns = list(rows[0].keys())
    feature_columns = [c for c in columns if c.startswith("f_")]

    leaking = [
        c for c in feature_columns
        if c.replace("f_", "", 1) in LEAKAGE_DENYLIST
    ]
    if leaking:
        raise RuntimeError(f"leakage-denylist features found: {leaking}")

    CSV_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUTPUT_PATH.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    with JSONL_OUTPUT_PATH.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n")

    feature_manifest = []
    for column in feature_columns:
        values = [row.get(column) for row in rows]
        nonnull = sum(v is not None and v != "" for v in values)
        unique = len({str(v) for v in values if v is not None and v != ""})
        feature_manifest.append({
            "feature": column,
            "type": _column_type(values),
            "nonnull_n": nonnull,
            "missing_n": len(rows) - nonnull,
            "coverage_pct": 100.0 * nonnull / len(rows),
            "unique_values": unique,
        })

    target_counts = {
        target: dict(Counter(str(row[target]) for row in rows))
        for target in TARGET_COLUMNS
    }
    constant_features = [
        item["feature"]
        for item in feature_manifest
        if item["unique_values"] <= 1
    ]
    model_feature_columns = [
        item["feature"]
        for item in feature_manifest
        if item["unique_values"] > 1
    ]

    manifest = {
        "version": WD5A_VERSION,
        "authority": "RESEARCH_ONLY",
        "rows": len(rows),
        "feature_count": len(feature_columns),
        "numeric_feature_count": sum(
            x["type"] == "numeric" for x in feature_manifest
        ),
        "categorical_feature_count": sum(
            x["type"] == "categorical" for x in feature_manifest
        ),
        "metadata_columns": list(META_COLUMNS),
        "target_columns": list(TARGET_COLUMNS),
        "feature_columns": feature_columns,
        "model_feature_columns": model_feature_columns,
        "model_feature_count": len(model_feature_columns),
        "constant_features_excluded_from_model": constant_features,
        "target_counts": target_counts,
        "causal_audit": audit,
        "feature_manifest": feature_manifest,
        "excluded_from_features": {
            "future_outcomes": sorted(LEAKAGE_DENYLIST),
            "high_cardinality_metadata": [
                "position_id",
                "signal_id",
                "symbol",
                "opened_at_ms",
            ],
            "free_text_reasons": (
                "Excluded because parameterized/high-cardinality and duplicated "
                "by structured causal fields."
            ),
            "wd4_future_path_metrics": (
                "Used only to create target labels; never exposed as f_* features."
            ),
            "post_gate_timing": [
                "order_created_at_ms",
                "position_opened_at_ms",
                "candle_to_fill",
                "signal_created_to_fill",
                "gate_to_fill",
                "order_to_fill",
            ],
        },
        "outputs": {
            "csv": str(CSV_OUTPUT_PATH),
            "jsonl": str(JSONL_OUTPUT_PATH),
            "manifest": str(MANIFEST_OUTPUT_PATH),
        },
    }
    MANIFEST_OUTPUT_PATH.write_text(json.dumps(manifest, indent=2, allow_nan=False))
    return manifest
