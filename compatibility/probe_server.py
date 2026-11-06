#!/usr/bin/env python3
"""
Small compatibility test server for CHAOS FAMILY BATTLE.

Uses only the Python standard library. It serves compatibility/index.html
and two JSON endpoints. It binds to localhost by default so Cloudflare
Quick Tunnel is the only remote entry point.
"""

import argparse
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
INDEX_FILE = ROOT / "index.html"
MAX_BODY_BYTES = 8192


class ProbeHandler(BaseHTTPRequestHandler):
    server_version = "ChaosCompatibilityProbe/1.0"

    def log_message(self, format_string, *args):
        # Keep logs short; do not print request bodies or session-like values.
        sys.stdout.write("%s - %s\n" % (self.address_string(), format_string % args))

    def send_json(self, status_code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/" or path == "/index.html":
            try:
                body = INDEX_FILE.read_bytes()
            except OSError:
                self.send_error(500, "Compatibility page is missing")
                return

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/ping":
            self.send_json(200, {
                "ok": True,
                "name": "CHAOS compatibility probe",
                "python": sys.version.split()[0],
                "server_time": int(time.time()),
            })
            return

        self.send_error(404, "Not found")

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/echo":
            self.send_error(404, "Not found")
            return

        content_length = self.headers.get("Content-Length", "")
        try:
            body_size = int(content_length)
        except (TypeError, ValueError):
            self.send_json(400, {"ok": False, "error": "Invalid content length"})
            return

        if body_size < 1 or body_size > MAX_BODY_BYTES:
            self.send_json(413, {"ok": False, "error": "Request body size is not allowed"})
            return

        try:
            raw_body = self.rfile.read(body_size)
            data = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            self.send_json(400, {"ok": False, "error": "Invalid JSON"})
            return

        if not isinstance(data, dict):
            self.send_json(400, {"ok": False, "error": "JSON object required"})
            return

        message = data.get("message", "")
        if not isinstance(message, str):
            self.send_json(400, {"ok": False, "error": "Message must be text"})
            return

        message = message[:200]
        self.send_json(200, {
            "ok": True,
            "received": message,
            "length": len(message),
            "server_time": int(time.time()),
        })


def main():
    parser = argparse.ArgumentParser(description="Run the CHAOS compatibility probe.")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="bind address; default is localhost only (127.0.0.1)",
    )
    parser.add_argument("--port", type=int, default=8765, help="TCP port; default: 8765")
    args = parser.parse_args()

    if args.port < 1024 or args.port > 65535:
        parser.error("Choose a port between 1024 and 65535.")

    try:
        server = ThreadingHTTPServer((args.host, args.port), ProbeHandler)
    except OSError as error:
        print("Could not start the server on %s:%s: %s" % (args.host, args.port, error))
        print("Check whether the address is available and the port is already in use.")
        return 1

    server.daemon_threads = True
    print("")
    print("CHAOS compatibility probe is running.")
    print("Local origin: http://%s:%s/" % (args.host, args.port))
    print("Remote access is provided only by the Cloudflare tunnel process.")
    print("Stop the server with Ctrl+C.")
    print("")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping compatibility probe...")
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
