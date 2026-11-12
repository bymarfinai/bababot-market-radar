#!/usr/bin/env node
/**
 * VPS2-only read-only SQLite -> Vercel private Blob publisher.
 *
 * Never runs on VPS1. One read per service invocation; zero DB writes.
 * Stores one overwriteable private JSON object and avoids uploads if identical.
 */
import { put } from "@vercel/blob";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const cwd = process.cwd();
const root = process.env.STRONG_EXPORT_ROOT || "/home/ubuntu/market-detektor-research";
const exporter = process.env.STRONG_EXPORT_SCRIPT || path.join(cwd, "export-strong-vps2.py");
const stateFolder = process.env.STRONG_SYNC_STATE_DIR || path.join(cwd, "state");
const statePath = path.join(stateFolder, "publish-state.json");
const BLOB_PATH = "research/strong-paper/latest.json";
const HEARTBEAT_MS = 10 * 60 * 1000;
const knownIds = new Set(["A","P01","P02","P03","P04","P05","P06","P07","M01","M02","M03","M04","M05"]);

function die(message) { console.error("paper-sync-error:", message); process.exitCode = 1; }
function parsePrevious() {
  try { return JSON.parse(fs.readFileSync(statePath, "utf8")); } catch { return {}; }
}
async function main() {
  const token = process.env.BLOB_READ_WRITE_TOKEN;
  if (!token || token.length < 20) throw new Error("Missing private Blob credential");
  const output = execFileSync("/usr/bin/python3", [exporter, "--root", root], {
    encoding: "utf8", maxBuffer: 2_000_000, timeout: 18_000,
    env: { PATH: process.env.PATH || "/usr/bin:/bin", LANG: "C.UTF-8" }
  });
  const doc = JSON.parse(output);
  if (doc.schemaVersion !== 1 || doc.origin !== "vps2-independent-paper" ||
      !Array.isArray(doc.trades) || !Array.isArray(doc.strategies) ||
      doc.strategies.length !== knownIds.size ||
      doc.strategies.some(s => !knownIds.has(s.id)) ||
      doc.trades.some(t => !knownIds.has(t.strategyId) || !t.sourceEventId)) {
    throw new Error("Exporter schema or strategy mapping mismatch");
  }
  if (new Set(doc.trades.map(t => t.id)).size !== doc.trades.length) {
    throw new Error("Duplicate trade identities");
  }
  if (doc.trades.length > 20000) throw new Error("Unexpected large payload");
  const { generatedAt, ...comparison } = doc;
  const fingerprint = createHash("sha256").update(JSON.stringify(comparison)).digest("hex");
  const previous = parsePrevious();
  const now = Date.now();
  if (previous.fingerprint === fingerprint &&
      Number.isFinite(previous.uploadedAtMs) &&
      now - previous.uploadedAtMs < HEARTBEAT_MS) {
    console.log("PAPER_SYNC_UNCHANGED", JSON.stringify({
      checkedAt: new Date(now).toISOString(),
      trades: doc.trades.length, strategies: doc.strategies.length
    }));
    return;
  }

  const body = JSON.stringify(doc);
  if (Buffer.byteLength(body) > 2_000_000) throw new Error("Blob payload exceeds 2MB");
  await put(BLOB_PATH, body, {
    access: "private",
    token,
    addRandomSuffix: false,
    allowOverwrite: true,
    cacheControlMaxAge: 60,
    contentType: "application/json"
  });
  fs.mkdirSync(stateFolder, { recursive: true, mode: 0o700 });
  const tmp = statePath + ".tmp";
  fs.writeFileSync(tmp, JSON.stringify({
    fingerprint, uploadedAtMs: now,
    trades: doc.trades.length, strategies: doc.strategies.length,
    snapshotGeneratedAt: generatedAt
  }), { encoding: "utf8", mode: 0o600 });
  fs.renameSync(tmp, statePath);
  console.log("PAPER_SYNC_PUBLISHED", JSON.stringify({
    generatedAt, trades: doc.trades.length, strategies: doc.strategies.length
  }));
}
main().catch(e => die(e instanceof Error ? e.name + ": " + e.message : "unknown"));
