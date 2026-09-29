from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

import requests


_VALID_AI_VERDICTS = {"APPROVE", "VETO", "WATCH"}
_provider_rate_locks: dict[str, threading.Lock] = {}
_provider_rate_locks_guard = threading.Lock()
_last_provider_call_monotonic_by_provider: dict[str, float] = {}
_blocked_until_by_target: dict[str, float] = {}


class AIProviderQuotaError(RuntimeError):
    pass


def provider_name() -> str:
    return os.environ.get("AI_PROVIDER", "clario").strip().lower()


def primary_provider() -> str:
    return os.environ.get("AI_PRIMARY_PROVIDER", provider_name()).strip().lower()


def active_model() -> str:
    return os.environ.get(
        "AI_PRIMARY_MODEL",
        os.environ.get("CLARIO_MODEL", "gemini-3.7-flash"),
    ).strip()


def _timeout_seconds() -> float:
    return max(
        5.0,
        min(float(os.environ.get("AI_APPROVAL_TIMEOUT_SECONDS", "30")), 90.0),
    )


def _min_call_interval_seconds(provider: str | None = None) -> float:
    provider_key = (provider or "").strip().upper()
    provider_specific = (
        os.environ.get(f"AI_APPROVAL_MIN_CALL_INTERVAL_SECONDS_{provider_key}")
        if provider_key
        else None
    )
    raw = (
        provider_specific
        if provider_specific is not None
        else os.environ.get("AI_APPROVAL_MIN_CALL_INTERVAL_SECONDS", "2")
    )
    return max(0.0, min(float(raw), 15.0))


def _provider_rate_lock(provider: str) -> threading.Lock:
    key = provider.strip().lower()
    with _provider_rate_locks_guard:
        lock = _provider_rate_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _provider_rate_locks[key] = lock
        return lock


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
    provider: str,
    headers: dict[str, str],
    body: dict[str, Any],
) -> requests.Response:
    """Space request starts per provider without serializing in-flight calls."""
    provider_key = provider.strip().lower()
    lock = _provider_rate_lock(provider_key)

    with lock:
        now = time.monotonic()
        last = _last_provider_call_monotonic_by_provider.get(provider_key, 0.0)
        wait = _min_call_interval_seconds(provider_key) - (now - last)
        if wait > 0:
            time.sleep(wait)
        _last_provider_call_monotonic_by_provider[provider_key] = time.monotonic()

    return requests.post(
        url,
        headers=headers,
        json=body,
        timeout=_timeout_seconds(),
    )


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
            "credit balance",
        )
    )


def _raise_for_quota(
    response: requests.Response,
    *,
    provider: str,
    model: str,
) -> None:
    if _is_quota_exhausted(response):
        key = f"{provider}:{model}"
        _blocked_until_by_target[key] = time.monotonic() + 900.0
        raise AIProviderQuotaError(
            f"{provider} quota/credits exhausted for model={model} (HTTP 429)"
        )


def _reasoning_effort_for(provider: str, model: str) -> str | None:
    if provider != "clario" or not model.startswith("gemini-"):
        return None
    value = os.environ.get(
        "CLARIO_REASONING_EFFORT",
        "medium",
    ).strip().lower()
    return value if value in {"low", "medium", "high"} else "medium"


def _provider_config(provider: str) -> tuple[str, str, list[str]]:
    if provider == "clario":
        api_key = os.environ.get("CLARIO_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("CLARIO_API_KEY is not configured")
        base_urls = [
            os.environ.get(
                "CLARIO_BASE_URL",
                "https://clariohub.id/v1",
            ).rstrip("/"),
            os.environ.get(
                "CLARIO_FALLBACK_BASE_URL",
                "https://api-direct.clariohub.id/v1",
            ).rstrip("/"),
        ]
        return api_key, "ClarioHub", base_urls

    if provider == "thirty":
        api_key = os.environ.get("THIRTY_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("THIRTY_API_KEY is not configured")
        base_url = os.environ.get(
            "THIRTY_BASE_URL",
            "https://api.thirtystore.com/v1",
        ).rstrip("/")
        return api_key, "ThirtyStore", [base_url]

    raise RuntimeError(f"Unsupported AI provider: {provider}")


def call_model_review(
    payload: dict[str, Any],
    *,
    system_prompt: str,
    model: str,
    provider: str | None = None,
) -> dict[str, Any]:
    provider = (provider or primary_provider()).strip().lower()
    target_key = f"{provider}:{model}"
    blocked_until = _blocked_until_by_target.get(target_key, 0.0)
    if time.monotonic() < blocked_until:
        raise AIProviderQuotaError(
            f"AI provider quota circuit is open for {target_key}"
        )

    api_key, provider_label, base_urls = _provider_config(provider)

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

    reasoning_effort = _reasoning_effort_for(provider, model)
    if reasoning_effort:
        body["reasoning_effort"] = reasoning_effort

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_error: Exception | None = None
    for index, base_url in enumerate(base_urls):
        try:
            response = _rate_limited_post(
                f"{base_url}/chat/completions",
                provider=provider,
                headers=headers,
                body=body,
            )
        except requests.RequestException as exc:
            last_error = exc
            if index < len(base_urls) - 1:
                continue
            raise

        _raise_for_quota(
            response,
            provider=provider,
            model=model,
        )

        if response.status_code == 403 and index < len(base_urls) - 1:
            last_error = RuntimeError(
                f"{provider_label} endpoint returned HTTP 403; trying fallback"
            )
            continue

        if response.status_code >= 500 and index < len(base_urls) - 1:
            last_error = RuntimeError(
                f"{provider_label} endpoint returned HTTP {response.status_code}; "
                "trying fallback"
            )
            continue

        if response.status_code == 429:
            last_error = RuntimeError(
                f"{provider_label} rate limited model={model} (HTTP 429): "
                + response.text[:180].replace("\n", " ")
            )
            time.sleep(4.0)
            continue

        response.raise_for_status()
        result = parse_provider_response(response.json())
        result["model"] = model
        result["provider"] = provider
        return result

    raise last_error or RuntimeError(
        f"{provider_label} review failed for model={model}"
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
        provider=primary_provider(),
    )
