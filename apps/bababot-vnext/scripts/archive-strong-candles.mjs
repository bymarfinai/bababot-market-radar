#!/usr/bin/env node
/**
 * Read-only VPS2 PAPER event -> real Binance USDT-M Futures OHLCV archive.
 *
 * Fetches public market data, not trades, and writes only private Vercel Blob.
 * Can run alongside the independent PAPER forward engines without DB writes.
 */
import { put } from "@vercel/blob";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const cwd=process.cwd();
const token=process.env.BLOB_READ_WRITE_TOKEN;
const exporter=process.env.STRONG_EXPORT_SCRIPT || path.join(cwd,"export-strong-vps2.py");
const root=process.env.STRONG_EXPORT_ROOT || "/home/ubuntu/market-detektor-research";
const stateDir=process.env.STRONG_SYNC_STATE_DIR || path.join(cwd,"state");
const stateFile=path.join(stateDir,"futures-candles.json");
const LIMIT_ARG=Number(process.argv.find(a=>a.startsWith("--limit="))?.split("=")[1] ?? "10");
const requested=process.argv.find(a=>a.startsWith("--event="))?.slice(8) || null;
const limit=Number.isFinite(LIMIT_ARG)?Math.max(1,Math.min(500,Math.floor(LIMIT_ARG))):10;
const tfIntervals={ "5m":300000,"1m":60000,"15m":900000,"1h":3600000,"4h":14400000 };

if(!token||token.length<25) throw Error("BLOB_READ_WRITE_TOKEN not configured");
const doc=JSON.parse(execFileSync("/usr/bin/python3",[exporter,"--root",root],{
  encoding:"utf8",maxBuffer:2000000,timeout:16000,
  env:{PATH:"/usr/bin:/bin",LANG:"C.UTF-8"}
}));
if(doc.schemaVersion!==1 || doc.origin!=="vps2-independent-paper" || !Array.isArray(doc.trades)) {
  throw Error("Invalid VPS2 PAPER normalization");
}
const groups=new Map();
for(const trade of doc.trades){
  if(!trade || !trade.sourceEventId || !/^[A-Z0-9]{1,24}USDT$/.test(trade.symbol) ||
     typeof trade.openedAtMs!=="number") throw Error("Invalid trade in normalized snapshot");
  const existing=groups.get(trade.sourceEventId);
  if(!existing) groups.set(trade.sourceEventId,{
    sourceEventId:trade.sourceEventId,symbol:trade.symbol,
    entryMs:trade.openedAtMs,
    lastMs:trade.closedAtMs??trade.openedAtMs,
    preferred: /^M0[3-5]$/.test(trade.strategyId)
  });
  else {
    if(existing.symbol!==trade.symbol)throw Error("Inconsistent symbol for source event");
    existing.entryMs=Math.min(existing.entryMs,trade.openedAtMs);
    existing.lastMs=Math.max(existing.lastMs,trade.closedAtMs??trade.openedAtMs);
    if(/^M0[3-5]$/.test(trade.strategyId)) existing.preferred=true;
  }
}
const groupsSorted=[...groups.values()].sort((a,b)=>
  Number(b.preferred)-Number(a.preferred) || b.lastMs-a.lastMs
);
const tasks=[];
for(const g of groupsSorted){
  if(requested && !g.sourceEventId.includes(requested))continue;
  for(const [tf,ms] of Object.entries(tfIntervals)) {
    const startMs=Math.max(0,g.entryMs-ms*(tf==="1m"?80:110));
    const endMs=Math.min(Date.now(),Math.max(g.entryMs,g.lastMs)+ms*(tf==="1m"?45:40));
    const eventHash=createHash("sha256").update(g.sourceEventId,"utf8").digest("hex");
    const key=`research/strong-candles/${tf}/${eventHash}.json`;
    const version=createHash("sha256").update(JSON.stringify({
      symbol:g.symbol,startMs,endMs,tf,sourceEventId:g.sourceEventId
    })).digest("hex");
    tasks.push({...g,tf,startMs,endMs,key,version});
  }
}
function readState(){try{return JSON.parse(fs.readFileSync(stateFile,"utf8"))}catch{return {}}}
const state=readState();
if(typeof state!=="object"||!state)throw Error("Invalid archive state");
const pending=tasks.filter(t=>state[t.key]?.version!==t.version).slice(0,limit);
let errors=0,done=0;

