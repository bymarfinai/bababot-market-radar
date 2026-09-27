from __future__ import annotations

import hashlib
import hmac
import os
import threading
import time
from decimal import Decimal, ROUND_DOWN
from typing import Any
from urllib.parse import urlencode

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

    def klines(
        self,
        symbol: str,
        interval: str = "5m",
        limit: int = 3,
    ) -> list[list[Any]]:
        return self.get(
            "/fapi/v1/klines",
            {"symbol": symbol, "interval": interval, "limit": limit},
        )

    def ticker_price(self, symbol: str) -> float:
        payload = self.get("/fapi/v1/ticker/price", {"symbol": symbol})
        return float(payload["price"])

    def depth(self, symbol: str, limit: int = 5) -> dict[str, Any]:
        return self.get(
            "/fapi/v1/depth",
            {"symbol": symbol.upper(), "limit": max(5, min(int(limit), 100))},
        )

    def open_interest_hist(
        self,
        symbol: str,
        period: str = "5m",
        limit: int = 7,
    ) -> list[dict[str, Any]]:
        return self.get(
            "/futures/data/openInterestHist",
            {"symbol": symbol, "period": period, "limit": limit},
        )

    def premium_index(self, symbol: str) -> dict[str, Any]:
        return self.get("/fapi/v1/premiumIndex", {"symbol": symbol})



