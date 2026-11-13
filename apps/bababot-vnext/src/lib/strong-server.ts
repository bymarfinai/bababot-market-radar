import { get } from "@vercel/blob";
import { isStrongSnapshot, type StrongApiResponse, type StrongSnapshot } from "@/lib/strong-types";

const TIMEOUT_MS = 6500;
const STALE_MS = 20 * 60 * 1000;
const BLOB_PATH = "research/strong-paper/latest.json";

function readSnapshot(raw: string | undefined): StrongSnapshot | null {
  if (!raw) return null;
  try {
    const data: unknown = JSON.parse(raw);
    if (!isStrongSnapshot(data)) return null;
    const time = Date.parse(data.generatedAt);
    if (!Number.isFinite(time) || time > Date.now() + 60000) return null;
    return data;
  } catch {
    return null;
  }
}

function snapshotFallback(why?: string): StrongApiResponse {
  const fallback = readSnapshot(process.env.STRONG_PAPER_SNAPSHOT_JSON);
  return {
    mode: fallback ? "snapshot" : "unconfigured",
    snapshot: fallback,
    warning: why ?? (fallback
      ? "Menggunakan snapshot lama VPS2, bukan data PAPER tersinkron otomatis."
      : "VPS2 sync belum tersedia; private Blob belum berisi snapshot.")
  };
}

/** Server-side data only; browser never receives storage credentials. */
export async function loadStrongPaper(): Promise<StrongApiResponse> {
  const blobToken = process.env.BLOB_READ_WRITE_TOKEN?.trim();
  if (blobToken) {
    try {
      const result = await get(BLOB_PATH, {
        access: "private",
        token: blobToken,
        useCache: false
      });
      if (!result || result.statusCode !== 200 || !result.stream) {
        throw new Error("Private Blob snapshot missing.");
      }
      if (result.blob.size > 2_000_000) throw new Error("Unexpected snapshot size");
      const raw = await new Response(result.stream).text();
      const data = readSnapshot(raw);
      if (!data) throw new Error("Invalid VPS2 payload");
      const age = Date.now() - Date.parse(data.generatedAt);
      return {
        mode: "sync",
        snapshot: data,
        warning: age > STALE_MS
          ? "PAPER sync terlambat: snapshot terakhir lebih dari 20 menit. Periksa publisher VPS2."
          : null
      };
    } catch {
      return snapshotFallback("Private PAPER sync gagal dibaca. Menampilkan fallback jika tersedia.");
    }
  }

  // Optional direct HTTPS read service remains supported for other environments,
  // but is NOT enabled in this deployment and is never routed via VPS1.
  const url = process.env.STRONG_READ_API_URL?.trim();
  const bearer = process.env.STRONG_READ_API_TOKEN?.trim();
  if (url && bearer) {
    try {
      const parsed = new URL(url);
      if (parsed.protocol !== "https:" || parsed.username || parsed.password || parsed.hash) {
        throw new Error("Read API must be HTTPS");
      }
      const response = await fetch(parsed.toString(), {
        headers: { Authorization: `Bearer ${bearer}`, Accept: "application/json" },
        cache: "no-store",
        redirect: "error",
        signal: AbortSignal.timeout(TIMEOUT_MS)
      });
      if (!response.ok) throw new Error("Read API offline");
      const data = readSnapshot(await response.text());
      if (!data) throw new Error("Invalid read API payload");
      const age = Date.now() - Date.parse(data.generatedAt);
      return { mode: "sync", snapshot: data, warning: age > STALE_MS ? "PAPER data lebih dari 20 menit." : null };
    } catch {
      return snapshotFallback("Read API tidak dapat diakses; menggunakan fallback snapshot bila tersedia.");
    }
  }
  return snapshotFallback();
}
