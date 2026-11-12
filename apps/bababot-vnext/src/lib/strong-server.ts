import { isStrongSnapshot, type StrongApiResponse, type StrongSnapshot } from "@/lib/strong-types";

const TIMEOUT_MS = 6500;

function readSnapshot(raw: string | undefined): StrongSnapshot | null {
  if (!raw) return null;
  try {
    const data: unknown = JSON.parse(raw);
    return isStrongSnapshot(data) ? data : null;
  } catch {
    return null;
  }
}

/** All sources are server-only. Nothing calls VPS2 directly from the browser. */
export async function loadStrongPaper(): Promise<StrongApiResponse> {
  const url = process.env.STRONG_READ_API_URL?.trim();
  const bearer = process.env.STRONG_READ_API_TOKEN?.trim();
  if (url && bearer) {
    try {
      const parsed = new URL(url);
      if (parsed.protocol !== "https:" || parsed.username || parsed.password || parsed.hash) {
        throw new Error("Read API must use HTTPS.");
      }
      const response = await fetch(parsed.toString(), {
        headers: {
          Authorization: `Bearer ${bearer}`,
          Accept: "application/json",
        },
        cache: "no-store",
        redirect: "error",
        signal: AbortSignal.timeout(TIMEOUT_MS),
      });
      if (!response.ok) throw new Error("Read API unavailable");
      const raw: unknown = await response.json();
      if (!isStrongSnapshot(raw)) throw new Error("Read API schema mismatch");
      return { mode: "live", snapshot: raw, warning: null };
    } catch {
      const cached = readSnapshot(process.env.STRONG_PAPER_SNAPSHOT_JSON);
      return {
        mode: cached ? "snapshot" : "unconfigured",
        snapshot: cached,
        warning: "Koneksi live VPS2 belum tersedia; fallback snapshot digunakan bila ada."
      };
    }
  }
  const cached = readSnapshot(process.env.STRONG_PAPER_SNAPSHOT_JSON);
  return {
    mode: cached ? "snapshot" : "unconfigured",
    snapshot: cached,
    warning: cached
      ? "Data merupakan snapshot VPS2, bukan streaming live."
      : "Sumber data belum dikonfigurasi. Set STRONG_READ_API_URL + TOKEN atau STRONG_PAPER_SNAPSHOT_JSON di Vercel Preview."
  };
}
