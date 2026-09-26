from __future__ import annotations

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests

from .persistence import get_pending_entry_signals, save_entry_approval


AI_APPROVAL_VERSION = "stage11-v1"
RISK_GATE_VERSION = "stage11-risk-v1"
PROMPT_VERSION = "stage11-entry-review-v1"

MINIMAX_MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M2.7")
MINIMAX_BASE_URL = os.environ.get(
    "MINIMAX_BASE_URL",
    "https://api.minimax.io/anthropic",
).rstrip("/")

_VALID_AI_VERDICTS = {"APPROVE", "VETO", "WATCH"}
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
    return max(1, min(int(os.environ.get("AI_APPROVAL_MAX_PER_SCAN", "12")), 50))


def _workers() -> int:
    return max(1, min(int(os.environ.get("AI_APPROVAL_WORKERS", "4")), 8))


def _timeout_seconds() -> float:
    return max(5.0, min(float(os.environ.get("AI_APPROVAL_TIMEOUT_SECONDS", "30")), 60.0))


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
    text = ""
    for block in data.get("content", []):
        if isinstance(block, dict) and block.get("type") == "text":
            text += str(block.get("text") or "")
    text = text.strip()
    fence = chr(96) * 3
    if text.startswith(fence):
        text = text.split("\n", 1)[1].rsplit(fence, 1)[0].strip()

    parsed = json.loads(text)
    verdict = str(parsed.get("verdict") or "").upper()
    if verdict not in _VALID_AI_VERDICTS:
        raise ValueError("AI verdict must be APPROVE, VETO, or WATCH")

    confidence = max(0.0, min(float(parsed.get("confidence", 0.0)), 1.0))
    reasons = [
        str(item)[:300]
        for item in (parsed.get("reasons") or [])
        if str(item).strip()
    ][:8]
    risk_flags = [
        str(item)[:200]
        for item in (parsed.get("risk_flags") or [])
        if str(item).strip()
    ][:8]

    return {
        "verdict": verdict,
        "confidence": confidence,
        "reasons": reasons,
        "risk_flags": risk_flags,
        "raw_text": text,
    }


def call_ai_entry_review(signal: dict[str, Any]) -> dict[str, Any]:
    api_key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not approval_enabled():
        raise RuntimeError("AI_APPROVAL_ENABLED is false")
    if not api_key:
        raise RuntimeError("MINIMAX_API_KEY is not configured")

    payload = _signal_for_ai(signal)
    response = requests.post(
        f"{MINIMAX_BASE_URL}/v1/messages",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": MINIMAX_MODEL,
            "max_tokens": 650,
            "temperature": 0.1,
            "system": SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(payload, separators=(",", ":"), allow_nan=False),
                }
            ],
        },
        timeout=_timeout_seconds(),
    )
    response.raise_for_status()
    return _parse_ai_response(response.json())


def review_signal(
    signal: dict[str, Any],
    *,
    now_ms: int | None = None,
) -> dict[str, Any]:
    reviewed_at_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    risk = evaluate_entry_risk(signal, now_ms=reviewed_at_ms)

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
        }
    else:
        started = time.monotonic()
        try:
            ai = call_ai_entry_review(signal)
            result = {
                "signal_id": signal["signal_id"],
                "risk_verdict": "PASS",
                "ai_verdict": ai["verdict"],
                "final_verdict": ai["verdict"],
                "confidence": ai["confidence"],
                "model": MINIMAX_MODEL,
                "risk_reasons": [],
                "ai_reasons": ai["reasons"],
                "risk": risk,
                "ai": ai,
                "ai_latency_ms": int((time.monotonic() - started) * 1000),
            }
        except Exception as exc:
            result = {
                "signal_id": signal["signal_id"],
                "risk_verdict": "PASS",
                "ai_verdict": "ERROR",
                "final_verdict": "VETO",
                "confidence": None,
                "model": MINIMAX_MODEL,
                "risk_reasons": [],
                "ai_reasons": ["ai_review_failed"],
                "risk": risk,
                "ai": {
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:500],
                },
                "ai_latency_ms": int((time.monotonic() - started) * 1000),
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
    return result


def process_pending_approvals() -> dict[str, Any]:
    """Review fresh unreviewed signals; never overlaps with itself."""
    if not _processing_lock.acquire(blocking=False):
        return {
            "approval_version": AI_APPROVAL_VERSION,
            "status": "BUSY",
            "processed": 0,
        }

    try:
        signals = get_pending_entry_signals(
            max_age_ms=_max_age_ms(),
            limit=_max_per_scan(),
        )
        if not signals:
            return {
                "approval_version": AI_APPROVAL_VERSION,
                "status": "IDLE",
                "processed": 0,
                "approve": 0,
                "veto": 0,
                "watch": 0,
            }

        results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=_workers()) as pool:
            futures = [pool.submit(review_signal, signal) for signal in signals]
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
    if _processing_lock.locked():
        return False

    def _runner() -> None:
        try:
            result = process_pending_approvals()
            print(
                "Stage 11 approvals: "
                f"status={result.get('status')} "
                f"processed={result.get('processed', 0)} "
                f"approve={result.get('approve', 0)} "
                f"veto={result.get('veto', 0)} "
                f"watch={result.get('watch', 0)}",
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
