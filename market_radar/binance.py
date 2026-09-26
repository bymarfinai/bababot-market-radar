from __future__ import annotations

import threading
import time
from typing import Any

import requests


BINANCE_FUTURES_BASE = "https://fapi.binance.com"


class BinancePublicClient:
    """Small public USD-M Futures REST client.

    No Binance API key is required for Stage 1.
    A requests.Session is kept per thread so concurrent symbol scans do not
    share a non-thread-safe Session object.
    """

    def __init__(self, timeout: float = 8.0, retries: int = 2) -> None:
        self.timeout = timeout
        self.retries = retries
        self._local = threading.local()

    def _session(self) -> requests.Session:
        if not hasattr(self._local, "session"):
            session = requests.Session()
            session.headers.update({"User-Agent": "BabaBot-Market-Radar/0.1-stage1"})
            self._local.session = session
        return self._local.session

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{BINANCE_FUTURES_BASE}{path}"
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self._session().get(url, params=params, timeout=self.timeout)
                if response.status_code in (418, 429):
                    retry_after = response.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after else min(4.0, 0.75 * (2**attempt))
                    time.sleep(max(0.25, wait))
                    response.raise_for_status()
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.35 * (attempt + 1))
        raise RuntimeError(f"Binance GET {path} failed: {last_error}")

    def server_time_ms(self) -> int:
        payload = self.get("/fapi/v1/time")
        return int(payload["serverTime"])

    def exchange_info(self) -> dict[str, Any]:
        return self.get("/fapi/v1/exchangeInfo")

    def ticker_24h(self) -> list[dict[str, Any]]:
        return self.get("/fapi/v1/ticker/24hr")

    def klines(self, symbol: str, interval: str = "5m", limit: int = 3) -> list[list[Any]]:
        return self.get(
            "/fapi/v1/klines",
            {"symbol": symbol, "interval": interval, "limit": limit},
        )
