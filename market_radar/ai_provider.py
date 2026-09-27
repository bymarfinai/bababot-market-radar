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
_blocked_until_by_model: dict[str, float] = {}


class AIProviderQuotaError(RuntimeError):
    pass


def provider_name() -> str:
    return os.environ.get("AI_PROVIDER", "clario").strip().lower()


def active_model() -> str:
    return os.environ.get("CLARIO_MODEL", "gemini-3.7-flash").strip()


def shadow_model() -> str:
    return os.environ.get(
        "CLARIO_SHADOW_MODEL",
        "deepseek-v4.1-flash",
    ).strip()


def escalation_model() -> str:
    return os.environ.get(
        "CLARIO_ESCALATION_MODEL",
        "gpt-5.6-sol",
    ).strip()


def tiebreaker_model() -> str:
    return os.environ.get(
        "CLARIO_TIEBREAKER_MODEL",
        "opus-5",
    ).strip()


def _timeout_seconds() -> float:
    return max(
        5.0,
        min(float(os.environ.get("AI_APPROVAL_TIMEOUT_SECONDS", "30")), 90.0),
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


def _raise_for_quota(
    response: requests.Response,
    *,
    model: str,
) -> None:
    if _is_quota_exhausted(response):
        _blocked_until_by_model[model] = time.monotonic() + 900.0
        raise AIProviderQuotaError(
            f"ClarioHub quota/credits exhausted for model={model} (HTTP 429)"
        )


def _reasoning_effort_for(model: str) -> str | None:
    if not model.startswith("gemini-"):
        return None
    value = os.environ.get(
        "CLARIO_REASONING_EFFORT",
        "medium",
    ).strip().lower()
    return value if value in {"low", "medium", "high"} else "medium"


def call_model_review(
    payload: dict[str, Any],
    *,
    system_prompt: str,
    model: str,
) -> dict[str, Any]:
    if provider_name() != "clario":
        raise RuntimeError(
            f"Unsupported AI_PROVIDER: {provider_name()}; Stage 11B requires clario"
        )

    blocked_until = _blocked_until_by_model.get(model, 0.0)
    if time.monotonic() < blocked_until:
        raise AIProviderQuotaError(
            f"AI provider quota circuit is open for model={model}"
        )

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

    reasoning_effort = _reasoning_effort_for(model)
    if reasoning_effort:
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
        _raise_for_quota(response, model=model)

        if response.status_code == 403 and index == 0:
            last_error = RuntimeError(
                "ClarioHub primary endpoint returned HTTP 403; trying fallback"
            )
            continue

        if response.status_code == 429:
            last_error = RuntimeError(
                f"ClarioHub rate limited model={model} (HTTP 429): "
                + response.text[:180].replace("\n", " ")
            )
            if index == 0:
                time.sleep(4.0)
                continue

        response.raise_for_status()
        result = parse_provider_response(response.json())
        result["model"] = model
        return result

    raise last_error or RuntimeError(
        f"ClarioHub review failed for model={model}"
    )


def call_entry_review(
    payload: dict[str, Any],
    *,
    system_prompt: str,
) -> dict[str, Any]:
    return call_model_review(
        payload,
        system_prompt=system_prompt,
        model=active_model(),
    )
