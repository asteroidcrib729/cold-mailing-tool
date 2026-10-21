"""Bounded system-browser authorization with a loopback-only callback."""

from __future__ import annotations

import secrets
import time
import webbrowser
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event
from urllib.parse import parse_qs, urlsplit

from cold_mailer.domain.models import ValidationError


def callback_values(target: str, path: str, state: str) -> dict[str, str] | None:
    parsed = urlsplit(target)
    if (
        parsed.path != path
        or parsed.netloc
        or parsed.scheme
        or parsed.fragment
        or len(target) > 8192
    ):
        return None
    values = parse_qs(parsed.query, max_num_fields=10)
    if any(len(value) != 1 for value in values.values()):
        return None
    supplied = values.get("state", [""])[0]
    if not supplied.isascii() or not secrets.compare_digest(supplied, state):
        return None
    if "error" in values:
        return {"error": "authorization_declined", "state": supplied}
    code = values.get("code", [""])[0]
    if not code or len(code) > 4096:
        return None
    return {"code": code, "state": supplied}


def authorize_in_browser(
    authorize: Callable[[str, str], str],
    stop: Event,
    *,
    timeout: float = 180,
    loopback_host: str = "127.0.0.1",
) -> tuple[str, dict[str, str]]:
    if stop.is_set():
        raise ValidationError("Sign-in was cancelled.")
    if loopback_host not in {"127.0.0.1", "localhost"}:
        raise ValidationError("Authorization callbacks must stay on the local loopback interface.")
    state, path = secrets.token_urlsafe(32), "/oauth/callback"
    result: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def setup(self) -> None:
            self.request.settimeout(1)
            super().setup()

        def log_message(self, format: str, *args: object) -> None:
            pass  # Authorization codes and query strings must never be logged.

        def do_GET(self) -> None:
            try:
                values = callback_values(self.path, path, state)
            except ValueError:
                values = None
            expected = f"{loopback_host}:{server.server_port}"
            if self.headers.get("Host") != expected or values is None:
                self.send_error(400, "Invalid authorization callback")
                return
            result.update(values)
            body = b"You can close this tab and return to Cold Mailer."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'none'")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    with HTTPServer(("127.0.0.1", 0), Handler) as server:
        server.timeout = 0.25
        redirect = f"http://{loopback_host}:{server.server_port}{path}"
        url = authorize(redirect, state)
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {"accounts.google.com", "login.microsoftonline.com"}
            or not webbrowser.open(url, new=1)
        ):
            raise ValidationError("Could not open the provider's sign-in page in your browser.")
        deadline = time.monotonic() + timeout
        while not result and not stop.is_set() and time.monotonic() < deadline:
            server.handle_request()
    if stop.is_set():
        raise ValidationError("Sign-in was cancelled.")
    if not result:
        raise ValidationError("Sign-in timed out. Start again when you are ready.")
    if "error" in result:
        raise ValidationError("Sign-in or sending permission was declined.")
    return redirect, result
