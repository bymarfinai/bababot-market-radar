import test from "node:test";
import assert from "node:assert/strict";
import {
  journalOverview,matchedOverview,filterStrategyMonth,wibDateKey,
  classifyTrade,availableCloseMonths
} from "../src/lib/journal-analytics.ts";

const mk=(id, strategyId, sourceEventId, netPnl, closedAtMs, extra={})=>({
  id, strategyId, sourceEventId, symbol:"ABCUSDT",status:"CLOSED",
  openedAtMs:closedAtMs-60_000,closedAtMs,entryPrice:1,exitPrice:1.01,
  netPnl,closeReason:"TP",decision:null,decisionReason:null,...extra
});
const base=Date.parse("2026-11-04T16:59:00Z");
test("WIB date groups UTC 17:00 on following local day",()=>{
  assert.equal(wibDateKey(Date.parse("2026-11-04T16:59:59Z")),"2026-11-04");
  assert.equal(wibDateKey(Date.parse("2026-11-04T17:00:00Z")),"2026-11-05");
});
test("only CLOSED realized ledger pnl counted; no double-counting open or gaps",()=>{
  const trades=[
    mk("a1","M03","E1",12,base),
    mk("a2","M03","E2",-8,base+60_000),
    mk("a3","M03","E3",0,base+120_000),
    mk("a4","M03","E4",null,base+180_000,{status:"OPEN",closedAtMs:null}),
    mk("a5","M03","E5",null,base+240_000,{status:"DATA_GAP",closedAtMs:null}),
  ];
  const {metrics,equity,days}=journalOverview(trades);
  assert.equal(metrics.closed,3);assert.equal(metrics.open,1);
  assert.equal(metrics.unresolved,1);
  assert.equal(metrics.wins,1);assert.equal(metrics.losses,1);assert.equal(metrics.breakevens,1);
  assert.equal(metrics.netPnl,4);
  assert.ok(Math.abs(metrics.winRate - 100/3) < 1e-10);
  assert.equal(metrics.profitFactor,1.5);
  assert.equal(metrics.expectancy,4/3);
  assert.equal(metrics.maxDrawdownUsd,8);
  assert.deepEqual(equity.map(p=>p.equity),[0,12,4,4]);
  assert.deepEqual(days.map(d=>d.date),["2026-11-04","2026-11-05"]);
  assert.equal(days[0].netPnl,12);
  assert.equal(days[1].netPnl,-8);
});
test("zero-loss positive PnL is infinite PF; zero trades is null, not 100%",()=>{
  assert.equal(journalOverview([mk("x","P01","X",3,base)]).metrics.profitFactor,Infinity);
  assert.equal(journalOverview([]).metrics.profitFactor,null);
  assert.equal(journalOverview([]).metrics.winRate,null);
});
test("month filter respects WIB close time, OPEN uses opening month",()=>{
  const at=Date.parse("2026-10-31T17:30:00Z");
  const a=mk("A","M03","E1",1,at);
  const b=mk("B","M03","E2",2,Date.parse("2026-10-31T16:00:00Z"));
  const c=mk("C","M03","E3",null,at,{status:"OPEN",closedAtMs:null});
  assert.deepEqual(filterStrategyMonth([a,b,c],"M03","2026-11").map(t=>t.id),["A","C"]);
  assert.deepEqual(availableCloseMonths([a,b,c]),["2026-11","2026-10"]);
  assert.equal(classifyTrade(c),"OPEN");
});
test("matched comparison only same source_event_id and same symbol; exclude missing branch",()=>{
  const trades=[
    mk("l1","M03","SOURCE:1",6,base),
    mk("r1","M04","SOURCE:1",3,base),
    mk("l2","M03","SOURCE:2",-2,base+60_000),
    mk("r2","M04","SOURCE:2",-4,base+60_000),
    mk("l3","M03","SOURCE:3",10,base+120_000),
    mk("r4","M04","SOURCE:4",3,base+180_000)
  ];
  const result=matchedOverview(trades,"M03","M04");
  assert.equal(result.matchedCount,2);
  assert.equal(result.leftNet,4);
  assert.equal(result.rightNet,-1);
  assert.equal(result.missingLeft,1);
  assert.equal(result.missingRight,1);
  assert.equal(result.events[0].sourceEventId,"SOURCE:2");
  assert.equal(result.events[0].deltaLeftMinusRight,2);
});
test("win-loss streaks and drawdown in USD from zero baseline",()=>{
 const arr=[
  mk("a","A","s1",5,base),
  mk("b","A","s2",2,base+60_000),
  mk("c","A","s3",-3,base+120_000),
  mk("d","A","s4",-4,base+180_000),
  mk("e","A","s5",1,base+240_000)
 ];
 const {metrics}=journalOverview(arr);
 assert.equal(metrics.maxWinStreak,2);
 assert.equal(metrics.maxLossStreak,2);
 assert.equal(metrics.maxDrawdownUsd,7);
 assert.equal(metrics.netPnl,1);
});

test("mixed independent PAPER strategies are explicitly rejected from portfolio metrics",()=>{
 const a=mk("l1","M03","SIGNAL:A",4,base);
 const b=mk("r1","M04","SIGNAL:A",3,base);
 assert.throws(()=>journalOverview([a,b]),/cannot aggregate independent PAPER strategies/);
 assert.equal(journalOverview([a]).metrics.netPnl,4);
 assert.equal(journalOverview([b]).metrics.netPnl,3);
});
