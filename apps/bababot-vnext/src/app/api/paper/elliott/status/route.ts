import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** EW PAPER is deliberately not wired to any STRONG LONG or VPS1 source. */
export function GET() {
  return NextResponse.json({
    schemaVersion: 1,
    environment: "PAPER",
    source: "vps2-elliott-wave",
    strategy: "elliott-wave",
    status: "NOT_CONNECTED",
    lastSourceSyncAt: null,
    snapshot: null,
    message: "Elliott Wave PAPER ledger integration has not been configured."
  }, {headers: {"Cache-Control": "no-store, max-age=0", "X-Robots-Tag": "noindex"}});
}
