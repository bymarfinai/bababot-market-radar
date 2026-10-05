from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any


from .ai_provider import (
    active_model,
    call_model_review,
    parse_provider_response,
    primary_provider,
)
from .multi_model import run_stage11b_failover
from .control_state import get_control_state
from .persistence import (
    get_pending_entry_signals,
    save_entry_approval,
    save_model_review,
    update_entry_latency,
)


AI_APPROVAL_VERSION = "stage11-v3-fast-pool"
FAST_POOL_VERSION = "stage11-fast-pool-v1"
RISK_GATE_VERSION = "stage11-risk-v1"
PROMPT_VERSION = "stage11-entry-review-v1"

_processing_lock = threading.Lock()


SYSTEM_PROMPT = """You are BabaBot's AI Entry Supervisor.

You receive a deterministic Market Radar LONG or SHORT signal that has already
passed the core signal engine and a deterministic safety/risk gate.

Your job is a SECOND-LAYER entry-quality review only.

Return exactly one verdict:
- APPROVE: context is sufficiently aligned for the proposed direction now.
- VETO: material context contradicts the proposed direction or the setup quality is poor.
- WATCH: evidence is mixed/uncertain; do not enter yet.

Rules:
1. Never change LONG into SHORT or SHORT into LONG.
2. Never invent missing market data.
3. Do not propose leverage, position size, entry price, stop loss, or take profit.
4. Funding is observational context and must not be the sole reason for a VETO.
5. Use stage, score/edge, volume, structure, taker flow, raw OI, funding,
   market regime, and the deterministic decision reasons together.
6. Prefer WATCH over APPROVE when important evidence is mixed.
7. A future execution engine may act only on APPROVE, so be selective.
8. Output valid JSON only, with no markdown or preamble.

Schema:
{
  "verdict": "APPROVE|VETO|WATCH",
  "confidence": 0.0,
  "reasons": ["short factual reason", "..."],
  "risk_flags": ["optional flag", "..."]
}
"""


def approval_enabled() -> bool:
    value = os.environ.get("AI_APPROVAL_ENABLED", "false").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _max_age_ms() -> int:
    minutes = float(os.environ.get("AI_APPROVAL_MAX_AGE_MINUTES", "15"))
    return max(1, int(minutes * 60_000))


def _max_per_scan() -> int:
    return max(1, min(int(os.environ.get("AI_APPROVAL_MAX_PER_SCAN", "24")), 50))


def _fast_pool_targets() -> list[tuple[str, str]]:
    raw = os.environ.get(
        "AI_FAST_POOL_TARGETS",
        "clario1:gpt-5.6-sol",
    )
    targets: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in raw.split(","):
        provider, sep, model = item.strip().partition(":")
        target = (provider.strip().lower(), model.strip())
        if not sep or not target[0] or not target[1] or target in seen:
            continue
        targets.append(target)
        seen.add(target)
    if not targets:
        targets.append((primary_provider(), active_model()))
    return targets


def _workers() -> int:
    default = min(len(_fast_pool_targets()), 4)
    return max(
        1,
        min(int(os.environ.get("AI_APPROVAL_WORKERS", str(default))), 4),
    )


def _target_for_index(index: int) -> tuple[str, str]:
    targets = _fast_pool_targets()
    return targets[index % len(targets)]


def _alternate_target(
    primary: tuple[str, str],
) -> tuple[str, str] | None:
    return next((target for target in _fast_pool_targets() if target != primary), None)


