"""Small local-only HTTP adapter. It never executes infrastructure actions."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib.resources import files
import json
import secrets
from urllib.parse import urlsplit

from .engine import RehearsalError, Session, load_scenario

MAX_BODY = 16_384


def create_server(scenario_id: str, host: str = "127.0.0.1", port: int = 0) -> HTTPServer:
    # Deliberately exclude names that can resolve unexpectedly and wildcard interfaces.
    if host != "127.0.0.1":
        raise RehearsalError("Only the literal loopback address 127.0.0.1 is supported")
    session = Session(load_scenario(scenario_id))
    token = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(20)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def log_message(self, format, *args):
            pass  # Rationale and evidence are not written to access logs.

        def reply(self, status: int, body, content_type="application/json; charset=utf-8"):
            encoded = json.dumps(body).encode() if content_type.startswith("application/json") else body.encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(encoded)

        def same_host(self) -> bool:
            expected = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get_all("Host") != [expected]:
                self.reply(421, {"error": "Unexpected Host"})
                return False
            return True

        def do_GET(self):
            if not self.same_host():
                return
            try:
                parsed = urlsplit(self.path)
            except ValueError:
                self.reply(400, {"error": "Malformed request target"})
                return
            if parsed.query or parsed.fragment or parsed.scheme or parsed.netloc:
                self.reply(404, {"error": "Unknown resource"})
            elif parsed.path == "/":
                html = files(__package__).joinpath("ui.html").read_text()
                self.reply(200, html.replace("__TOKEN__", token).replace("__NONCE__", nonce), "text/html; charset=utf-8")
            elif parsed.path == "/api/state":
                self.reply(200, session.state())
            elif parsed.path == "/api/export":
                try:
                    self.reply(200, session.debrief())
                except RehearsalError as exc:
                    self.reply(409, {"error": str(exc)})
            else:
                self.reply(404, {"error": "Unknown resource"})

        def do_POST(self):
            if not self.same_host():
                return
            expected_origin = f"http://127.0.0.1:{self.server.server_port}"
            if (self.headers.get_all("Origin") != [expected_origin]
                    or self.headers.get_all("X-Rehearsal-Token") != [token]):
                self.reply(403, {"error": "Same-origin token required"})
                return
            if self.headers.get("Transfer-Encoding") is not None:
                self.reply(400, {"error": "Transfer-Encoding is not supported"})
                return
            if self.headers.get_all("Content-Type") != ["application/json"]:
                self.reply(415, {"error": "Content-Type must be application/json"})
                return
            lengths = self.headers.get_all("Content-Length") or []
            if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
                self.reply(411, {"error": "One Content-Length is required"})
                return
            if len(lengths[0]) > 6:
                self.reply(413, {"error": "Request body exceeds 16 KiB"})
                return
            length = int(lengths[0])
            if length > MAX_BODY:
                self.reply(413, {"error": "Request body exceeds 16 KiB"})
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise RehearsalError("JSON body must be an object")
                if self.path == "/api/advance":
                    if set(payload) != {"minutes"}:
                        raise RehearsalError("Expected only minutes")
                    result = session.advance(payload["minutes"])
                elif self.path == "/api/decide":
                    if set(payload) - {"action_id", "evidence_ids", "rationale", "approval"}:
                        raise RehearsalError("Unknown decision field")
                    result = session.decide(**payload)
                elif self.path == "/api/finish":
                    if payload:
                        raise RehearsalError("Finish body must be empty")
                    result = session.finish()
                else:
                    self.reply(404, {"error": "Unknown resource"})
                    return
                self.reply(200, result)
            except (RehearsalError, TypeError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
                self.reply(400, {"error": str(exc)})

    server = HTTPServer((host, port), Handler)
    server.timeout = 1
    # Bound idle clients so one malformed request cannot retain the sole handler forever.
    server.get_request_original = server.get_request
    def get_request():
        sock, address = server.get_request_original()
        sock.settimeout(3)
        return sock, address
    server.get_request = get_request
    return server
