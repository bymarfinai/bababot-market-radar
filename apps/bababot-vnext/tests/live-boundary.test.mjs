import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";

const root = new URL("../src/", import.meta.url);
const load = (p) => readFileSync(new URL(p, root), "utf8");

test("LIVE API is a disconnected read-only stub with no order route or outbound request", () => {
  const api=load("app/api/live/status/route.ts");
  assert.match(api,/status: "NOT_CONNECTED"/);
  assert.match(api,/snapshot: null/);
  assert.match(api,/executionControlsEnabled: false/);
  assert.match(api,/function GET\(/);
  assert.doesNotMatch(api,/function POST\(|function PUT\(|function DELETE\(|fetch\(|axios|BLOB_READ_WRITE_TOKEN|BINANCE_/);
});
test("LIVE UI does not import or use PAPER trades or fetch VPS1/exchange API",()=>{
  const ui=load("components/live-workspace.tsx");
  assert.match(ui,/not been connected yet/);
  assert.match(ui,/No VPS1 data connected/);
  assert.match(ui,/No Binance keys/);
  assert.doesNotMatch(ui,/StrongTrade|StrongSnapshot|useStrong|\/api\/strong|fetch\(|api\.binance\.com|window\.location/);
});
test("workspace switch and navigation visually separate LIVE and RESEARCH",()=>{
  const ui=load("components/strong-workspace.tsx");
  assert.match(ui,/LIVE · VPS1/);
  assert.match(ui,/RESEARCH · VPS2/);
  assert.match(ui,/LiveWorkspace/);
  assert.match(ui,/setWorkspaceMode/);
  assert.match(ui,/workspaceMode === "live"/);
  assert.match(ui,/sidebar-scroll/);
});
