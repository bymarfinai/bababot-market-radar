import { NextResponse } from "next/server";
import { loadStrongPaper } from "@/lib/strong-server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const result = await loadStrongPaper();
  return NextResponse.json(result, {
    headers: {
      "Cache-Control": "private, no-store, max-age=0",
      "X-Content-Type-Options": "nosniff"
    }
  });
}
