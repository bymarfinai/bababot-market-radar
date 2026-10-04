from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import median
from typing import Iterable, Mapping, Sequence


EPS = 1e-12


@dataclass(frozen=True)
class Trade:
    price: float
    qty: float
    timestamp_ms: int
    buyer_is_maker: bool

    @property
    def quote_qty(self) -> float:
        return self.price * self.qty

    @property
    def taker_sign(self) -> float:
        # Binance m=true means buyer is maker -> aggressive seller.
        return -1.0 if self.buyer_is_maker else 1.0


def _f(value: object) -> float:
    out = float(value)
    if not isfinite(out):
        raise ValueError("non-finite numeric value")
    return out


def parse_agg_trades(rows: Iterable[Mapping[str, object]]) -> list[Trade]:
    out: list[Trade] = []
    for row in rows:
        out.append(
            Trade(
                price=_f(row.get("p", row.get("price"))),
                qty=_f(row.get("q", row.get("qty"))),
                timestamp_ms=int(row.get("T", row.get("time"))),
                buyer_is_maker=bool(row.get("m", row.get("isBuyerMaker"))),
            )
        )
    return sorted(out, key=lambda x: x.timestamp_ms)


def _book_side(levels: Sequence[Sequence[object]], depth: int) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for level in levels[:depth]:
        if len(level) < 2:
            continue
        price, qty = _f(level[0]), _f(level[1])
        if price > 0 and qty >= 0:
            out.append((price, qty))
    return out


def depth_features(
    bids: Sequence[Sequence[object]],
    asks: Sequence[Sequence[object]],
) -> dict[str, float]:
    if not bids or not asks:
        return {}

    b20 = _book_side(bids, 20)
    a20 = _book_side(asks, 20)
    if not b20 or not a20:
        return {}

    best_bid, best_bid_qty = b20[0]
    best_ask, best_ask_qty = a20[0]
    mid = (best_bid + best_ask) / 2.0
    spread_bps = (best_ask - best_bid) / max(mid, EPS) * 10_000.0

    denom = best_bid_qty + best_ask_qty
    microprice = (
        best_ask * best_bid_qty + best_bid * best_ask_qty
    ) / max(denom, EPS)
    microprice_edge_bps = (microprice - mid) / max(mid, EPS) * 10_000.0

    out: dict[str, float] = {
        "lob_spread_bps": spread_bps,
        "lob_microprice_edge_bps": microprice_edge_bps,
        "lob_top1_imbalance": (best_bid_qty - best_ask_qty) / max(denom, EPS),
    }

    for depth in (5, 10, 20):
        bs = b20[:depth]
        aa = a20[:depth]
        bqty = sum(q for _, q in bs)
        aqty = sum(q for _, q in aa)
        bnot = sum(p * q for p, q in bs)
        anot = sum(p * q for p, q in aa)
        out[f"lob_qty_imbalance_{depth}"] = (bqty - aqty) / max(bqty + aqty, EPS)
        out[f"lob_notional_imbalance_{depth}"] = (bnot - anot) / max(bnot + anot, EPS)

        # Near-touch concentration: fraction of depth in the first two levels.
        bnear = sum(q for _, q in bs[:2])
        anear = sum(q for _, q in aa[:2])
        out[f"lob_bid_near_touch_share_{depth}"] = bnear / max(bqty, EPS)
        out[f"lob_ask_near_touch_share_{depth}"] = anear / max(aqty, EPS)

        # Distance-weighted pressure gives more weight to liquidity near the touch.
        bw = sum(q / max(abs(mid - p) / max(mid, EPS), 1e-7) for p, q in bs)
        aw = sum(q / max(abs(p - mid) / max(mid, EPS), 1e-7) for p, q in aa)
        out[f"lob_distance_weighted_imbalance_{depth}"] = (bw - aw) / max(bw + aw, EPS)

    return out


def _window(rows: Sequence[Trade], end_ms: int, seconds: int) -> list[Trade]:
    start = end_ms - seconds * 1000
    return [r for r in rows if start <= r.timestamp_ms <= end_ms]


