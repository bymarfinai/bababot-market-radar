from __future__ import annotations

import time
from typing import Any

from .ai_provider import call_model_review
from .persistence import save_model_review


STAGE11B_VERSION = "stage11b-v3-failover-only"


def run_stage11b_failover(
    *,
    signal_id: str,
    reviewed_at_ms: int,
    payload: dict[str, Any],
    system_prompt: str,
    failed_target: tuple[str, str],
    alternate_target: tuple[str, str] | None,
) -> dict[str, Any]:
    """Attempt exactly one alternate fast provider after Stage 11 primary failure.

    Stage 11B is resilience only. It never runs on a successful Stage 11
    review, never votes across multiple models, and never reverses direction.
    If the alternate target is unavailable or fails, the result is fail-closed
    VETO.
    """

    failed_provider, failed_model = failed_target
    base = {
        "version": STAGE11B_VERSION,
        "mode": "FAILOVER_ONLY",
        "failed_target": {
            "provider": failed_provider,
            "model": failed_model,
        },
    }

    if alternate_target is None:
        return {
            **base,
            "status": "NO_ALTERNATE",
            "final_verdict": "VETO",
            "fallback_reason": "no_alternate_fast_lane",
            "alternate": None,
        }

    provider, model = alternate_target
    started = time.monotonic()
    try:
        result = call_model_review(
            payload,
            system_prompt=system_prompt,
            provider=provider,
            model=model,
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        review = {
            "status": "OK",
            "provider": provider,
            "model": model,
            "latency_ms": latency_ms,
            **result,
        }
        save_model_review(
            signal_id=signal_id,
            reviewed_at_ms=reviewed_at_ms,
            role="FAST_FAILOVER",
            model=f"{provider}:{model}",
            verdict=result["verdict"],
            confidence=result["confidence"],
            reasons=result.get("reasons") or [],
            risk_flags=result.get("risk_flags") or [],
            latency_ms=latency_ms,
            status="OK",
            error_text=None,
            raw=review,
        )
        return {
            **base,
            "status": "OK",
            "final_verdict": str(result["verdict"]),
            "fallback_reason": "alternate_fast_lane_succeeded",
            "alternate": review,
        }
    except Exception as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        error_text = f"{type(exc).__name__}: {str(exc)[:300]}"
        save_model_review(
            signal_id=signal_id,
            reviewed_at_ms=reviewed_at_ms,
            role="FAST_FAILOVER",
            model=f"{provider}:{model}",
            verdict=None,
            confidence=None,
            reasons=[],
            risk_flags=[],
            latency_ms=latency_ms,
            status="ERROR",
            error_text=error_text,
            raw=None,
        )
        return {
            **base,
            "status": "ERROR",
            "final_verdict": "VETO",
            "fallback_reason": "alternate_fast_lane_failed",
            "alternate": {
                "status": "ERROR",
                "provider": provider,
                "model": model,
                "latency_ms": latency_ms,
                "error_type": type(exc).__name__,
                "error": str(exc)[:500],
            },
        }
