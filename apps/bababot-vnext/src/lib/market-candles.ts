export const CANDLE_INTERVALS = {
  "1m": 60_000,
  "5m": 300_000,
  "15m": 900_000,
  "1h": 3_600_000,
  "4h": 14_400_000,
} as const;
export type CandleTimeframe = keyof typeof CANDLE_INTERVALS;
export const CANDLE_TIMEFRAMES = Object.keys(CANDLE_INTERVALS) as CandleTimeframe[];

export type Ohlcv = {
  time: number; open: number; high: number; low: number; close: number; volume: number;
};

export type PaperCandleResponse = {
  market: "BINANCE_USDT_FUTURES";
  symbol: string;
  timeframe: CandleTimeframe;
  bars: Ohlcv[];
  tradeId: string;
  fromMs: number;
  toMs: number;
  source: "binance-fapi" | "vps2-archive";
  fetchedAt: string;
  warning: string | null;
};

/** Keep historical candles around a PAPER trade: no present-day ticker substitution. */
export function marketWindow(timeframe: CandleTimeframe, entryMs: number, closeMs: number | null) {
  const ms = CANDLE_INTERVALS[timeframe];
  const before = ms * (timeframe === "1m" ? 80 : 110);
  const after = ms * (timeframe === "1m" ? 45 : 40);
  // OPEN positions end at current time, bounded by the public 1000-bar Binance limit.
  const end = closeMs ?? Date.now();
  const earliestEnd = Math.max(entryMs, end);
  return {
    startTime: Math.max(0, entryMs - before),
    endTime: Math.min(Date.now(), Math.max(entryMs + after, earliestEnd + after)),
  };
}

export function parseBinanceKlines(input: unknown): Ohlcv[] {
  if (!Array.isArray(input)) throw Error("Invalid Binance Futures response");
  const byTime = new Map<number, Ohlcv>();
  for (const item of input) {
    if (!Array.isArray(item) || item.length < 6) throw Error("Incomplete Binance candle");
    const [time, open, high, low, close, volume] = item.slice(0,6).map(Number);
    if (![time,open,high,low,close,volume].every(Number.isFinite) ||
        time < 0 || open <= 0 || close <= 0 || high <= 0 || low <= 0 ||
        high < Math.max(open,close,low) || low > Math.min(open,close,high) || volume < 0) {
      throw Error("Invalid Binance OHLCV");
    }
    byTime.set(time, {time,open,high,low,close,volume});
  }
  return [...byTime.values()].sort((a,b)=>a.time-b.time);
}
