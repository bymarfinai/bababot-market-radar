import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const root = new URL("../src/", import.meta.url);
const load = (file) => readFileSync(new URL(file, root), "utf8");

test("PAPER strategy selection is nested below environment selection", () => {
  const ui=load("components/strong-workspace.tsx");
  assert.match(ui,/LIVE · VPS1/);
  assert.match(ui,/PAPER · VPS2/);
  assert.match(ui,/STRONG LONG/);
  assert.match(ui,/Elliott Wave/);
  assert.match(ui,/setPaperStrategy/);
  assert.match(ui,/paperStrategy === "elliott-wave"/);
  assert.match(ui,/paperStrategy === "strong-long"/);
  assert.match(ui,/ElliottPaperWorkspace/);
  assert.match(ui,/sidebar-scroll/);
});
test("Elliott Wave placeholder does not consume STRONG LONG ledger or LIVE data", () => {
  const ui=load("components/elliott-paper-workspace.tsx");
  assert.match(ui,/No Elliott Wave PAPER ledger connected/);
  assert.match(ui,/awaiting EW ledger/);
  assert.doesNotMatch(ui,/StrongTrade|StrongSnapshot|\/api\/strong|\/api\/live|fetch\(|window\.location/);
});
test("EW PAPER status is null and never copied from STRONG LONG source", () => {
  const api=load("app/api/paper/elliott/status/route.ts");
  assert.match(api,/status: "NOT_CONNECTED"/);
  assert.match(api,/snapshot: null/);
  assert.match(api,/source: "vps2-elliott-wave"/);
  assert.doesNotMatch(api,/function POST\(|function PUT\(|function DELETE\(|fetch\(|axios|BLOB_READ_WRITE_TOKEN/);
});
