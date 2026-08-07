"""Auth0 JWT verification: pure, framework-free, fail-closed.

Access tokens are verified LOCALLY against the tenant's JWKS (RS256) — signature,
issuer, audience, expiry — so steady-state auth makes no per-request network call and a
JWKS blip never rejects a valid token (``PyJWKClient`` caches signing keys by ``kid``).
The FastAPI wiring lives in the API app; this module is the testable unit and the home of
the ``Principal`` the rest of the system authorizes against.
"""

from __future__ import annotations

from typing import Any

import jwt
from jwt import PyJWKClient
from pydantic import BaseModel

from tp_core.settings import Settings, get_settings

# Auth0 carries app-specific claims under a namespaced key (a URI it will not strip).
_TENANT_CLAIM = "https://tp/tenant"


class AuthError(Exception):
    """Raised when a token is missing, malformed, expired, or otherwise invalid."""


class Principal(BaseModel):
    """The authenticated caller. ``tenant_id`` drives multi-tenant isolation."""

    sub: str
    tenant_id: str
    scopes: tuple[str, ...] = ()


# Synthetic principal used only when auth is disabled (local dev); never in a deployed env.
LOCAL_PRINCIPAL = Principal(sub="local-dev", tenant_id="local")

_jwks_clients: dict[str, PyJWKClient] = {}


def _signing_key(token: str, domain: str) -> Any:
    """Resolve the RS256 signing key for ``token`` from the tenant's cached JWKS."""
    url = f"https://{domain}/.well-known/jwks.json"
    client = _jwks_clients.get(url)
    if client is None:
        client = PyJWKClient(url)
        _jwks_clients[url] = client
    return client.get_signing_key_from_jwt(token).key


def _principal_from_claims(claims: dict[str, Any]) -> Principal:
    tenant = claims.get(_TENANT_CLAIM) or claims.get("org_id") or "default"
    scope = claims.get("scope", "")
    return Principal(
        sub=str(claims.get("sub", "")),
        tenant_id=str(tenant),
        scopes=tuple(scope.split()) if scope else (),
    )


def verify_token(token: str, *, settings: Settings | None = None) -> Principal:
    """Verify an Auth0 RS256 access token and return its :class:`Principal`.

    Raises :class:`AuthError` on any failure (no key, bad signature, wrong
    audience/issuer, expired) — callers map that to a 401.
    """
    cfg = settings or get_settings()
    if not (cfg.auth0_domain and cfg.auth0_audience):
        raise AuthError("auth is enabled but AUTH0_DOMAIN/AUTH0_AUDIENCE are not configured")
    try:
        key = _signing_key(token, cfg.auth0_domain)
        claims: dict[str, Any] = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=cfg.auth0_audience,
            issuer=f"https://{cfg.auth0_domain}/",
        )
    except AuthError:
        raise
    except Exception as exc:  # PyJWT raises a family of errors — all mean "unauthorized"
        raise AuthError(f"token verification failed: {exc}") from exc
    return _principal_from_claims(claims)