class BinanceTradingClient(BinancePublicClient):
    """Authenticated USD-M Futures client for guarded Stage 15 execution."""

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
        timeout: float = 8.0,
        retries: int = 1,
    ) -> None:
        super().__init__(timeout=timeout, retries=retries)
        self.api_key = (api_key or os.environ.get("BINANCE_API_KEY") or "").strip()
        self.api_secret = (
            api_secret or os.environ.get("BINANCE_API_SECRET") or ""
        ).strip()
        if not self.api_key or not self.api_secret:
            raise RuntimeError("BINANCE_API_KEY / BINANCE_API_SECRET not configured")

    def _signed_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        payload = dict(params or {})
        payload.setdefault("recvWindow", 5000)
        payload["timestamp"] = self.server_time_ms()
        query = urlencode(payload, doseq=True)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        url = f"{BINANCE_FUTURES_BASE}{path}"
        headers = {"X-MBX-APIKEY": self.api_key}
        data = f"{query}&signature={signature}"

        response = self._session().request(
            method.upper(),
            url,
            headers=headers,
            data=data if method.upper() in {"POST", "PUT", "DELETE"} else None,
            params=None if method.upper() in {"POST", "PUT", "DELETE"} else data,
            timeout=self.timeout,
        )
        try:
            body = response.json()
        except Exception:
            body = {"msg": response.text[:500]}
        if not response.ok:
            code = body.get("code") if isinstance(body, dict) else None
            msg = body.get("msg") if isinstance(body, dict) else str(body)
            raise RuntimeError(
                f"Binance {method.upper()} {path} HTTP {response.status_code} "
                f"code={code} msg={msg}"
            )
        return body

    def account(self) -> dict[str, Any]:
        return self._signed_request("GET", "/fapi/v3/account")

    def balances(self) -> list[dict[str, Any]]:
        return self._signed_request("GET", "/fapi/v3/balance")

    def position_risk(self, symbol: str | None = None) -> list[dict[str, Any]]:
        params = {"symbol": symbol.upper()} if symbol else {}
        return self._signed_request("GET", "/fapi/v3/positionRisk", params)

    def position_mode(self) -> dict[str, Any]:
        return self._signed_request("GET", "/fapi/v1/positionSide/dual")

    def set_leverage(self, symbol: str, leverage: int) -> dict[str, Any]:
        return self._signed_request(
            "POST",
            "/fapi/v1/leverage",
            {"symbol": symbol.upper(), "leverage": int(leverage)},
        )

    def set_margin_type(
        self,
        symbol: str,
        margin_type: str = "ISOLATED",
    ) -> dict[str, Any]:
        try:
            return self._signed_request(
                "POST",
                "/fapi/v1/marginType",
                {
                    "symbol": symbol.upper(),
                    "marginType": margin_type.upper(),
                },
            )
        except RuntimeError as exc:
            # Binance -4046 means margin type already has requested value.
            if "code=-4046" in str(exc):
                return {"code": -4046, "msg": "No need to change margin type."}
            raise

    def new_market_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: str,
        client_order_id: str,
        reduce_only: bool = False,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "positionSide": "BOTH",
            "type": "MARKET",
            "quantity": quantity,
            "newClientOrderId": client_order_id,
            "newOrderRespType": "RESULT",
        }
        if reduce_only:
            params["reduceOnly"] = "true"
        return self._signed_request("POST", "/fapi/v1/order", params)

    def query_order(
        self,
        *,
        symbol: str,
        client_order_id: str,
    ) -> dict[str, Any]:
        return self._signed_request(
            "GET",
            "/fapi/v1/order",
            {
                "symbol": symbol.upper(),
                "origClientOrderId": client_order_id,
            },
        )

    def user_trades(
        self,
        *,
        symbol: str,
        order_id: int | str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "symbol": symbol.upper(),
            "limit": max(1, min(int(limit), 1000)),
        }
        if order_id is not None:
            params["orderId"] = order_id
        return self._signed_request("GET", "/fapi/v1/userTrades", params)

    def exchange_symbol(self, symbol: str) -> dict[str, Any]:
        wanted = symbol.upper()
        for item in self.exchange_info().get("symbols", []):
            if item.get("symbol") == wanted:
                return item
        raise RuntimeError(f"symbol not found in exchangeInfo: {wanted}")

    def price_to_tick(
        self,
        *,
        symbol: str,
        price: float,
        round_up: bool = False,
    ) -> str:
        info = self.exchange_symbol(symbol)
        filters = {
            item.get("filterType"): item
            for item in info.get("filters", [])
            if isinstance(item, dict)
        }
        price_filter = filters.get("PRICE_FILTER") or {}
        tick = Decimal(str(price_filter.get("tickSize") or "0"))
        value = Decimal(str(price))
        if tick > 0:
            units = value / tick
            if round_up:
                rounded = units.to_integral_value(rounding="ROUND_CEILING")
            else:
                rounded = units.to_integral_value(rounding=ROUND_DOWN)
            value = rounded * tick
        return format(value.normalize(), "f")

    def new_stop_close_algo(
        self,
        *,
        symbol: str,
        side: str,
        trigger_price: str,
        client_algo_id: str,
    ) -> dict[str, Any]:
        return self._signed_request(
            "POST",
            "/fapi/v1/algoOrder",
            {
                "algoType": "CONDITIONAL",
                "symbol": symbol.upper(),
                "side": side.upper(),
                "positionSide": "BOTH",
                "type": "STOP_MARKET",
                "triggerPrice": trigger_price,
                "closePosition": "true",
                "workingType": "MARK_PRICE",
                "priceProtect": "true",
                "clientAlgoId": client_algo_id,
            },
        )

    def query_algo_order(
        self,
        *,
        client_algo_id: str,
    ) -> dict[str, Any]:
        return self._signed_request(
            "GET",
            "/fapi/v1/algoOrder",
            {"clientAlgoId": client_algo_id},
        )

    def cancel_algo_order(
        self,
        *,
        client_algo_id: str,
    ) -> dict[str, Any]:
        return self._signed_request(
            "DELETE",
            "/fapi/v1/algoOrder",
            {"clientAlgoId": client_algo_id},
        )

    def market_quantity(
        self,
        *,
        symbol: str,
        notional_usdt: float,
        reference_price: float,
    ) -> str:
        if notional_usdt <= 0 or reference_price <= 0:
            raise ValueError("notional and reference price must be positive")
        info = self.exchange_symbol(symbol)
        filters = {
            item.get("filterType"): item
            for item in info.get("filters", [])
            if isinstance(item, dict)
        }
        lot = filters.get("MARKET_LOT_SIZE") or filters.get("LOT_SIZE") or {}
        step = Decimal(str(lot.get("stepSize") or "0"))
        min_qty = Decimal(str(lot.get("minQty") or "0"))
        max_qty = Decimal(str(lot.get("maxQty") or "0"))
        qty = Decimal(str(notional_usdt)) / Decimal(str(reference_price))
        if step > 0:
            qty = (qty / step).to_integral_value(rounding=ROUND_DOWN) * step
        if min_qty > 0 and qty < min_qty:
            raise RuntimeError(
                f"calculated quantity {qty} below minQty {min_qty} for {symbol}"
            )
        if max_qty > 0 and qty > max_qty:
            qty = max_qty
        normalized = format(qty.normalize(), "f")
        if Decimal(normalized) <= 0:
            raise RuntimeError(f"calculated quantity is zero for {symbol}")
        return normalized

    def available_usdt(self) -> float:
        for item in self.balances():
            if item.get("asset") == "USDT":
                return float(item.get("availableBalance") or 0.0)
        return 0.0

    def nonzero_positions(self) -> list[dict[str, Any]]:
        return [
            item
            for item in self.position_risk()
            if abs(float(item.get("positionAmt") or 0.0)) > 0.0
        ]