def _trade_window_features(rows: Sequence[Trade], prefix: str) -> dict[str, float]:
    if not rows:
        return {}

    buy = [r for r in rows if r.taker_sign > 0]
    sell = [r for r in rows if r.taker_sign < 0]
    buy_quote = sum(r.quote_qty for r in buy)
    sell_quote = sum(r.quote_qty for r in sell)
    total_quote = buy_quote + sell_quote
    signed_quote = buy_quote - sell_quote

    prices = [r.price for r in rows]
    first_price, last_price = prices[0], prices[-1]
    ret_bps = (last_price / max(first_price, EPS) - 1.0) * 10_000.0

    qq = sorted(r.quote_qty for r in rows)
    q90 = qq[min(len(qq) - 1, int(0.90 * (len(qq) - 1)))]
    large = [r for r in rows if r.quote_qty >= q90]
    large_signed = sum(r.taker_sign * r.quote_qty for r in large)
    large_total = sum(r.quote_qty for r in large)

    buy_avg = buy_quote / max(len(buy), 1)
    sell_avg = sell_quote / max(len(sell), 1)

    # If aggressive flow is large but price barely responds, absorption rises.
    flow_share = signed_quote / max(total_quote, EPS)
    absorption = abs(flow_share) / max(abs(ret_bps), 0.25)

    # Directional efficiency: price response per 1% signed-flow imbalance.
    impact_eff = ret_bps / max(abs(flow_share) * 100.0, 0.25)
    if flow_share < 0:
        impact_eff *= -1.0

    return {
        f"{prefix}_quote_volume": total_quote,
        f"{prefix}_cvd_quote": signed_quote,
        f"{prefix}_cvd_share": flow_share,
        f"{prefix}_trade_count_imbalance": (len(buy) - len(sell)) / max(len(rows), 1),
        f"{prefix}_buy_sell_avg_size_ratio": buy_avg / max(sell_avg, EPS),
        f"{prefix}_large_trade_imbalance": large_signed / max(large_total, EPS),
        f"{prefix}_price_return_bps": ret_bps,
        f"{prefix}_flow_price_efficiency": impact_eff,
        f"{prefix}_absorption_proxy": absorption,
        f"{prefix}_trade_count": float(len(rows)),
    }


def aggtrade_features(
    rows: Iterable[Mapping[str, object]],
    *,
    decision_ms: int,
) -> dict[str, float]:
    trades = parse_agg_trades(rows)
    if not trades:
        return {}

    out: dict[str, float] = {}
    for sec in (1, 5, 15, 30, 60):
        out.update(_trade_window_features(_window(trades, decision_ms, sec), f"agg_{sec}s"))

    # Acceleration / persistence across nested windows.
    for short, long in ((1, 5), (5, 15), (15, 30), (30, 60)):
        a = out.get(f"agg_{short}s_cvd_share")
        b = out.get(f"agg_{long}s_cvd_share")
        if a is not None and b is not None:
            out[f"agg_cvd_accel_{short}s_vs_{long}s"] = a - b

    vals = [out.get(f"agg_{s}s_cvd_share") for s in (1, 5, 15, 30, 60)]
    vals = [v for v in vals if v is not None]
    if vals:
        out["agg_cvd_persistence"] = sum(1.0 if v > 0 else -1.0 if v < 0 else 0.0 for v in vals) / len(vals)

    return out


def side_adjust(features: Mapping[str, float], side: str) -> dict[str, float]:
    sign = 1.0 if side.upper() == "LONG" else -1.0
    signed_keys = (
        "imbalance",
        "microprice_edge",
        "cvd_share",
        "cvd_quote",
        "price_return",
        "flow_price_efficiency",
        "persistence",
        "accel",
    )
    out: dict[str, float] = {}
    for key, value in features.items():
        val = float(value)
        out[key] = val * sign if any(token in key for token in signed_keys) else val
    return out
