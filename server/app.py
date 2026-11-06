"""HTTP application for CHAOS FAMILY BATTLE.

One process owns the SQLite database and serves every player browser.
It binds to loopback by default; Cloudflare Quick Tunnel is the public ingress.
Only Python's standard library is required.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
import unicodedata
from collections import defaultdict, deque
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from .store import GameStore, InvalidInput, StoreError

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
COMPATIBILITY_FILE = ROOT / "compatibility" / "index.html"
COOKIE_NAME = "chaos_session"
MAX_REQUEST_BYTES = 8192


class MessageBus:
    """Small in-memory feed used only by the compatibility probe."""

    def __init__(self, limit: int = 100) -> None:
        self._items = deque(maxlen=limit)
        self._next_id = 1
        self._lock = threading.Lock()

    def publish(self, message: str) -> Dict[str, Any]:
        with self._lock:
            item = {"id": self._next_id, "message": message, "created_at": int(time.time())}
            self._next_id += 1
            self._items.append(item)
            return dict(item)

    def since(self, after_id: int) -> Dict[str, Any]:
        with self._lock:
            items = [dict(item) for item in self._items if item["id"] > after_id]
            latest_id = self._next_id - 1
        return {"ok": True, "messages": items, "latest_id": latest_id}


class RateLimiter:
    """Small in-memory sliding-window limiter for public room entry points."""

    def __init__(self) -> None:
        self._events = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, bucket: str, maximum: int, window_seconds: int) -> bool:
        now = time.monotonic()
        identity = bucket + ":" + key
        with self._lock:
            events = self._events[identity]
            while events and now - events[0] >= window_seconds:
                events.popleft()
            if len(events) >= maximum:
                return False
            events.append(now)
            return True


class ChaosHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _read_json(handler: BaseHTTPRequestHandler) -> Dict[str, Any]:
    raw_length = handler.headers.get("Content-Length", "0")
    try:
        length = int(raw_length)
    except (TypeError, ValueError):
        raise InvalidInput("حجم الطلب غير صحيح.")
    if length < 0 or length > MAX_REQUEST_BYTES:
        raise InvalidInput("حجم البيانات أكبر من الحد المسموح.")
    if length == 0:
        return {}
    try:
        value = json.loads(handler.rfile.read(length).decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise InvalidInput("تعذر قراءة بيانات الطلب.")
    if not isinstance(value, dict):
        raise InvalidInput("يجب إرسال بيانات بصيغة JSON object.")
    return value


def _session_from_cookie(handler: BaseHTTPRequestHandler) -> Optional[str]:
    cookie = SimpleCookie()
    try:
        cookie.load(handler.headers.get("Cookie", ""))
    except Exception:
        return None
    morsel = cookie.get(COOKIE_NAME)
    return morsel.value if morsel else None


def _safe_request_origin(handler: BaseHTTPRequestHandler) -> bool:
    """Reject cross-origin unsafe requests when a browser Origin is present."""
    origin = handler.headers.get("Origin")
    if not origin:
        return True
    parsed = urlparse(origin)
    host = handler.headers.get("Host", "").lower()
    return bool(parsed.netloc) and parsed.netloc.lower() == host and parsed.scheme in ("http", "https")


def make_handler(store: GameStore, message_bus: MessageBus, rate_limiter: RateLimiter):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ChaosFamilyBattle/1.0"
        sys_version = ""

        def log_message(self, format_string: str, *args: Any) -> None:
            # Never print cookies or request bodies.
            sys.stdout.write("[chaos-http] %s - %s\n" % (self.address_string(), format_string % args))
            sys.stdout.flush()

        def _rate_key(self) -> str:
            # cloudflared's loopback connection carries Cloudflare's client-IP header.
            # Never trust X-Forwarded-For supplied by an arbitrary browser.
            value = self.headers.get("CF-Connecting-IP", "").strip()
            if value and len(value) <= 64:
                return value
            return self.client_address[0]

        def _headers(self, content_type: str = "application/json; charset=utf-8", cache: str = "no-store") -> None:
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")

        def _json(
            self,
            status: int,
            payload: Dict[str, Any],
            session_token: Optional[str] = None,
            clear_cookie: bool = False,
        ) -> None:
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self._headers()
            if session_token:
                self.send_header(
                    "Set-Cookie",
                    "%s=%s; Path=/; Max-Age=604800; HttpOnly; Secure; SameSite=Lax" % (COOKIE_NAME, session_token),
                )
            elif clear_cookie:
                self.send_header(
                    "Set-Cookie",
                    "%s=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax" % COOKIE_NAME,
                )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _error(self, error: StoreError) -> None:
            self._json(error.status, {"ok": False, "code": error.code, "error": str(error)})

        def _static(self, file_path: Path, content_type: str) -> None:
            try:
                body = file_path.read_bytes()
            except OSError:
                self._json(500, {"ok": False, "error": "تعذر تحميل ملف الواجهة."})
                return
            self.send_response(200)
            self._headers(content_type, "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path

            if path in ("/", "/index.html"):
                self._static(WEB_DIR / "index.html", "text/html; charset=utf-8")
                return
            if path in ("/compatibility", "/compatibility/"):
                self._static(COMPATIBILITY_FILE, "text/html; charset=utf-8")
                return
            if path == "/static/main.css":
                self._static(WEB_DIR / "css" / "main.css", "text/css; charset=utf-8")
                return
            if path == "/static/app.js":
                self._static(WEB_DIR / "js" / "app.js", "application/javascript; charset=utf-8")
                return
            if path in ("/api/health", "/api/ping"):
                self._json(200, {
                    "ok": True,
                    "name": "CHAOS FAMILY BATTLE",
                    "python": sys.version.split()[0],
                    "server_time": int(time.time()),
                })
                return
            if path == "/api/messages":
                query = parse_qs(parsed.query)
                try:
                    after_id = int(query.get("after_id", ["0"])[0])
                except (TypeError, ValueError):
                    after_id = 0
                self._json(200, message_bus.since(max(0, after_id)))
                return
            if path == "/api/me":
                try:
                    session = store.get_session(_session_from_cookie(self))
                    self._json(200, store.public_session_snapshot(session))
                except StoreError as error:
                    self._error(error)
                return

            match = re.fullmatch(r"/api/rooms/([A-Za-z0-9]+)/?", path)
            if match:
                try:
                    room = store.get_room_for_session(match.group(1), _session_from_cookie(self))
                    self._json(200, {"ok": True, "room": room})
                except StoreError as error:
                    self._error(error)
                return

            self._json(404, {"ok": False, "code": "not_found", "error": "المسار المطلوب غير موجود."})

        def do_POST(self) -> None:
            if not _safe_request_origin(self):
                self._json(403, {"ok": False, "code": "origin_rejected", "error": "تم رفض مصدر الطلب."})
                return

            try:
                path = urlparse(self.path).path
                rate_key = self._rate_key()
                if path == "/api/rooms" and not rate_limiter.allow(rate_key, "create", 5, 600):
                    self._json(429, {
                        "ok": False,
                        "code": "rate_limited",
                        "error": "محاولات إنشاء الغرف كثيرة. انتظر قليلًا ثم حاول مجددًا.",
                    })
                    return
                if re.fullmatch(r"/api/rooms/[A-Za-z0-9]+/join", path) and not rate_limiter.allow(rate_key, "join", 15, 60):
                    self._json(429, {
                        "ok": False,
                        "code": "rate_limited",
                        "error": "محاولات الانضمام كثيرة. انتظر قليلًا ثم حاول مجددًا.",
                    })
                    return

                data = _read_json(self)
                current_token = _session_from_cookie(self)

                if path == "/api/messages":
                    message = data.get("message", "")
                    if not isinstance(message, str):
                        raise InvalidInput("الرسالة يجب أن تكون نصًا.")
                    message = "".join(
                        ch for ch in message if unicodedata.category(ch) not in ("Cc", "Cf", "Cs")
                    )
                    message = " ".join(message.split())
                    if not message or len(message) > 120:
                        raise InvalidInput("اكتب رسالة من حرف واحد إلى 120 حرفًا.")
                    item = message_bus.publish(message)
                    print("[chaos-message] %s" % message, flush=True)
                    self._json(201, {"ok": True, "stored_by_server": True, "message": item})
                    return

                if path == "/api/rooms":
                    result = store.create_room(data.get("name"), current_token)
                    self._json(
                        201,
                        {
                            "ok": True,
                            "player_id": result["player_id"],
                            "invite_code": result["invite_code"],
                            "room": result["room"],
                        },
                        session_token=result["session_token"],
                    )
                    return

                join_match = re.fullmatch(r"/api/rooms/([A-Za-z0-9]+)/join", path)
                if join_match:
                    result = store.join_room(join_match.group(1), data.get("name"), current_token)
                    self._json(
                        201,
                        {
                            "ok": True,
                            "player_id": result["player_id"],
                            "invite_code": result["invite_code"],
                            "room": result["room"],
                        },
                        session_token=result["session_token"],
                    )
                    return

                ready_match = re.fullmatch(r"/api/rooms/([A-Za-z0-9]+)/ready", path)
                if ready_match:
                    room = store.set_ready(ready_match.group(1), current_token, data.get("ready"))
                    self._json(200, {"ok": True, "room": room})
                    return

                leave_match = re.fullmatch(r"/api/rooms/([A-Za-z0-9]+)/leave", path)
                if leave_match:
                    store.leave_room(leave_match.group(1), current_token)
                    self._json(200, {"ok": True, "left": True}, clear_cookie=True)
                    return

                self._json(404, {"ok": False, "code": "not_found", "error": "المسار المطلوب غير موجود."})
            except StoreError as error:
                self._error(error)

        def do_OPTIONS(self) -> None:
            # No CORS is enabled; reject preflighted cross-origin requests explicitly.
            self._json(405, {"ok": False, "code": "method_not_allowed", "error": "الطريقة غير مسموحة."})

    return Handler


def create_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    database_path: Optional[str] = None,
) -> ChaosHTTPServer:
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("The CHAOS server must bind to loopback only.")
    store = GameStore(database_path)
    bus = MessageBus()
    limiter = RateLimiter()
    server = ChaosHTTPServer((host, port), make_handler(store, bus, limiter))
    server.chaos_store = store
    server.message_bus = bus
    server.rate_limiter = limiter
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the CHAOS FAMILY BATTLE local application server.")
    parser.add_argument("--host", default="127.0.0.1", help="loopback only; default 127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("CHAOS_PORT", "8765")))
    parser.add_argument("--database", default=None, help="optional SQLite path; default is outside the repository")
    args = parser.parse_args()

    if args.port < 1024 or args.port > 65535:
        parser.error("Choose a port between 1024 and 65535.")

    try:
        server = create_server(args.host, args.port, args.database)
    except (OSError, ValueError) as error:
        print("ERROR: %s" % error, file=sys.stderr)
        return 1

    print("", flush=True)
    print("CHAOS application server is running.", flush=True)
    print("Local origin: http://%s:%s/" % (args.host, args.port), flush=True)
    print("SQLite database: %s" % server.chaos_store.database_path, flush=True)
    print("Binding is loopback-only. Cloudflare Quick Tunnel provides remote access.", flush=True)
    print("Open /compatibility to run the shared-message network test.", flush=True)
    print("Press Ctrl+C to stop.", flush=True)

    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\nStopping CHAOS application server...", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
