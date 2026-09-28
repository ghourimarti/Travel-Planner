"""Auth consent diagnostic: read the REAL authorize request and name what forces consent.

The "Authorize App" screen kept reappearing on every plan. Five hypotheses were
eliminated by checking rather than asserting:

  1. audience  -> a custom API audience forces consent. REMOVED; verified gone from the
                  live /authorize URL.
  2. offline_access -> a refresh-token scope also forces consent. REMOVED; verified.
  3. the SDK reads AUTH0_AUDIENCE from env by itself -> it does NOT (it reads
     AUTH0_DOMAIN / CLIENT_ID / SECRET / cookie / DPoP vars, never AUDIENCE).
  4. the session cookie is marked Secure over plain http, so the browser drops it ->
     the SDK derives `secure` from the appBaseUrl protocol, which is http here, so false.
  5. the app is third-party -> could not be read: this client is not authorized for the
     Management API.

What remains is decided in the BROWSER, not in this repo, so this script prints the
evidence and the one test that separates the last two causes.
"""

from __future__ import annotations

import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

WEB = f"http://localhost:{os.environ.get('WEB_PORT', '3006')}"
BASE_URL = os.environ.get("APP_BASE_URL", "(unset)")


def authorize_params() -> dict[str, str]:
    """Follow /auth/login WITHOUT redirecting and read the Location it hands back."""
    req = urllib.request.Request(f"{WEB}/auth/login")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):  # noqa: ANN002, ANN003
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        opener.open(req, timeout=15)
        return {}
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location", "")
        if not loc:
            return {}
        q = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)
        return {k: v[0] for k, v in q.items()}
    except Exception as e:  # noqa: BLE001
        print(f"  could not reach {WEB}/auth/login: {e}")
        return {}


def main() -> int:
    print("\nAUTH CONSENT DOCTOR")
    print("=" * 72)

    p = authorize_params()
    if not p:
        print("  No authorize redirect. Is the web tier up, and is Auth0 configured?")
        return 1

    aud = p.get("audience")
    scope = p.get("scope", "")
    prompt = p.get("prompt")

    print("\n  What the app actually sends to Auth0:")
    print(f"    audience : {aud or '(none)'}")
    print(f"    scope    : {scope or '(none)'}")
    print(f"    prompt   : {prompt or '(none)'}")
    print(f"    base URL : {BASE_URL}")

    forces = []
    if aud:
        forces.append("audience -> an API access token always requires consent")
    if "offline_access" in scope:
        forces.append("offline_access -> a refresh token requires consent")
    if prompt == "consent":
        forces.append("prompt=consent -> consent is being requested explicitly")

    print("\n  Things in THIS REPO that would force consent:")
    if forces:
        for f in forces:
            print(f"    STILL PRESENT: {f}")
    else:
        print("    none - this is a plain first-party OIDC request")

    localhost = "localhost" in BASE_URL or "127.0.0.1" in BASE_URL
    print("\n  The localhost rule, stated precisely:")
    if forces and localhost:
        print("    Consent is being REQUESTED above, and APP_BASE_URL is localhost, where")
        print("    Auth0 cannot skip it: it has no way to verify the app's identity there,")
        print("    so 'remember this decision' is unavailable. Remove the cause above, or")
        print("    serve the app from a real hostname.")
    elif localhost:
        print("    APP_BASE_URL is localhost, BUT nothing above is requesting consent.")
        print("    The localhost rule governs whether consent can be SKIPPED once it is")
        print("    required - it does NOT create a prompt on its own. A first-party app")
        print("    making a plain openid/profile/email request should see no consent")
        print("    screen at all, on localhost or anywhere else.")
    else:
        print(f"    APP_BASE_URL is {BASE_URL} - not localhost, so Auth0 CAN skip consent.")

    if not forces:
        print("\n  => Nothing in this repo requests consent any more, so a consent screen")
        print("     now points AWAY from the code and toward the tenant: a THIRD-PARTY")
        print("     application prompts unconditionally and cannot be fixed in code.")

    print("\n  Two causes remain, and this test separates them in about two minutes:")
    print("\n    Open a PRIVATE/INCOGNITO window (empty cookie jar), sign in, plan 3 trips.")
    print("      consent ONCE, then never  -> the session cookie is being EVICTED in your")
    print("                                   normal profile (17 services share the")
    print("                                   localhost cookie jar; cookies are per-DOMAIN,")
    print("                                   not per-port)")
    print("      consent EVERY time        -> the Auth0 Application is registered")
    print("                                   THIRD-PARTY, which forces consent")
    print("                                   unconditionally and cannot be fixed in code.")
    print("                                   Dashboard > Applications > your app.")

    print("\n  And if the session cannot be READ, this now says why:")
    print("    docker logs p3-ai-travel-planner-web-1 2>&1 | grep auth0-session")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
