import { NextRequest, NextResponse } from "next/server";
import { get } from "@vercel/blob";
import { createHash } from "node:crypto";
import { loadStrongPaper } from "@/lib/strong-server";
import {
  CANDLE_INTERVALS, type CandleTimeframe, marketWindow, parseBinanceKlines,
  type PaperCandleResponse, type Ohlcv
} from "@/lib/market-candles";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const LIMIT = 1000;
function noStore(response: unknown, status = 200) {
  return NextResponse.json(response, {status, headers: {
    "Cache-Control":"private, no-store, max-age=0",
    "X-Content-Type-Options":"nosniff"
  }});
}

function archiveKey(sourceEventId: string, timeframe: CandleTimeframe): string {
  const hash = createHash("sha256").update(sourceEventId, "utf8").digest("hex");
  return \`research/strong-candles/\${timeframe}/\${hash}.json\`;
}
async function readPrivateArchive(key:string, token:string): Promise<unknown | null> {
  try {
    const blob = await get(key, { access:"private", token, useCache:false });
    if (!blob || blob.statusCode!==200 || !blob.stream || blob.blob.size>250000) return null;
    return JSON.parse(await new Response(blob.stream).text());
  } catch { return null; }
}

export async function GET(req: NextRequest) {
  const q=req.nextUrl.searchParams;
  const tradeId=q.get("tradeId")??"";
  const timeframe=q.get("timeframe")??"5m";
  if (tradeId.length>240 || !/^(1m|5m|15m|1h|4h)$/.test(timeframe)) {
    return noStore({error:"Invalid trade/timeframe selection"},400);
  }
  const tf=timeframe as CandleTimeframe;
  const paper=await loadStrongPaper();
  const trade=paper.snapshot?.trades.find(x=>x.id===tradeId);
  if (!trade || !/^[A-Z0-9]{3,24}USDT$/.test(trade.symbol)) {
    return noStore({error:"Trade not found in authorized VPS2 PAPER snapshot"},404);
  }
  const {startTime,endTime}=marketWindow(tf,trade.openedAtMs,trade.closedAtMs);
  const symbol=trade.symbol;
  if (endTime<=startTime) return noStore({error:"Invalid research time window"},400);

  let bars: Ohlcv[] | null = null;
  let source: PaperCandleResponse["source"] = "binance-fapi";
  const token=process.env.BLOB_READ_WRITE_TOKEN?.trim();

  // Favor immutable VPS2 archive when available: Binance Futures REST is
  // geo-blocked from some Vercel deployment regions.
  if(token){
    const archived=await readPrivateArchive(archiveKey(trade.sourceEventId,tf),token);
    if(archived && typeof archived==="object" && "bars" in archived &&
       Array.isArray(archived.bars) && "symbol" in archived &&
       archived.symbol===symbol && "timeframe" in archived && archived.timeframe===tf &&
       "market" in archived && archived.market==="BINANCE_USDT_FUTURES") {
      try {
        const checked=archived.bars as Ohlcv[];
        if(checked.length>0 && checked.length<=1000) {
          const parsed=parseBinanceKlines(checked.map(b=>[b.time,b.open,b.high,b.low,b.close,b.volume]));
          if(parsed.length===checked.length &&
             parsed.every(b=>b.time>=startTime-CANDLE_INTERVALS[tf] && b.time<=endTime+CANDLE_INTERVALS[tf])) {
            bars=parsed;
            source="vps2-archive";
          }
        }
      } catch { /* ignore invalid private object */ }
    }
  }

  if(!bars) {
    const url=new URL("https://fapi.binance.com/fapi/v1/klines");
    url.searchParams.set("symbol",symbol);
    url.searchParams.set("interval",tf);
    url.searchParams.set("startTime",String(startTime));
    url.searchParams.set("endTime",String(endTime));
    url.searchParams.set("limit",String(LIMIT));
    try {
      const res=await fetch(url, {cache:"no-store",redirect:"error",signal:AbortSignal.timeout(8500)});
      if(!res.ok) throw Error("fapi-"+res.status);
      bars=parseBinanceKlines(await res.json());
    } catch {
      return noStore({
        error:"Binance Futures candles unavailable in this region. VPS2 archive is required.",
        symbol,timeframe:tf,source:"binance-fapi"
      },503);
    }
  }
  if(!bars || bars.length===0) return noStore({error:"No verified futures candles returned",symbol,timeframe:tf},404);
  const result:PaperCandleResponse={
    market:"BINANCE_USDT_FUTURES",symbol,timeframe:tf,bars,tradeId:trade.id,
    fromMs:startTime,toMs:endTime,source,fetchedAt:new Date().toISOString(),
    warning:bars.length===LIMIT?"1000-bar API limit reached; check historical coverage.":null
  };
  return noStore(result);
}
