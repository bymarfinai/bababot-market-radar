import type { StrongTrade } from "./strong-types";

/**
 * Analytics for STRONG LONG independent PAPER portfolios.
 *
 * Deliberately NOT a round-trip reconstruction: source ledgers already provide
 * authoritative net realized USD per independent strategy event. Without an
 * execution/fill ledger, we cannot infer gross PnL, fees, MAE/MFE, R, or true
 * balance-relative drawdown %. No strategy aggregation is permitted.
 */
export type JournalOutcome = "WIN" | "LOSS" | "BREAKEVEN" | "OPEN" | "UNRESOLVED";
export type DateBucket = {
  date: string; trades: number; wins: number; losses: number; breakevens: number; netPnl: number;
};
export type JournalEquityPoint = {
  id: string; closedAtMs: number; equity: number; drawdown: number;
};
export type SymbolStats = {
  symbol: string; trades: number; wins: number; losses: number; breakevens: number;
  netPnl: number; winRate: number | null;
};
export type ReasonStats = {
  reason: string; trades: number; wins: number; losses: number; netPnl: number;
};
export type JournalStats = {
  closed: number; open: number; unresolved: number; wins: number; losses: number; breakevens: number;
  netPnl: number; winRate: number | null; grossWinningPnl: number; grossLosingPnlAbs: number;
  profitFactor: number | null; expectancy: number | null; avgWin: number | null; avgLossAbs: number | null;
  payoffRatio: number | null; bestTrade: number | null; worstTrade: number | null;
  avgDurationMs: number | null; medianDurationMs: number | null; maxDrawdownUsd: number;
  maxWinStreak: number; maxLossStreak: number;
  uniqueSourceEvents: number; sampleWarning: string | null;
};
export type JournalOverview = {
  metrics: JournalStats; equity: JournalEquityPoint[];
  days: DateBucket[]; symbols: SymbolStats[]; reasons: ReasonStats[];
};
export type MatchedEvent = {
  sourceEventId: string; symbol: string; left: StrongTrade; right: StrongTrade;
  leftNet: number; rightNet: number; deltaLeftMinusRight: number;
};
export type MatchedOverview = {
  left: string; right: string; matchedCount: number;
  leftNet: number; rightNet: number; leftWins: number; rightWins: number;
  leftLosses: number; rightLosses: number;
  missingLeft: number; missingRight: number; events: MatchedEvent[];
};

export const JOURNAL_TIMEZONE = "Asia/Jakarta" as const;
const dayFormatter = new Intl.DateTimeFormat("en-US", {
  timeZone: JOURNAL_TIMEZONE, year: "numeric", month: "2-digit", day: "2-digit"
});

export function wibDateKey(timestampMs: number): string {
  if (!Number.isFinite(timestampMs)) return "";
  const parts = Object.fromEntries(dayFormatter.formatToParts(timestampMs).map(p => [p.type, p.value]));
  return `${parts.year}-${parts.month}-${parts.day}`;
}

export function isRealized(trade: StrongTrade): boolean {
  return trade.status === "CLOSED" &&
    Number.isFinite(trade.netPnl) && trade.netPnl !== null &&
    Number.isFinite(trade.closedAtMs) && trade.closedAtMs !== null;
}

export function classifyTrade(trade: StrongTrade): JournalOutcome {
  if (trade.status === "OPEN") return "OPEN";
  if (!isRealized(trade)) return "UNRESOLVED";
  return trade.netPnl! > 0 ? "WIN" : trade.netPnl! < 0 ? "LOSS" : "BREAKEVEN";
}

export function orderedClosed(trades: readonly StrongTrade[]): StrongTrade[] {
  return trades.filter(isRealized).sort((a,b) =>
    (a.closedAtMs! - b.closedAtMs!) || a.id.localeCompare(b.id)
  );
}
function mean(numbers: number[]): number | null {
  return numbers.length ? numbers.reduce((a,b)=>a+b,0)/numbers.length : null;
}
function median(numbers: number[]): number | null {
  if (!numbers.length) return null;
  const a=[...numbers].sort((x,y)=>x-y);
  const middle=Math.floor(a.length/2);
  return a.length%2 ? a[middle] : (a[middle-1]+a[middle])/2;
}
function pct(wins: number, total: number): number | null {
  return total ? wins / total * 100 : null;
}
function sum(list: number[]): number { return list.reduce((a,b)=>a+b,0); }
function sortByNetAndCount<T extends {netPnl:number;trades:number}>(a:T,b:T):number {
  return b.netPnl-a.netPnl || b.trades-a.trades;
}

