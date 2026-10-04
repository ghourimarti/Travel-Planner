"""Langfuse auto-login - LOCAL DEVELOPMENT ONLY.

Opening http://localhost:<LANGFUSE_AUTOLOGIN_PORT> signs the browser into Langfuse as
the bootstrap admin (LANGFUSE_INIT_USER_*) and redirects to Langfuse. No form, no
typing: the Langfuse equivalent of Grafana's anonymous admin in this stack.

WHY IT EXISTS
-------------
Langfuse v3 has no anonymous or auto-login mode - every auth option it reads is SSO,
sign-up policy or session tuning. And `make upv` / `make downv` wipe its database, which
re-creates the admin user and invalidates every existing session. So "log in once" was
really "log in after every wipe".

HOW
---
It performs Langfuse's OWN email/password login server-side - NextAuth's public flow,
GET /api/auth/csrf then POST /api/auth/callback/credentials - and hands the browser the
session cookie Langfuse itself issued. It never forges a token, so it cannot drift from
Langfuse's token format across upgrades: it depends only on the public login endpoints.

WHY THIS WORKS FROM ANOTHER PORT: cookies are scoped by HOST, not by port. A cookie set
here for `localhost` is sent to Langfuse on localhost:3013 as well.

SECURITY
--------
Anyone who can open this URL is the Langfuse admin. That is acceptable ONLY because the
port is bound to 127.0.0.1 in compose (unreachable from the network) and the service is
not part of the Helm chart. Never deploy it anywhere.
"""

from __future__ import annotations

import html
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from http.client import HTTPResponse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

INTERNAL = os.environ.get("LANGFUSE_INTERNAL_URL", "http://langfuse-web:3000").rstrip("/")
PUBLIC = os.environ.get("LANGFUSE_PUBLIC_URL", "http://localhost:3013").rstrip("/")
EMAIL = os.environ.get("LANGFUSE_INIT_USER_EMAIL", "")
PASSWORD = os.environ.get("LANGFUSE_INIT_USER_PASSWORD", "")
SESSION_COOKIE = "next-auth.session-token"
TIMEOUT_S = 15


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Keep 3xx responses as they are: their Set-Cookie headers are the whole point."""

    def redirect_request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def _open(req: urllib.request.Request) -> HTTPResponse | urllib.error.HTTPError:
    try:
        return _opener.open(req, timeout=TIMEOUT_S)  # type: ignore[no-any-return]
    except urllib.error.HTTPError as err:  # 3xx/4xx still carry the headers we need
        return err


def _set_cookies(resp: HTTPResponse | urllib.error.HTTPError) -> dict[str, str]:
    """Cookie name -> the full Set-Cookie header value, attributes included."""
    return {h.split("=", 1)[0].strip(): h for h in (resp.headers.get_all("Set-Cookie") or [])}


def login() -> list[str]:
    """Run Langfuse's own email/password login; return its session Set-Cookie headers."""
    resp = _open(urllib.request.Request(f"{INTERNAL}/api/auth/csrf"))
    if resp.status != 200:
        raise ConnectionError(f"csrf endpoint answered HTTP {resp.status}")
    csrf_token = json.loads(resp.read())["csrfToken"]
    # NextAuth checks the body token against the csrf COOKIE, so send that cookie back.
    cookie_hdr = "; ".join(v.split(";", 1)[0] for v in _set_cookies(resp).values())

    body = urllib.parse.urlencode({
        "email": EMAIL,
        "password": PASSWORD,
        "csrfToken": csrf_token,
        "callbackUrl": f"{PUBLIC}/",
        "json": "true",
    }).encode()
    resp = _open(urllib.request.Request(
        f"{INTERNAL}/api/auth/callback/credentials",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Cookie": cookie_hdr},
    ))
    session = [v for k, v in _set_cookies(resp).items() if k.startswith(SESSION_COOKIE)]
    if not session:
        detail = resp.read(300).decode("utf-8", "replace")
        raise PermissionError(
            f"Langfuse refused the login for {EMAIL} (HTTP {resp.status}): {detail}"
        )
    return session


def _page(title: str, body: str, refresh: bool) -> bytes:
    meta = '<meta http-equiv="refresh" content="3">' if refresh else ""
    return (
        f"<!doctype html><meta charset=utf-8>{meta}<title>{html.escape(title)}</title>"
        f'<body style="font:15px system-ui;max-width:640px;margin:15vh auto;padding:0 1rem">'
        f"<h2>{html.escape(title)}</h2><p>{body}</p></body>"
    ).encode()


class Handler(BaseHTTPRequestHandler):
    server_version = "langfuse-autologin"

    def do_GET(self) -> None:  # noqa: N802 - the stdlib's name
        url = urllib.parse.urlsplit(self.path)
        if url.path == "/healthz":
            self._send(200, b"ok", "text/plain")
            return

        # ?next=/project/... lands on a specific page. Paths only - never an open redirect.
        nxt = urllib.parse.parse_qs(url.query).get("next", ["/"])[0]
        if not nxt.startswith("/") or nxt.startswith("//"):
            nxt = "/"

        try:
            cookies = login()
        except PermissionError as err:
            self._send(502, _page(
                "Langfuse rejected the auto-login",
                html.escape(str(err)) + "<br><br>Check LANGFUSE_INIT_USER_EMAIL / "
                "LANGFUSE_INIT_USER_PASSWORD in .env - they must match the admin Langfuse "
                "bootstrapped on its first boot.", refresh=False))
            return
        except (OSError, ValueError, KeyError) as err:  # not up yet, or answering garbage
            self._send(503, _page(
                "Langfuse is still starting...",
                f"This page retries every 3 seconds.<br><small>{html.escape(str(err))}</small>",
                refresh=True))
            return

        self.send_response(302)
        for c in cookies:
            self.send_header("Set-Cookie", c)
        # NextAuth splits a large session over name.0, name.1, ... and REASSEMBLES every
        # cookie sharing the prefix. A leftover piece from an older session would corrupt
        # the new one, so expire whichever variants this login did not just set.
        fresh = {c.split("=", 1)[0] for c in cookies}
        expire = "=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"
        for name in [SESSION_COOKIE] + [f"{SESSION_COOKIE}.{i}" for i in range(4)]:
            if name not in fresh:
                self.send_header("Set-Cookie", name + expire)
        self.send_header("Location", f"{PUBLIC}{nxt}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        print(f"auto-login: signed in {EMAIL} -> {PUBLIC}{nxt}", flush=True)

    def _send(self, status: int, body: bytes, ctype: str = "text/html; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:  # quiet: one line per login
        return


if __name__ == "__main__":
    if not (EMAIL and PASSWORD):
        raise SystemExit("LANGFUSE_INIT_USER_EMAIL and LANGFUSE_INIT_USER_PASSWORD must be set")
    print(f"langfuse-autologin ready: signs in {EMAIL}, then redirects to {PUBLIC}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()  # noqa: S104 - host binds 127.0.0.1