function save(){
  fs.mkdirSync(stateDir,{recursive:true,mode:0o700});
  const tmp=stateFile+".tmp";
  fs.writeFileSync(tmp,JSON.stringify(state),{mode:0o600,encoding:"utf8"});
  fs.renameSync(tmp,stateFile);
}
async function archive(t){
  const q=new URL("https://fapi.binance.com/fapi/v1/klines");
  q.searchParams.set("symbol",t.symbol);
  q.searchParams.set("interval",t.tf);
  q.searchParams.set("startTime",String(t.startMs));
  q.searchParams.set("endTime",String(t.endMs));
  q.searchParams.set("limit","1000");
  const resp=await fetch(q,{signal:AbortSignal.timeout(9000),redirect:"error"});
  if(!resp.ok)throw Error(`Binance Futures HTTP ${resp.status}`);
  const raw=await resp.json();
  if(!Array.isArray(raw)||raw.length===0||raw.length>1000)throw Error("Futures history empty/invalid");
  const byTime=new Map();
  for(const k of raw){
    if(!Array.isArray(k)||k.length<6)throw Error("Invalid OHLCV tuple");
    const [time,open,high,low,close,volume]=k.slice(0,6).map(Number);
    if(![time,open,high,low,close,volume].every(Number.isFinite) ||
       open<=0||high<=0||low<=0||close<=0||volume<0||
       high<Math.max(open,close,low)||low>Math.min(open,close,high))throw Error("Corrupted Futures candle");
    byTime.set(time,{time,open,high,low,close,volume});
  }
  const bars=[...byTime.values()].sort((a,b)=>a.time-b.time);
  if(!bars.length || bars[0].time>t.entryMs || bars.at(-1).time<t.lastMs-tfIntervals[t.tf]) {
    throw Error("Insufficient historical coverage for PAPER event");
  }
  const payload=JSON.stringify({
    schemaVersion:1,market:"BINANCE_USDT_FUTURES",
    symbol:t.symbol,timeframe:t.tf,sourceEventId:t.sourceEventId,
    fromMs:t.startMs,toMs:t.endMs,
    bars,source:"binance-fapi",fetchedAt:new Date().toISOString()
  });
  if(Buffer.byteLength(payload)>250000)throw Error("Archive size exceeds 250 kB");
  await put(t.key,payload,{
    access:"private",token,allowOverwrite:true,addRandomSuffix:false,
    contentType:"application/json",cacheControlMaxAge:60
  });
  state[t.key]={version:t.version,bars:bars.length,uploadedAt:new Date().toISOString()};
  save();
  done++;
  console.log("FUTURES_ARCHIVED",t.symbol,t.tf,"bars",bars.length,"source",t.sourceEventId.slice(0,50));
}
async function worker(queue){
  while(queue.length){
    const t=queue.shift();
    if(!t)break;
    try{await archive(t)}
    catch(e){errors++;console.error("FUTURES_ARCHIVE_ERROR",t.symbol,t.tf,e instanceof Error?e.message:"unexpected");}
  }
}
await Promise.all([worker(pending),worker(pending)]);
console.log("FUTURES_ARCHIVE_SUMMARY",JSON.stringify({
  events:groups.size,plans:tasks.length,attempted:pending.length,published:done,errors,
  remaining:tasks.filter(t=>state[t.key]?.version!==t.version).length
}));
if(errors)process.exitCode=1;