def evaluate_entry_risk(
    signal: dict[str, Any],
    *,
    now_ms: int | None = None,
) -> dict[str, Any]:
    """Deterministic fail-closed safety gate before the AI review."""
    reasons: list[str] = []
    side = str(signal.get("side") or "").upper()
    stage = str(signal.get("stage") or "").upper()
    score = signal.get("long_score") if side == "LONG" else signal.get("short_score")

    if side not in {"LONG", "SHORT"}:
        reasons.append("invalid_side")
    if stage not in {"IGNITION", "EXPANSION"}:
        reasons.append("stage_not_entry_eligible")
    if score is None or float(score) < 68.0:
        reasons.append("winning_score_below_stage6_floor")
    edge = signal.get("score_edge")
    if edge is None or float(edge) < 10.0:
        reasons.append("score_edge_below_stage6_floor")
    balance = signal.get("decision_context_balance")
    if balance is None or int(balance) < 1:
        reasons.append("context_balance_below_stage6_floor")

    price = signal.get("signal_price")
    if price is None or float(price) <= 0:
        reasons.append("missing_signal_price")

    required_context = (
        "structure_status",
        "taker_bias",
        "raw_oi_change_pct",
        "funding_rate",
        "market_regime",
    )
    missing = [name for name in required_context if signal.get(name) is None]
    if missing:
        reasons.append("missing_context:" + ",".join(missing))

    structure = str(signal.get("structure_status") or "").upper()
    if side == "LONG" and structure == "BREAKDOWN":
        reasons.append("hard_structural_conflict")
    if side == "SHORT" and structure == "BREAKOUT":
        reasons.append("hard_structural_conflict")

    current_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    signal_ms = int(signal.get("signal_time_ms") or 0)
    age_ms = current_ms - signal_ms
    if signal_ms <= 0:
        reasons.append("invalid_signal_time")
    elif age_ms < -60_000:
        reasons.append("signal_time_in_future")
    elif age_ms > _max_age_ms():
        reasons.append("stale_signal")

    return {
        "version": RISK_GATE_VERSION,
        "verdict": "PASS" if not reasons else "FAIL",
        "reasons": reasons,
        "signal_age_ms": age_ms,
    }


