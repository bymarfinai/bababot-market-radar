export type PaperTradeStatus = "OPEN" | "CLOSED" | "DATA_GAP" | "CENSORED_30MIN";
export type StrategyActivity = "ACTIVE" | "PAUSED" | "REFERENCE";
export type StrategyFamily = "original" | "p-series" | "master";

export type StrongStrategy = {
  id: string;
  label: string;
  family: StrategyFamily;
  activity: StrategyActivity;
  moduleLabel: string;
  closed: number;
  open: number;
  wins: number;
  losses: number;
  dataGap: number;
  netPnl: number;
  winRate: number | null;
  lastActivityAtMs: number | null;
};

export type StrongTrade = {
  id: string;
  strategyId: string;
  sourceEventId: string;
  symbol: string;
  status: PaperTradeStatus;
  openedAtMs: number;
  closedAtMs: number | null;
  entryPrice: number | null;
  exitPrice: number | null;
  netPnl: number | null;
  closeReason: string | null;
  decision: string | null;
  decisionReason: string | null;
};

export type StrongSnapshot = {
  schemaVersion: 1;
  origin: "vps2-independent-paper";
  generatedAt: string;
  strategies: StrongStrategy[];
  trades: StrongTrade[];
};

export type StrongApiResponse = {
  mode: "sync" | "live" | "snapshot" | "unconfigured";
  snapshot: StrongSnapshot | null;
  warning: string | null;
};

export function isStrongSnapshot(value: unknown): value is StrongSnapshot {
  if (!value || typeof value !== "object") return false;
  const x = value as Record<string, unknown>;
  if (x.schemaVersion !== 1 || x.origin !== "vps2-independent-paper") return false;
  if (typeof x.generatedAt !== "string" || !Array.isArray(x.strategies) || !Array.isArray(x.trades)) return false;
  return x.strategies.every(s => !!s && typeof s.id === "string" && typeof s.closed === "number" && typeof s.netPnl === "number") &&
    x.trades.every(t => !!t && typeof t.strategyId === "string" && typeof t.sourceEventId === "string" && typeof t.symbol === "string");
}
