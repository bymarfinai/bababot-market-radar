import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json(
    { service: "bababot-vnext", ok: true, researchReadOnly: true, controlsEnabled: false },
    { headers: { "Cache-Control": "no-store" } }
  );
}