export function journalOverview(strategyTrades: readonly StrongTrade[]): JournalOverview {
  const independentStrategies = new Set(strategyTrades.map(t => t.strategyId));
  if (independentStrategies.size > 1) {
    throw new Error("Journal PnL cannot aggregate independent PAPER strategies; select one branch.");
  }
  const closed = orderedClosed(strategyTrades);
  const wins=closed.filter(t=>t.netPnl!>0);
  const losses=closed.filter(t=>t.netPnl!<0);
  const breakevens=closed.filter(t=>t.netPnl===0);
  const grossWinningPnl=sum(wins.map(t=>t.netPnl!));
  const grossLosingPnlAbs=-sum(losses.map(t=>t.netPnl!));
  const netPnl=sum(closed.map(t=>t.netPnl!));
  const avgWin=mean(wins.map(t=>t.netPnl!));
  const avgLossAbs=mean(losses.map(t=>Math.abs(t.netPnl!)));
  const durations=closed.map(t=>t.closedAtMs!-t.openedAtMs).filter(n=>Number.isFinite(n)&&n>=0);
  const equity:JournalEquityPoint[]=[];
  let running=0,highWater=0,maxDrawdownUsd=0,winStreak=0,lossStreak=0,maxWinStreak=0,maxLossStreak=0;
  if(closed.length) equity.push({id:"baseline",closedAtMs:closed[0].closedAtMs!-1,equity:0,drawdown:0});
  for (const trade of closed) {
    const n=trade.netPnl!;
    running+=n;
    highWater=Math.max(highWater,running);
    const drawdown=highWater-running;
    maxDrawdownUsd=Math.max(maxDrawdownUsd,drawdown);
    equity.push({id:trade.id,closedAtMs:trade.closedAtMs!,equity:running,drawdown});
    if(n>0){winStreak++;lossStreak=0;}
    else if(n<0){lossStreak++;winStreak=0;}
    else {winStreak=0;lossStreak=0;}
    maxWinStreak=Math.max(maxWinStreak,winStreak);
    maxLossStreak=Math.max(maxLossStreak,lossStreak);
  }
  const dayMap=new Map<string,DateBucket>();
  const symbolMap=new Map<string,SymbolStats>();
  const reasonMap=new Map<string,ReasonStats>();
  for(const trade of closed){
    const value=trade.netPnl!,won=value>0,lost=value<0,tie=value===0;
    const date=wibDateKey(trade.closedAtMs!);
    const day=dayMap.get(date) ?? {date,trades:0,wins:0,losses:0,breakevens:0,netPnl:0};
    day.trades++;day.wins+=Number(won);day.losses+=Number(lost);day.breakevens+=Number(tie);day.netPnl+=value;dayMap.set(date,day);
    const symbol=symbolMap.get(trade.symbol) ?? {symbol:trade.symbol,trades:0,wins:0,losses:0,breakevens:0,netPnl:0,winRate:null};
    symbol.trades++;symbol.wins+=Number(won);symbol.losses+=Number(lost);symbol.breakevens+=Number(tie);symbol.netPnl+=value;
    symbol.winRate=pct(symbol.wins,symbol.trades);symbolMap.set(trade.symbol,symbol);
    const reason=trade.closeReason?.trim() || "UNSPECIFIED";
    const group=reasonMap.get(reason) ?? {reason,trades:0,wins:0,losses:0,netPnl:0};
    group.trades++;group.wins+=Number(won);group.losses+=Number(lost);group.netPnl+=value;reasonMap.set(reason,group);
  }

  const uniqueSourceEvents=new Set(strategyTrades.map(t=>t.sourceEventId)).size;
  const metrics:JournalStats = {
    closed:closed.length,
    open:strategyTrades.filter(t=>t.status==="OPEN").length,
    unresolved:strategyTrades.filter(t=>classifyTrade(t)==="UNRESOLVED").length,
    wins:wins.length,losses:losses.length,breakevens:breakevens.length,
    netPnl,winRate:pct(wins.length,closed.length),
    grossWinningPnl,grossLosingPnlAbs,
    profitFactor:grossLosingPnlAbs>0 ? grossWinningPnl/grossLosingPnlAbs :
      grossWinningPnl>0 ? Number.POSITIVE_INFINITY : null,
    expectancy:mean(closed.map(t=>t.netPnl!)),
    avgWin,avgLossAbs,payoffRatio:avgWin!==null&&avgLossAbs!==null&&avgLossAbs>0 ? avgWin/avgLossAbs:null,
    bestTrade:closed.length?Math.max(...closed.map(t=>t.netPnl!)):null,
    worstTrade:closed.length?Math.min(...closed.map(t=>t.netPnl!)):null,
    avgDurationMs:mean(durations), medianDurationMs:median(durations),
    maxDrawdownUsd,maxWinStreak,maxLossStreak,
    uniqueSourceEvents,
    sampleWarning:closed.length < 20
      ? `Small sample: only ${closed.length} CLOSED PAPER trade(s). Results are descriptive, not a validated trading edge.` : null
  };
  return {
    metrics,equity,days:[...dayMap.values()].sort((a,b)=>a.date.localeCompare(b.date)),
    symbols:[...symbolMap.values()].sort(sortByNetAndCount),
    reasons:[...reasonMap.values()].sort((a,b)=>b.trades-a.trades || a.reason.localeCompare(b.reason))
  };
}

