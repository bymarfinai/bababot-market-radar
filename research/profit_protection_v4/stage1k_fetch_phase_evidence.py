from __future__ import annotations

import argparse
import bisect
import json
import math
import statistics
import time
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STAGE1J = (
    ROOT
    / "research/profit_protection_v4/results/"
    "stage1j_clean_post_entry_mfe_evidence.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "research/profit_protection_v4/results/"
    "stage1k_sub5s_phase_benchmark_evidence.json"
)
CADENCES_MS = (5000, 2000, 1000)
PHASE_GRID_MS = 100


def side_return(side: str, entry: float, price: float) -> float:
    raw = 100.0 * (price / entry - 1.0)
    return raw if side.upper() == "LONG" else -raw


def threshold_price(
    side: str,
    entry: float,
    clean_mfe_pct: float,
    capture_ratio: float,
) -> float:
    target_pct = clean_mfe_pct * capture_ratio
    if side.upper() == "LONG":
        return entry * (1.0 + target_pct / 100.0)
    return entry * (1.0 - target_pct / 100.0)


def sample_price(
    *,
    times: list[int],
    prices: list[float],
    prior_price: float,
    sample_at_ms: int,
) -> float:
    index = bisect.bisect_right(times, int(sample_at_ms)) - 1
    return prices[index] if index >= 0 else float(prior_price)


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * q
    lo = math.floor(position)
    hi = math.ceil(position)
    if lo == hi:
        return ordered[lo]
    weight = position - lo
    return ordered[lo] * (1.0 - weight) + ordered[hi] * weight


class BinanceHistory:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "BabaBot-PP-V4-1K/1.0"}
        )

    def get(self, path: str, params: dict[str, Any]) -> Any:
        last: Exception | str | None = None
        for attempt in range(10):
            try:
                response = self.session.get(
                    "https://fapi.binance.com" + path,
                    params=params,
                    timeout=10,
                )
                if response.status_code in {418, 429}:
                    last = f"HTTP {response.status_code}"
                    time.sleep(min(5.0, 0.5 * (attempt + 1)))
                    continue
                response.raise_for_status()
                time.sleep(0.035)
                return response.json()
            except Exception as exc:  # pragma: no cover - network
                last = exc
                time.sleep(min(3.0, 0.3 * (attempt + 1)))
        raise RuntimeError(f"{path} {params}: {last}")

    def aggregate_trades(
        self,
        symbol: str,
        start_ms: int,
        end_ms: int,
    ) -> list[dict[str, Any]]:
        if end_ms < start_ms:
            return []
        data = self.get(
            "/fapi/v1/aggTrades",
            {
                "symbol": symbol,
                "startTime": int(start_ms),
                "endTime": int(end_ms),
                "limit": 1000,
            },
        )
        output = [
            row
            for row in data
            if start_ms <= int(row["T"]) <= end_ms
        ]
        guard = 0
        while data and len(data) >= 1000:
            guard += 1
            if guard > 120:
                raise RuntimeError(
                    f"aggregate-trade pagination runaway: {symbol}"
                )
            next_rows = self.get(
                "/fapi/v1/aggTrades",
                {
                    "symbol": symbol,
                    "fromId": int(data[-1]["a"]) + 1,
                    "limit": 1000,
                },
            )
            output.extend(
                row
                for row in next_rows
                if start_ms <= int(row["T"]) <= end_ms
            )
            if (
                not next_rows
                or int(next_rows[-1]["T"]) > end_ms
                or len(next_rows) < 1000
            ):
                break
            data = next_rows
        return output

    def klines(
        self,
        symbol: str,
        start_ms: int,
        end_ms: int,
    ) -> list[list[Any]]:
        return self.get(
            "/fapi/v1/klines",
            {
                "symbol": symbol,
                "interval": "1m",
                "startTime": int(start_ms),
                "endTime": int(end_ms),
                "limit": 1500,
            },
        )


