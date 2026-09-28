from __future__ import annotations

import os
import threading
import time
from collections import Counter
from typing import Any

from .ai_provider import (
    call_model_review,
    escalation_model,
    escalation_provider,
    shadow_model,
    shadow_provider,
    tiebreaker_model,
    tiebreaker_provider,
)
from .persistence import save_model_review


STAGE11B_VERSION = "stage11b-v2-primary-fallback"

_window_lock = threading.Lock()
_window_key = -1
_escalations_used = 0
_tiebreakers_used = 0


def _threshold() -> float:
    return max(
        0.0,
        min(float(os.environ.get("AI_ESCALATION_CONFIDENCE_THRESHOLD", "0.70")), 1.0),
    )


def _escalation_cap() -> int:
    return max(0, min(int(os.environ.get("AI_ESCALATION_MAX_PER_5M", "3")), 12))


def _tiebreaker_cap() -> int:
    return max(0, min(int(os.environ.get("AI_TIEBREAKER_MAX_PER_5M", "1")), 6))


def _take_slot(kind: str) -> bool:
    global _window_key, _escalations_used, _tiebreakers_used
    key = int(time.time() // 300)
    with _window_lock:
        if key != _window_key:
            _window_key = key
            _escalations_used = 0
            _tiebreakers_used = 0
        if kind == "escalation":
            if _escalations_used >= _escalation_cap():
                return False
            _escalations_used += 1
            return True
        if _tiebreakers_used >= _tiebreaker_cap():
            return False
        _tiebreakers_used += 1
        return True


def _review_model(
    *,
    role: str,
    provider: str,
    model: str,
    signal_id: str,
    reviewed_at_ms: int,
    payload: dict[str, Any],
    system_prompt: str,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        result = call_model_review(
            payload,
            system_prompt=system_prompt,
            model=model,
            provider=provider,
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        save_model_review(
            signal_id=signal_id,
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
            raw=result,
        )
        return {"status": "OK", "latency_ms": latency_ms, **result}
    except Exception as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        save_model_review(
            signal_id=signal_id,
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
            "model": model,
            "provider": provider,
            "error_type": type(exc).__name__,
            "error": str(exc)[:300],
        }


def run_primary_fallback(
    *,
    signal_id: str,
    reviewed_at_ms: int,
    payload: dict[str, Any],
    system_prompt: str,
    primary_error: dict[str, Any],
) -> dict[str, Any]:
    """Fail-safe degraded consensus when the normal primary model is unavailable."""
    if not _take_slot("escalation"):
        return {
            "version": STAGE11B_VERSION,
            "mode": "DEGRADED_PRIMARY_FALLBACK",
            "final_verdict": "VETO",
            "fallback_reason": "quota_guard_cap",
            "primary_error": primary_error,
            "shadow": None,
            "validator": None,
        }

    shadow = _review_model(
        role="FALLBACK_PRIMARY",
        provider=shadow_provider(),
        model=shadow_model(),
        signal_id=signal_id,
        reviewed_at_ms=reviewed_at_ms,
        payload=payload,
        system_prompt=system_prompt,
    )
    validator = _review_model(
        role="FALLBACK_VALIDATOR",
        provider=tiebreaker_provider(),
        model=tiebreaker_model(),
        signal_id=signal_id,
        reviewed_at_ms=reviewed_at_ms,
        payload=payload,
        system_prompt=system_prompt,
    )

    shadow_ok = shadow.get("status") == "OK"
    validator_ok = validator.get("status") == "OK"
    shadow_verdict = str(shadow.get("verdict") or "") if shadow_ok else ""
    validator_verdict = str(validator.get("verdict") or "") if validator_ok else ""

    if not shadow_ok and not validator_ok:
        final = "VETO"
        reason = "both_fallback_models_failed"
    elif shadow_verdict == "VETO" or validator_verdict == "VETO":
        final = "VETO"
        reason = "fallback_veto_present"
    elif (
        shadow_ok
        and validator_ok
        and shadow_verdict == "APPROVE"
        and validator_verdict == "APPROVE"
    ):
        final = "APPROVE"
        reason = "dual_approve"
    else:
        final = "WATCH"
        reason = "no_dual_approve"

    return {
        "version": STAGE11B_VERSION,
        "mode": "DEGRADED_PRIMARY_FALLBACK",
        "final_verdict": final,
        "fallback_reason": reason,
        "primary_error": primary_error,
        "shadow": shadow,
        "validator": validator,
    }


def run_stage11b(
    *,
    signal_id: str,
    reviewed_at_ms: int,
    payload: dict[str, Any],
    system_prompt: str,
    primary: dict[str, Any],
) -> dict[str, Any]:
    """Run shadow review and guarded escalation/tiebreak supervision."""
    save_model_review(
        signal_id=signal_id,
        reviewed_at_ms=reviewed_at_ms,
        role="PRIMARY",
        model=(
            f"{primary.get('provider') or 'unknown'}:"
            f"{primary.get('model') or 'unknown'}"
        ),
        verdict=primary.get("verdict"),
        confidence=primary.get("confidence"),
        reasons=primary.get("reasons") or [],
        risk_flags=primary.get("risk_flags") or [],
        latency_ms=primary.get("latency_ms"),
        status="OK",
        error_text=None,
        raw=primary,
    )

    shadow = _review_model(
        role="SHADOW",
        provider=shadow_provider(),
        model=shadow_model(),
        signal_id=signal_id,
        reviewed_at_ms=reviewed_at_ms,
        payload=payload,
        system_prompt=system_prompt,
    )

    primary_verdict = str(primary.get("verdict") or "WATCH")
    primary_conf = float(primary.get("confidence") or 0.0)
    shadow_verdict = shadow.get("verdict") if shadow.get("status") == "OK" else None

    escalation_needed = (
        primary_verdict == "WATCH"
        or primary_conf < _threshold()
        or (shadow_verdict is not None and shadow_verdict != primary_verdict)
    )

    if not escalation_needed:
        return {
            "version": STAGE11B_VERSION,
            "final_verdict": primary_verdict,
            "escalated": False,
            "primary": primary,
            "shadow": shadow,
            "gpt": None,
            "opus": None,
        }

    if not _take_slot("escalation"):
        return {
            "version": STAGE11B_VERSION,
            "final_verdict": "VETO" if primary_verdict == "VETO" else "WATCH",
            "escalated": False,
            "escalation_reason": "quota_guard_cap",
            "primary": primary,
            "shadow": shadow,
            "gpt": None,
            "opus": None,
        }

    gpt = _review_model(
        role="ESCALATION",
        provider=escalation_provider(),
        model=escalation_model(),
        signal_id=signal_id,
        reviewed_at_ms=reviewed_at_ms,
        payload=payload,
        system_prompt=system_prompt,
    )

    if gpt.get("status") != "OK":
        return {
            "version": STAGE11B_VERSION,
            "final_verdict": "VETO" if primary_verdict == "VETO" else "WATCH",
            "escalated": True,
            "primary": primary,
            "shadow": shadow,
            "gpt": gpt,
            "opus": None,
        }

    votes = [primary_verdict, str(gpt["verdict"])]
    if shadow_verdict is not None:
        votes.append(str(shadow_verdict))

    counts = Counter(votes)
    majority = counts.most_common(1)[0]
    has_majority = majority[1] >= 2
    candidate = majority[0] if has_majority else None

    need_opus = (
        candidate is None
        or (candidate == "APPROVE" and primary_verdict == "VETO")
    )

    if not need_opus:
        return {
            "version": STAGE11B_VERSION,
            "final_verdict": candidate,
            "escalated": True,
            "primary": primary,
            "shadow": shadow,
            "gpt": gpt,
            "opus": None,
        }

    same_tiebreak_target = (
        escalation_provider() == tiebreaker_provider()
        and escalation_model() == tiebreaker_model()
    )
    if same_tiebreak_target:
        tiebreaker = gpt
        return {
            "version": STAGE11B_VERSION,
            "final_verdict": str(gpt["verdict"]),
            "escalated": True,
            "tiebreaker_reused_escalation": True,
            "primary": primary,
            "shadow": shadow,
            "gpt": gpt,
            "opus": tiebreaker,
        }

    if not _take_slot("tiebreaker"):
        return {
            "version": STAGE11B_VERSION,
            "final_verdict": "VETO" if primary_verdict == "VETO" else "WATCH",
            "escalated": True,
            "tiebreaker_reason": "quota_guard_cap",
            "primary": primary,
            "shadow": shadow,
            "gpt": gpt,
            "opus": None,
        }

    opus = _review_model(
        role="TIEBREAKER",
        provider=tiebreaker_provider(),
        model=tiebreaker_model(),
        signal_id=signal_id,
        reviewed_at_ms=reviewed_at_ms,
        payload=payload,
        system_prompt=system_prompt,
    )

    if opus.get("status") != "OK":
        final = "VETO" if primary_verdict == "VETO" else "WATCH"
    else:
        final = str(opus["verdict"])
        if primary_verdict == "VETO" and final == "APPROVE":
            final = "APPROVE"

    return {
        "version": STAGE11B_VERSION,
        "final_verdict": final,
        "escalated": True,
        "primary": primary,
        "shadow": shadow,
        "gpt": gpt,
        "opus": opus,
    }