export function filterStrategyMonth(trades: readonly StrongTrade[], strategyId: string, month: string): StrongTrade[] {
  return trades.filter(t=>t.strategyId===strategyId && (month==="all" ||
    (t.status==="OPEN"
      ? wibDateKey(t.openedAtMs).slice(0,7)===month
      : t.closedAtMs!==null && wibDateKey(t.closedAtMs).slice(0,7)===month)));
}

export function availableCloseMonths(trades: readonly StrongTrade[]): string[] {
  return [...new Set(trades.filter(isRealized).map(t=>wibDateKey(t.closedAtMs!).slice(0,7)))]
    .sort((a,b)=>b.localeCompare(a));
}

export function matchedOverview(trades: readonly StrongTrade[], left: string, right: string): MatchedOverview {
  if(left===right) return {left,right,matchedCount:0,leftNet:0,rightNet:0,leftWins:0,rightWins:0,leftLosses:0,rightLosses:0,missingLeft:0,missingRight:0,events:[]};
  const registry=new Map<string,{left?:StrongTrade;right?:StrongTrade}>();
  for (const trade of trades) {
    if(trade.strategyId!==left && trade.strategyId!==right)continue;
    const item=registry.get(trade.sourceEventId)??{};
    if(trade.strategyId===left)item.left=trade;
    else item.right=trade;
    registry.set(trade.sourceEventId,item);
  }
  const events: MatchedEvent[]=[];
  let missingLeft=0,missingRight=0;
  for(const [sourceEventId,pair] of registry.entries()){
    if(!pair.left){missingLeft++;continue;}
    if(!pair.right){missingRight++;continue;}
    if(!isRealized(pair.left)||!isRealized(pair.right))continue;
    if(pair.left.symbol!==pair.right.symbol)continue;
    events.push({
      sourceEventId,symbol:pair.left.symbol,
      left:pair.left,right:pair.right,
      leftNet:pair.left.netPnl!,rightNet:pair.right.netPnl!,
      deltaLeftMinusRight:pair.left.netPnl!-pair.right.netPnl!
    });
  }
  events.sort((a,b)=>(b.left.closedAtMs??0)-(a.left.closedAtMs??0)||a.sourceEventId.localeCompare(b.sourceEventId));
  return {
    left,right,matchedCount:events.length,
    leftNet:sum(events.map(x=>x.leftNet)),rightNet:sum(events.map(x=>x.rightNet)),
    leftWins:events.filter(x=>x.leftNet>0).length,rightWins:events.filter(x=>x.rightNet>0).length,
    leftLosses:events.filter(x=>x.leftNet<0).length,rightLosses:events.filter(x=>x.rightNet<0).length,
    missingLeft,missingRight,events
  };
}
