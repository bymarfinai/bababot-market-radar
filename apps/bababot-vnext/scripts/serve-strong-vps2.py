#!/usr/bin/env python3
"""Authenticated, read-only HTTP source for BabaBot vNext.

Bind only to the private VPS2 WireGuard address. Does not write to ledgers,
send orders, or expose controls. Public access MUST pass through an HTTPS
reverse proxy and a server-only Bearer token.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import importlib.util
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

EXPORTER = Path(__file__).with_name("export-strong-vps2.py")
spec = importlib.util.spec_from_file_location("bababot_strong_exporter", EXPORTER)
if spec is None or spec.loader is None:
    raise RuntimeError("Could not initialize read-only exporter")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def make_handler(root: Path, token: str):
    expected = "Bearer " + token

    class ReadOnlyHandler(BaseHTTPRequestHandler):
        server_version = "BabaBotResearchRead/1"
        sys_version = ""

        def reply(self, status: int, payload: dict, allowed: str | None = None):
            body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "private, no-store, max-age=0")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            if allowed:
                self.send_header("Allow", allowed)
            self.end_headers()
            self.wfile.write(body)

        def authorize(self) -> bool:
            supplied = self.headers.get("Authorization", "")
            if not hmac.compare_digest(supplied, expected):
                self.reply(401, {"error": "unauthorized"})
                return False
            return True

        def do_GET(self):
            path = urlsplit(self.path).path
            if path not in ("/v1/strong", "/health"):
                self.reply(404, {"error": "not_found"})
                return
            if not self.authorize():
                return
            if path == "/health":
                self.reply(200, {"ok": True, "source": "vps2", "readOnly": True})
                return
            try:
                snapshot = module.normalize(root)
                self.reply(200, snapshot)
            except (OSError, ValueError, Exception) as exc:
                # Return no filesystem details, raw SQLite errors or table contents.
                print("snapshot_error", type(exc).__name__, file=sys.stderr, flush=True)
                self.reply(503, {"error": "snapshot_unavailable"})

        def do_POST(self):
            self.reply(405, {"error": "read_only"}, "GET")

        def do_PUT(self):
            self.reply(405, {"error": "read_only"}, "GET")

        def do_DELETE(self):
            self.reply(405, {"error": "read_only"}, "GET")

        def log_message(self, fmt, *args):
            # Avoid logging Authorization values or sensitive payloads.
            print("strong-read", self.address_string(), fmt % args, file=sys.stderr, flush=True)

    return ReadOnlyHandler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="10.77.22.2")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--root", type=Path, default=Path("/home/ubuntu/market-detektor-research"))
    args = parser.parse_args()
    token = os.environ.get("STRONG_READ_TOKEN", "")
    if len(token) < 40:
        raise SystemExit("STRONG_READ_TOKEN must be set and >=40 characters")
    if not args.root.is_dir():
        raise SystemExit("Research root missing")
    if args.bind in ("0.0.0.0", "::"):
        raise SystemExit("Public interface binding prohibited")
    server = ThreadingHTTPServer((args.bind, args.port), make_handler(args.root, token))
    server.daemon_threads = True
    print(f"strong-read listening on {args.bind}:{args.port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
