import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/**
 * A deliberately disconnected stage-zero contract, not a VPS1 data reader.
 * Do not add exchange credentials or external network requests to this route.
 * Future connection requires separately approved VPS1 outbound exporter.
 */
export function GET() {
  return NextResponse.json({
    schemaVersion: 1,
    environment: "LIVE",
    source: "vps1",
    status: "NOT_CONNECTED",
    lastSourceSyncAt: null,
    snapshot: null,
    executionControlsEnabled: false,
    message: "LIVE workspace reserved. No VPS1 read integration has been configured."
  }, {
    headers: {
      "Cache-Control": "no-store, max-age=0",
      "X-Robots-Tag": "noindex"
    }
  });
}
