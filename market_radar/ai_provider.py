from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

import requests


_VALID_AI_VERDICTS = {"APPROVE", "VETO", "WATCH"}
_provider_rate_lock = threading.Lock()
_last_provider_call_monotonic = 0.0
_provider_blocked_until_monotonic = 0.0


class AIProviderQuotaError(RuntimeError):
    pass


def provider_name() -> str:
    return os.environ.get("AI_PROVIDER", "clario").strip().lower()


def active_model() -> str:
    if provider_name() == "clario":
        return os.environ.get("CLARIO_MODEL", "gemini-3.7-flash").strip()
    return os.environ.get("MINIMAX_MODEL", "MiniMax-M2.7").strip()


def _timeout_seconds() -> float:
    return max(
        5.0,
        min(float(os.environ.get("AI_APPROVAL_TIMEOUT_SECONDS", "30")), 60.0),
    )


def _min_call_interval_seconds() -> float:
    return max(
        0.0,
        min(
            float(os.environ.get("AI_APPROVAL_MIN_CALL_INTERVAL_SECONDS", "2")),
            15.0,
        ),
    )


def _normalize_json_text(text: str) -> dict[str, Any]:
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


def parse_provider_response(data: dict[str, Any]) -> dict[str, Any]:
    """Accept OpenAI-compatible and Anthropic-compatible response shapes."""
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if isinstance(content, list):
            text = "".join(
                str(part.get("text") or "")
                for part in content
                if isinstance(part, dict)
            )
        else:
            text = str(content or "")
        return _normalize_json_text(text)

    text = ""
    for block in data.get("content", []):
        if isinstance(block, dict) and block.get("type") == "text":
            text += str(block.get("text") or "")
    if text:
        return _normalize_json_text(text)

    raise ValueError("Unsupported AI provider response shape")


def _rate_limited_post(
    url: str,
    *,
    headers: dict[str, str],
    body: dict[str, Any],
) -> requests.Response:
    global _last_provider_call_monotonic

    with _provider_rate_lock:
        now = time.monotonic()
        wait = _min_call_interval_seconds() - (
            now - _last_provider_call_monotonic
        )
        if wait > 0:
            time.sleep(wait)

        response = requests.post(
            url,
            headers=headers,
            json=body,
            timeout=_timeout_seconds(),
        )
        _last_provider_call_monotonic = time.monotonic()
        return response


def _is_quota_exhausted(response: requests.Response) -> bool:
    if response.status_code != 429:
        return False
    body = response.text[:600].lower()
    return any(
        marker in body
        for marker in (
            "usage limit reached",
            "purchase credits",
            "upgrade your token plan",
            "quota exceeded",
            "insufficient credits",
            "insufficient_credit",
        )
    )


def _raise_for_quota(response: requests.Response, provider: str) -> None:
    global _provider_blocked_until_monotonic
    if _is_quota_exhausted(response):
        _provider_blocked_until_monotonic = time.monotonic() + 900.0
        raise AIProviderQuotaError(
            f"{provider} provider token plan/credits exhausted (HTTP 429)"
        )


def _call_clario(
    payload: dict[str, Any],
    *,
    system_prompt: str,
) -> dict[str, Any]:
    api_key = os.environ.get("CLARIO_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("CLARIO_API_KEY is not configured")

    base_urls = [
        os.environ.get("CLARIO_BASE_URL", "https://clariohub.id/v1").rstrip("/"),
        os.environ.get(
            "CLARIO_FALLBACK_BASE_URL",
            "https://api-direct.clariohub.id/v1",
        ).rstrip("/"),
    ]
    model = active_model()
    body: dict[str, Any] = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 650,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    payload,
                    separators=(",", ":"),
                    allow_nan=False,
                ),
            },
        ],
    }

    reasoning_effort = os.environ.get(
        "CLARIO_REASONING_EFFORT",
        "medium",
    ).strip().lower()
    if model.startswith("gemini-") and reasoning_effort in {"low", "medium", "high"}:
        body["reasoning_effort"] = reasoning_effort

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_error: Exception | None = None
    for index, base_url in enumerate(base_urls):
        response = _rate_limited_post(
            f"{base_url}/chat/completions",
            headers=headers,
            body=body,
        )
        _raise_for_quota(response, "ClarioHub")

        if response.status_code == 403 and index == 0:
            last_error = RuntimeError(
                "ClarioHub primary endpoint returned HTTP 403; trying fallback"
            )
            continue

        if response.status_code == 429:
            last_error = RuntimeError(
                "ClarioHub rate limited (HTTP 429): "
                + response.text[:180].replace("\n", " ")
            )
            time.sleep(4.0)
            continue

        response.raise_for_status()
        return parse_provider_response(response.json())

    raise last_error or RuntimeError("ClarioHub review failed")


def _call_minimax(
    payload: dict[str, Any],
    *,
    system_prompt: str,
) -> dict[str, Any]:
    api_key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("MINIMAX_API_KEY is not configured")

    base_url = os.environ.get(
        "MINIMAX_BASE_URL",
        "https://api.minimax.io/anthropic",
    ).rstrip("/")
    body = {
        "model": active_model(),
        "max_tokens": 650,
        "temperature": 0.1,
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": json.dumps(
                    payload,
                    separators=(",", ":"),
                    allow_nan=False,
                ),
            }
        ],
    }
    response = _rate_limited_post(
        f"{base_url}/v1/messages",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        body=body,
    )
    _raise_for_quota(response, "MiniMax")
    response.raise_for_status()
    return parse_provider_response(response.json())


def call_entry_review(
    payload: dict[str, Any],
    *,
    system_prompt: str,
) -> dict[str, Any]:
    global _provider_blocked_until_monotonic

    if time.monotonic() < _provider_blocked_until_monotonic:
        raise AIProviderQuotaError("AI provider quota circuit is open")

    provider = provider_name()
    if provider == "clario":
        return _call_clario(payload, system_prompt=system_prompt)
    if provider == "minimax":
        return _call_minimax(payload, system_prompt=system_prompt)
    raise RuntimeError(f"Unsupported AI_PROVIDER: {provider}")