def residual_rows(stage1j_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for source in stage1j_rows:
        clean_mfe = float(source["clean_post_entry_mfe_pct"])
        if clean_mfe < 0.30:
            continue
        if float(source["peak5"]) / clean_mfe >= 0.80:
            continue
        output.append(dict(source))
    return output


def simulate_trade(
    source: dict[str, Any],
    client: BinanceHistory,
) -> dict[str, Any]:
    minute_ms = 60_000
    symbol = str(source["symbol"])
    side = str(source["side"]).upper()
    entry = float(source["entry_price"])
    clean_mfe = float(source["clean_post_entry_mfe_pct"])
    opened = int(source["opened_at_ms"])
    closed = int(source["closed_at_ms"])
    actual_5s_capture = float(source["peak5"]) / clean_mfe

    first_minute = (opened // minute_ms) * minute_ms
    last_minute = (closed // minute_ms) * minute_ms
    klines = client.klines(
        symbol,
        first_minute,
        last_minute + minute_ms - 1,
    )
    by_minute = {int(row[0]): row for row in klines}
    price80 = threshold_price(side, entry, clean_mfe, 0.80)

    candidate_minutes: list[int] = []
    cursor = first_minute
    while cursor <= last_minute:
        row = by_minute.get(cursor)
        if row is not None:
            high = float(row[2])
            low = float(row[3])
            qualifies = (
                high >= price80 if side == "LONG" else low <= price80
            )
            if qualifies:
                candidate_minutes.append(cursor)
        cursor += minute_ms

    exact_minutes: list[int] = []
    minute_data: dict[int, dict[str, Any]] = {}
    total_ticks = 0
    for minute_open in candidate_minutes:
        start = max(opened, minute_open)
        end = min(closed, minute_open + minute_ms - 1)
        trades = client.aggregate_trades(symbol, start, end)
        total_ticks += len(trades)
        times = [int(row["T"]) for row in trades]
        prices = [float(row["p"]) for row in trades]
        previous_price = entry
        if minute_open > first_minute:
            previous = by_minute.get(minute_open - minute_ms)
            if previous is not None:
                previous_price = float(previous[4])

        favorable = [
            side_return(side, entry, price)
            for price in prices
        ]
        if favorable and max(favorable) >= 0.80 * clean_mfe - 1e-12:
            exact_minutes.append(minute_open)
            minute_data[minute_open] = {
                "start": start,
                "end": end,
                "times": times,
                "prices": prices,
                "prior_price": previous_price,
            }

    cadence_results: dict[str, Any] = {}
    for cadence in CADENCES_MS:
        phases: list[dict[str, Any]] = []
        for offset in range(0, cadence, PHASE_GRID_MS):
            best = float("-inf")
            for minute_open in exact_minutes:
                data = minute_data[minute_open]
                base = opened + offset
                if base > int(data["end"]):
                    continue
                if base < int(data["start"]):
                    steps = math.ceil(
                        (int(data["start"]) - base) / cadence
                    )
                    sample_at = base + steps * cadence
                else:
                    sample_at = base

                while sample_at <= int(data["end"]):
                    price = sample_price(
                        times=data["times"],
                        prices=data["prices"],
                        prior_price=float(data["prior_price"]),
                        sample_at_ms=sample_at,
                    )
                    best = max(
                        best,
                        side_return(side, entry, price),
                    )
                    sample_at += cadence

            capture = (
                max(0.0, best / clean_mfe)
                if math.isfinite(best)
                else 0.0
            )
            phases.append(
                {
                    "offset_ms": offset,
                    "capture_ratio": capture,
                    "ge80": capture >= 0.80,
                    "ge90": capture >= 0.90,
                    "ge95": capture >= 0.95,
                }
            )

        captures = [float(row["capture_ratio"]) for row in phases]
        cadence_results[str(cadence)] = {
            "phase_count": len(phases),
            "ge80_phase_probability": (
                sum(bool(row["ge80"]) for row in phases) / len(phases)
            ),
            "ge90_phase_probability": (
                sum(bool(row["ge90"]) for row in phases) / len(phases)
            ),
            "ge95_phase_probability": (
                sum(bool(row["ge95"]) for row in phases) / len(phases)
            ),
            "capture_median_ratio": statistics.median(captures),
            "capture_p10_ratio": percentile(captures, 0.10),
            "capture_min_ratio": min(captures),
            "capture_max_ratio": max(captures),
            "incremental_over_actual5_median_ratio": statistics.median(
                [max(actual_5s_capture, value) for value in captures]
            ),
            "phases": phases,
        }

    return {
        "position_id": source["position_id"],
        "symbol": symbol,
        "side": side,
        "opened_at_ms": opened,
        "closed_at_ms": closed,
        "entry_price": entry,
        "clean_mfe_pct": clean_mfe,
        "actual_5s_capture_ratio": actual_5s_capture,
        "candidate_1m_count_preclip": len(candidate_minutes),
        "candidate_1m_count_exact": len(exact_minutes),
        "candidate_tick_count": total_ticks,
        "cadences": cadence_results,
        "event_driven_tick_capture_ratio": 1.0,
    }


def main() -> None:  # pragma: no cover - public network research utility
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage1j", default=str(DEFAULT_STAGE1J))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    stage1j = json.loads(Path(args.stage1j).read_text(encoding="utf-8"))
    cohort = residual_rows(stage1j)
    client = BinanceHistory()
    output: list[dict[str, Any]] = []
    output_path = Path(args.output)

    for index, row in enumerate(cohort, 1):
        result = simulate_trade(row, client)
        output.append(result)
        output_path.write_text(
            json.dumps(output, indent=2, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )
        print(
            f"{index}/{len(cohort)} {result['symbol']} "
            f"2s80={result['cadences']['2000']['ge80_phase_probability']:.3f} "
            f"1s80={result['cadences']['1000']['ge80_phase_probability']:.3f}",
            flush=True,
        )


if __name__ == "__main__":
    main()
