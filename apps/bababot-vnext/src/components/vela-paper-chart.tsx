"use client";

import { useEffect, useRef, useState } from "react";
import type { StrongTrade } from "@/lib/strong-types";
import { CANDLE_INTERVALS, CANDLE_TIMEFRAMES, type CandleTimeframe, type PaperCandleResponse } from "@/lib/market-candles";

type ReplayState = { active: boolean; playing: boolean; cursorTime: number | null; remaining: number };
type VelaChart = import("@luxalgo/vela").Vela;
const fmtPrice = (n:number|null) => n == null ? "—" : n.toLocaleString("en-US",{maximumFractionDigits:10});
const fmtWib = (t:number|null) => t==null ? "—" : new Date(t).toLocaleString("id-ID",{timeZone:"Asia/Jakarta",day:"2-digit",month:"short",hour:"2-digit",minute:"2-digit"})+" WIB";
const fmtMoney = (n:number|null) => n == null ? "—" : (n>=0?"+":"−")+"$"+Math.abs(n).toFixed(2);

export default function VelaPaperChart({trade, matched}: {trade: StrongTrade; matched: StrongTrade[]}) {
  const [tf,setTf]=useState<CandleTimeframe>("5m");
  const [history,setHistory]=useState<PaperCandleResponse|null>(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState<string|null>(null);
  const [replay,setReplay]=useState<ReplayState>({active:false,playing:false,cursorTime:null,remaining:0});
  const host=useRef<HTMLDivElement>(null);
  const chartRef=useRef<VelaChart|null>(null);
  const [indicatorReady,setIndicatorReady]=useState(false);
  const [shown,setShown]=useState(0);

  // Fetch the *selected PAPER event*, not a ticker's unrelated latest market.
  useEffect(()=>{
    const ctrl=new AbortController();
    setHistory(null);setError(null);setLoading(true);setIndicatorReady(false);
    setReplay({active:false,playing:false,cursorTime:null,remaining:0});
    const params=new URLSearchParams({tradeId:trade.id,timeframe:tf});
    void fetch("/api/market/candles?"+params,{cache:"no-store",signal:ctrl.signal})
      .then(async res=>{
        const value=await res.json() as PaperCandleResponse & {error?:string};
        if(!res.ok) throw Error(value.error||"Market history request failed");
        if(value.symbol!==trade.symbol || value.timeframe!==tf ||
           value.market!=="BINANCE_USDT_FUTURES" || !Array.isArray(value.bars)) {
          throw Error("Market source mismatch");
        }
        if(!ctrl.signal.aborted){setHistory(value);setShown(value.bars.length);}
      })
      .catch(e=>{if(!ctrl.signal.aborted)setError(e instanceof Error?e.message:"Could not load futures candles");})
      .finally(()=>{if(!ctrl.signal.aborted)setLoading(false);});
    return ()=>ctrl.abort();
  },[trade.id,trade.symbol,tf]);

  useEffect(()=>{
    const el=host.current;
    if(!el||!history?.bars.length) return;
    let destroyed=false;
    let cleanup:()=>void=()=>{};
    let indicator: ReturnType<VelaChart["addNativeIndicator"]>|null=null;
    void (async()=>{
      const {Vela,registerNativeIndicator,unregisterNativeIndicator}=await import("@luxalgo/vela");
      if(destroyed || !host.current) return;
      const markerType="bababot-research-paper-trade";
      const bars=history.bars;
      const start=bars[0].time, end=bars.at(-1)!.time;
      let markerCutoff=Number.POSITIVE_INFINITY;
      const activeTrades=matched.filter(t=>t.symbol===trade.symbol && t.sourceEventId===trade.sourceEventId);
      const markerTrades=activeTrades.filter(t=>t.openedAtMs>=start && t.openedAtMs<=end+CANDLE_INTERVALS[tf]);
      registerNativeIndicator({
        type:markerType,title:"Recorded PAPER fills",shortTitle:"PAPER",paneHint:"price",overlay:true,
        inputsSchema:()=>[],defaultInputs:()=>({}),
        create:()=>({
          start(ctx) {
            const labels: Array<{
              id:string; paneId:string;xloc:"bar_time";x:number;y:number;yloc:"belowbar"|"abovebar";
              text:string;style:"triangleup"|"triangledown";color:string;textColor:string;
              size:"small";textAlign:"center";fontFamily:"default";overlay:boolean;
            }> = [];
            const lines:Array<{
              id:string;paneId:string;xloc:"bar_time";x1:number;y1:number;x2:number;y2:number;
              extend:"none";color:string;invisible:boolean;width:number;style:"dashed";
              arrowLeft:boolean;arrowRight:boolean;overlay:boolean;
            }>=[];
            for(const t of markerTrades) {
              const color=t.netPnl==null?"#8fb5dd":t.netPnl>=0?"#3ed4ae":"#f17c86";
              if(t.entryPrice!=null && t.openedAtMs<=markerCutoff) {
                labels.push({
                  id:t.id+":entry",paneId:"price",xloc:"bar_time",x:t.openedAtMs,y:t.entryPrice,
                  yloc:"belowbar",text:"▲ "+t.strategyId+" PAPER IN",style:"triangleup",color:"#31c7b7",
                  textColor:"#f1f6fb",size:"small",textAlign:"center",fontFamily:"default",overlay:true
                });
              }
              if(t.closedAtMs!=null && t.exitPrice!=null && t.closedAtMs<=markerCutoff) {
                labels.push({
                  id:t.id+":exit",paneId:"price",xloc:"bar_time",x:t.closedAtMs,y:t.exitPrice,
                  yloc:"abovebar",text:"▼ "+t.strategyId+" "+fmtMoney(t.netPnl),
                  style:"triangledown",color,
                  textColor:"#f1f6fb",size:"small",textAlign:"center",fontFamily:"default",overlay:true
                });
                if(t.entryPrice!=null && t.openedAtMs<=markerCutoff) {
                  lines.push({
                    id:t.id+":path",paneId:"price",xloc:"bar_time",
                    x1:t.openedAtMs,y1:t.entryPrice,x2:t.closedAtMs,y2:t.exitPrice,
                    extend:"none",color,invisible:false,width:1,style:"dashed",
                    arrowLeft:false,arrowRight:true,overlay:true
                  });
                }
              }
            }
            ctx.emit({lines,labels});ctx.setStatus("idle");
          },
          onBars(){},onViewport(){},setInputs(){},suspend(){},resume(){},stop(){}
        })
      });

      const chart=new Vela(el,{
        data:bars,timeframe:tf,theme:"dark",volume:true,
        priceStyle:"candles",drawings:true,live:false,
        animations:false,currentPriceLine:false,
        upColor:"#36c8a7",downColor:"#f07685",height:430,
        visibleRange:{
          from:Math.max(start,trade.openedAtMs-CANDLE_INTERVALS[tf]*30),
          to:Math.min(end, (trade.closedAtMs??trade.openedAtMs)+CANDLE_INTERVALS[tf]*20)
        }
      });
      chartRef.current=chart;
      const repaint=()=>{
        indicator?.remove();indicator=chart.addNativeIndicator(markerType);
      };
      repaint();
      const onStep=()=>{
        const s=chart.replay.state;
        markerCutoff=s.active && s.cursorTime!=null?s.cursorTime+CANDLE_INTERVALS[tf]-1:Number.POSITIVE_INFINITY;
        repaint();
        setReplay({active:s.active,playing:s.playing,cursorTime:s.cursorTime,remaining:s.remaining});
      };
      const onEnd=()=>{markerCutoff=Number.POSITIVE_INFINITY;repaint();setReplay({active:false,playing:false,cursorTime:null,remaining:0});};
      chart.on("replay:start",onStep);
      chart.on("replay:step",onStep);
      chart.on("replay:end",onEnd);
      await chart.ready();
      if(!destroyed){setIndicatorReady(true);setShown(bars.length);}
      cleanup=()=>{
        chart.replay.pause();
        chart.destroy();
        unregisterNativeIndicator(markerType);
        if(chartRef.current===chart)chartRef.current=null;
      };
      if(destroyed)cleanup();
    })().catch(e=>{if(!destroyed)setError(e instanceof Error?e.message:"Vela render error");});
    return ()=>{destroyed=true;cleanup();};
  },[history,trade.id,trade.openedAtMs,trade.closedAtMs,matched,tf]);

  async function startReplay(){
    const chart=chartRef.current;
    if(!chart||!history?.bars.length)return;
    const before=trade.openedAtMs-CANDLE_INTERVALS[tf]*12;
    const from=history.bars.filter(b=>b.time<=before).at(-1)?.time??history.bars[0].time;
    await chart.replay.start({from});
    const s=chart.replay.state;setReplay({active:s.active,playing:s.playing,cursorTime:s.cursorTime,remaining:s.remaining});
  }
  function oneStep(){
    const c=chartRef.current;if(!c)return;
    c.replay.step();const s=c.replay.state;
    setReplay({active:s.active,playing:s.playing,cursorTime:s.cursorTime,remaining:s.remaining});
  }
  function togglePlay(){
    const c=chartRef.current;if(!c)return;
    if(c.replay.state.playing)c.replay.pause();else c.replay.play(750);
    const s=c.replay.state;setReplay({active:s.active,playing:s.playing,cursorTime:s.cursorTime,remaining:s.remaining});
  }
  function stopReplay(){
    chartRef.current?.replay.stop();
    setReplay({active:false,playing:false,cursorTime:null,remaining:0});
  }

  return <section className="panel vela-panel">
    <div className="panel-head">
      <div><div className="section-eyebrow">VPS2 RESEARCH / FUTURES MARKET DATA</div>
        <h2>{trade.symbol} · Binance USDT-M Perpetual</h2>
        <p>True Futures OHLCV + recorded PAPER entry/exit annotations</p>
      </div><a className="vela-attribution" href="https://velacharts.dev" target="_blank" rel="noopener noreferrer">Charts by Vela™ · LuxAlgo ↗</a>
    </div>
    <div className="chart-controls">
      <div className="timeframes" aria-label="Chart timeframes">{CANDLE_TIMEFRAMES.map(t=>
        <button key={t} disabled={loading} onClick={()=>setTf(t)} className={tf===t?"selected":""} aria-pressed={tf===t}>{t}</button>)}</div>
      <span className="chart-marketsource">{history?.source==="vps2-archive"?"VPS2 MARKET ARCHIVE":history?.source==="binance-fapi"?"BINANCE FUTURES REST":"WAITING FOR FUTURES"}</span>
    </div>
    <div className="vela-host-wrap">
      <div ref={host} className="vela-canvas" aria-label="Vela candlestick chart with recorded PAPER transaction markers"/>
      {loading && <div className="chart-state">Loading real Binance Futures candles…</div>}
      {error && <div className="chart-state error"><strong>Market chart unavailable</strong><span>{error}</span><span>No fabricated candles shown.</span></div>}
    </div>
    {history && <div className="chart-replay-controls">
      <div className="replay-buttons">
        {!replay.active ? <button disabled={!indicatorReady || !history?.bars.length} onClick={()=>void startReplay()}>▶ Start replay</button>
          : <><button onClick={togglePlay}>{replay.playing?"Ⅱ Pause":"▶ Play"}</button><button onClick={oneStep} disabled={replay.playing}>Step +1 bar</button><button onClick={stopReplay}>Show full history</button></>}
      </div>
      <div className="replay-progress">{replay.active?<>Visible through <strong>{fmtWib(replay.cursorTime)}</strong> · {replay.remaining} bars hidden</>:
        <>{shown} verified candles · Full historical context</>}</div>
    </div>}
    <div className="chart-legend">
      <span><i className="swatch entry"/> PAPER ENTRY</span>
      <span><i className="swatch exit"/> PAPER EXIT / NET PnL</span>
      <span><i className="swatch candle"/> FUTURES CANDLE</span>
    </div>
    <div className="chart-trades">
      <div><small>Selected strategy</small><strong>{trade.strategyId}</strong></div>
      <div><small>PAPER entry</small><strong className="mono">{fmtPrice(trade.entryPrice)}</strong></div>
      <div><small>PAPER exit reference</small><strong className="mono">{fmtPrice(trade.exitPrice)}</strong></div>
      <div><small>Realized ledger PnL</small><strong className="mono">{fmtMoney(trade.netPnl)}</strong></div>
    </div>
    {history?.warning && <p className="chart-warning">{history.warning}</p>}
    <p className="microcopy">Candle source: Binance USDT-M Futures (historical OHLCV). PAPER annotations are sourced only from VPS2 ledgers; they are not exchange execution fills. Replay reveals closed candles one by one; it is not tick-level execution reconstruction. A 1m candle cannot prove intrabar event ordering.</p>
  </section>;
}