def _signal_for_ai(signal: dict[str, Any]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    try:
        snapshot = json.loads(signal.get("snapshot_json") or "{}")
    except Exception:
        snapshot = {}

    decision_reasons: list[str] = []
    try:
        decision_reasons = json.loads(signal.get("decision_reasons_json") or "[]")
    except Exception:
        pass

    market_context = snapshot.get("market_context") or {}

    return {
        "signal_id": signal.get("signal_id"),
        "symbol": signal.get("symbol"),
        "direction": signal.get("side"),
        "signal_time_ms": signal.get("signal_time_ms"),
        "signal_price": signal.get("signal_price"),
        "stage": signal.get("stage"),
        "long_score": signal.get("long_score"),
        "short_score": signal.get("short_score"),
        "score_edge": signal.get("score_edge"),
        "volume_ratio": signal.get("volume_ratio"),
        "structure_status": signal.get("structure_status"),
        "taker_bias": signal.get("taker_bias"),
        "raw_oi_change_pct": signal.get("raw_oi_change_pct"),
        "raw_oi_interpretation": market_context.get("raw_oi_interpretation"),
        "funding_rate": signal.get("funding_rate"),
        "market_regime": signal.get("market_regime"),
        "decision_context_balance": signal.get("decision_context_balance"),
        "decision_reasons": decision_reasons,
        "returns": {
            "5m_pct": snapshot.get("ret_5m_pct"),
            "15m_pct": snapshot.get("ret_15m_pct"),
            "1h_pct": snapshot.get("ret_1h_pct"),
            "24h_pct": snapshot.get("ret_24h_pct"),
        },
        "activity": {
            "range_ratio": snapshot.get("range_ratio"),
            "trades_ratio": snapshot.get("trades_ratio"),
            "return_expansion_ratio": snapshot.get("return_expansion_ratio"),
            "directional_persistence": snapshot.get("directional_persistence"),
        },
    }


def _parse_ai_response(data: dict[str, Any]) -> dict[str, Any]:
    """Backward-compatible parser wrapper used by Stage 11 tests."""
    return parse_provider_response(data)


def call_ai_entry_review(
    signal: dict[str, Any],
    *,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    if not approval_enabled():
        raise RuntimeError("AI_APPROVAL_ENABLED is false")
    return call_model_review(
        _signal_for_ai(signal),
        system_prompt=SYSTEM_PROMPT,
        provider=(provider or primary_provider()),
        model=(model or active_model()),
    )


def _review_with_target(
    signal: dict[str, Any],
    *,
    provider: str,
    model: str,
    role: str,
    reviewed_at_ms: int,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        result = call_ai_entry_review(
            signal,
            provider=provider,
            model=model,
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        row = {
            **result,
            "provider": provider,
            "model": model,
            "latency_ms": latency_ms,
            "status": "OK",
            "role": role,
        }
        save_model_review(
            signal_id=signal["signal_id"],
            reviewed_at_ms=reviewed_at_ms,
            role=role,
            model=f"{provider}:{model}",
            verdict=result["verdict"],
            confidence=result["confidence"],
            reasons=result.get("reasons") or [],
            risk_flags=result.get("risk_flags") or [],
            latency_ms=latency_ms,
            status="OK",
            error_text=None,
            raw=row,
        )
        return row
    except Exception as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        save_model_review(
            signal_id=signal["signal_id"],
            reviewed_at_ms=reviewed_at_ms,
            role=role,
            model=f"{provider}:{model}",
            verdict=None,
            confidence=None,
            reasons=[],
            risk_flags=[],
            latency_ms=latency_ms,
            status="ERROR",
            error_text=f"{type(exc).__name__}: {str(exc)[:300]}",
            raw=None,
        )
        return {
            "status": "ERROR",
            "role": role,
            "provider": provider,
            "model": model,
            "latency_ms": latency_ms,
            "error_type": type(exc).__name__,
            "error": str(exc)[:500],
        }


def review_signal(
    signal: dict[str, Any],
    *,
    target: tuple[str, str] | None = None,
    now_ms: int | None = None,
) -> dict[str, Any]:
    reviewed_at_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    update_entry_latency(
        signal["signal_id"],
        ai_started_at_ms=reviewed_at_ms,
    )
    risk = evaluate_entry_risk(signal, now_ms=reviewed_at_ms)
    primary_target = target or _target_for_index(0)

    if risk["verdict"] != "PASS":
        result = {
            "signal_id": signal["signal_id"],
            "risk_verdict": "FAIL",
            "ai_verdict": "NOT_CALLED",
            "final_verdict": "VETO",
            "confidence": None,
            "model": None,
            "risk_reasons": risk["reasons"],
            "ai_reasons": [],
            "risk": risk,
            "ai": None,
            "fast_pool": {
                "version": FAST_POOL_VERSION,
                "primary_target": primary_target,
                "fallback_used": False,
            },
        }
    else:
        provider, model = primary_target
        primary = _review_with_target(
            signal,
            provider=provider,
            model=model,
            role="FAST_PRIMARY",
            reviewed_at_ms=reviewed_at_ms,
        )
        chosen = primary
        fallback = None

        if primary.get("status") != "OK":
            fallback = run_stage11b_failover(
                signal_id=signal["signal_id"],
                reviewed_at_ms=reviewed_at_ms,
                payload=_signal_for_ai(signal),
                system_prompt=SYSTEM_PROMPT,
                failed_target=primary_target,
                alternate_target=_alternate_target(primary_target),
            )
            alternate = fallback.get("alternate") or {}
            if fallback.get("status") == "OK" and alternate.get("status") == "OK":
                chosen = alternate

        if chosen.get("status") == "OK":
            ai_verdict = str(chosen.get("verdict") or "WATCH")
            final_verdict = ai_verdict
            confidence = float(chosen.get("confidence") or 0.0)
            ai_reasons = list(chosen.get("reasons") or [])
            model_name = f"{chosen.get('provider')}:{chosen.get('model')}"
        else:
            ai_verdict = "ERROR"
            final_verdict = "VETO"
            confidence = None
            ai_reasons = [
                (fallback or {}).get("fallback_reason")
                or "fast_pool_all_targets_failed"
            ]
            model_name = f"{provider}:{model}"

        result = {
            "signal_id": signal["signal_id"],
            "risk_verdict": "PASS",
            "ai_verdict": ai_verdict,
            "final_verdict": final_verdict,
            "confidence": confidence,
            "model": model_name,
            "risk_reasons": [],
            "ai_reasons": ai_reasons,
            "risk": risk,
            "ai": chosen,
            "fast_pool": {
                "version": FAST_POOL_VERSION,
                "primary_target": {
                    "provider": provider,
                    "model": model,
                },
                "primary": primary,
                "fallback_used": fallback is not None,
                "fallback": fallback,
            },
        }

    ai_finished_at_ms = int(time.time() * 1000)
    result["entry_latency"] = {
        "ai_started_at_ms": reviewed_at_ms,
        "ai_finished_at_ms": ai_finished_at_ms,
        "ai_total_ms": max(0, ai_finished_at_ms - reviewed_at_ms),
    }

    save_entry_approval(
        signal_id=signal["signal_id"],
        reviewed_at_ms=reviewed_at_ms,
        risk_verdict=result["risk_verdict"],
        ai_verdict=result["ai_verdict"],
        final_verdict=result["final_verdict"],
        confidence=result["confidence"],
        model=result["model"],
        approval_version=AI_APPROVAL_VERSION,
        prompt_version=PROMPT_VERSION,
        risk_reasons=result["risk_reasons"],
        ai_reasons=result["ai_reasons"],
        raw=result,
    )
    update_entry_latency(
        signal["signal_id"],
        ai_finished_at_ms=ai_finished_at_ms,
    )

    if result["final_verdict"] == "APPROVE":
        try:
            from .paper_trading import process_approved_signal

            result["stage13_handoff"] = process_approved_signal(
                str(signal["signal_id"])
            )
        except Exception as exc:
            result["stage13_handoff"] = {
                "status": "ERROR",
                "error_type": type(exc).__name__,
                "error": str(exc)[:300],
            }

    return result


def process_pending_approvals() -> dict[str, Any]:
    """Review fresh unreviewed signals; never overlaps with itself.

    Entry AI is a RUN-only subsystem. PAUSE_ENTRIES and EXIT_ONLY keep
    scanner/research visibility and position lifecycle alive, but must not
    spend entry-review tokens or create fresh approvals.
    """
    control = get_control_state()
    if not control.get("entries_enabled"):
        return {
            "approval_version": AI_APPROVAL_VERSION,
            "status": "PAUSED",
            "control_mode": control.get("mode"),
            "processed": 0,
            "approve": 0,
            "veto": 0,
            "watch": 0,
        }

    if not _processing_lock.acquire(blocking=False):
        return {
            "approval_version": AI_APPROVAL_VERSION,
            "status": "BUSY",
            "processed": 0,
        }

    try:
        # Re-check after acquiring the lock so a mode transition that happened
        # while another Stage 11 batch was finishing cannot start a new batch.
        control = get_control_state()
        if not control.get("entries_enabled"):
            return {
                "approval_version": AI_APPROVAL_VERSION,
                "status": "PAUSED",
                "control_mode": control.get("mode"),
                "processed": 0,
                "approve": 0,
                "veto": 0,
                "watch": 0,
            }

        signals = get_pending_entry_signals(
            max_age_ms=_max_age_ms(),
            limit=_max_per_scan(),
        )

        # Do not replay candidates accumulated while entries were paused.
        # A RUN transition is a clean entry epoch: only signals born at/after
        # that transition may reach Stage 11.
        run_started_at_ms = int(control.get("updated_at_ms") or 0)
        signals = [
            signal
            for signal in signals
            if int(signal.get("signal_time_ms") or 0) >= run_started_at_ms
        ]
        if not signals:
            return {
                "approval_version": AI_APPROVAL_VERSION,
                "status": "IDLE",
                "processed": 0,
                "approve": 0,
                "veto": 0,
                "watch": 0,
            }

        queued_at_ms = int(time.time() * 1000)
        for signal in signals:
            update_entry_latency(
                signal["signal_id"],
                ai_queued_at_ms=queued_at_ms,
            )

        results: list[dict[str, Any]] = []
        targets = [_target_for_index(index) for index in range(len(signals))]
        with ThreadPoolExecutor(max_workers=_workers()) as pool:
            futures = [
                pool.submit(review_signal, signal, target=target)
                for signal, target in zip(signals, targets)
            ]
            for future in as_completed(futures):
                results.append(future.result())

        counts = {"APPROVE": 0, "VETO": 0, "WATCH": 0}
        for result in results:
            counts[result["final_verdict"]] += 1

        return {
            "approval_version": AI_APPROVAL_VERSION,
            "status": "COMPLETE",
            "processed": len(results),
            "approve": counts["APPROVE"],
            "veto": counts["VETO"],
            "watch": counts["WATCH"],
            "results": results,
        }
    finally:
        _processing_lock.release()


def start_pending_approval_worker() -> bool:
    """Start one background Stage 11 pass without blocking the scanner."""
    control = get_control_state()
    if not control.get("entries_enabled"):
        return False
    if _processing_lock.locked():
        return False

    def _runner() -> None:
        try:
            result = process_pending_approvals()
            results = result.get("results") or []
            risk_fail = sum(
                1 for item in results
                if item.get("risk_verdict") == "FAIL"
            )
            ai_error = sum(
                1 for item in results
                if item.get("ai_verdict") == "ERROR"
            )
            provider_blocked = sum(
                1 for item in results
                if item.get("ai_verdict") == "PROVIDER_BLOCKED"
            )
            sample_issue = next(
                (
                    (item.get("risk_reasons") or item.get("ai_reasons") or [None])[0]
                    for item in results
                    if item.get("final_verdict") != "APPROVE"
                ),
                None,
            )
            sample_error = next(
                (
                    item.get("ai") or {}
                    for item in results
                    if item.get("ai_verdict") == "ERROR"
                ),
                {},
            )
            fallback_used = sum(
                1 for item in results
                if (item.get("fast_pool") or {}).get("fallback_used")
            )
            lane_counts: dict[str, int] = {}
            for item in results:
                pool_info = item.get("fast_pool") or {}
                primary = pool_info.get("primary_target") or {}
                if isinstance(primary, dict):
                    lane = f"{primary.get('provider')}:{primary.get('model')}"
                else:
                    lane = str(primary)
                lane_counts[lane] = lane_counts.get(lane, 0) + 1
            print(
                "Stage 11 approvals: "
                f"version={AI_APPROVAL_VERSION} "
                f"pool={_fast_pool_targets()} "
                f"workers={_workers()} "
                f"status={result.get('status')} "
                f"processed={result.get('processed', 0)} "
                f"approve={result.get('approve', 0)} "
                f"veto={result.get('veto', 0)} "
                f"watch={result.get('watch', 0)} "
                f"risk_fail={risk_fail} "
                f"ai_error={ai_error} "
                f"fallback_used={fallback_used} "
                f"lanes={lane_counts} "
                f"sample_issue={sample_issue} "
                f"error_type={sample_error.get('error_type')} "
                f"error={str(sample_error.get('error') or '')[:180]}",
                flush=True,
            )
        except Exception as exc:
            print(f"Stage 11 approval worker error: {exc}", flush=True)

    threading.Thread(
        target=_runner,
        name="stage11-entry-approval",
        daemon=True,
    ).start()
    return True
