"""S12a: Auth0 RS256 token verification — real signature/aud/iss/exp checks, hermetic.

An in-test RSA keypair signs tokens; the JWKS lookup is monkeypatched to return the
matching public key, so ``jwt.decode`` runs for real with NO Auth0 network call.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from tp_core import auth
from tp_core.auth import AuthError, verify_token
from tp_core.settings import Settings

_DOMAIN = "tp.us.auth0.com"
_AUDIENCE = "tp-api"


@pytest.fixture
def keypair():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return priv_pem, priv.public_key()


@pytest.fixture
def cfg() -> Settings:
    return Settings(
        openai_api_key="x",
        auth_enabled=True,
        auth0_domain=_DOMAIN,
        auth0_audience=_AUDIENCE,
    )


def _token(priv_pem: bytes, **override: Any) -> str:
    now = dt.datetime.now(dt.UTC)
    claims: dict[str, Any] = {
        "sub": "auth0|user1",
        "aud": _AUDIENCE,
        "iss": f"https://{_DOMAIN}/",
        "iat": now,
        "exp": now + dt.timedelta(hours=1),
        "https://tp/tenant": "acme",
        "scope": "plan:write trip:write",
    }
    claims.update(override)
    return jwt.encode(claims, priv_pem, algorithm="RS256")


def test_valid_token_yields_principal(monkeypatch, keypair, cfg):
    priv_pem, pub = keypair
    monkeypatch.setattr(auth, "_signing_key", lambda token, domain: pub)
    principal = verify_token(_token(priv_pem), settings=cfg)
    assert principal.sub == "auth0|user1"
    assert principal.tenant_id == "acme"
    assert "plan:write" in principal.scopes


def test_expired_token_rejected(monkeypatch, keypair, cfg):
    priv_pem, pub = keypair
    monkeypatch.setattr(auth, "_signing_key", lambda token, domain: pub)
    tok = _token(priv_pem, exp=dt.datetime.now(dt.UTC) - dt.timedelta(hours=1))
    with pytest.raises(AuthError):
        verify_token(tok, settings=cfg)


def test_wrong_audience_rejected(monkeypatch, keypair, cfg):
    priv_pem, pub = keypair
    monkeypatch.setattr(auth, "_signing_key", lambda token, domain: pub)
    tok = _token(priv_pem, aud="some-other-api")
    with pytest.raises(AuthError):
        verify_token(tok, settings=cfg)


def test_bad_signature_rejected(monkeypatch, keypair, cfg):
    priv_pem, _ = keypair
    other_pub = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key()
    monkeypatch.setattr(auth, "_signing_key", lambda token, domain: other_pub)
    with pytest.raises(AuthError):
        verify_token(_token(priv_pem), settings=cfg)


def test_unconfigured_auth_rejects():
    cfg = Settings(openai_api_key="x", auth_enabled=True)  # no domain/audience
    with pytest.raises(AuthError):
        verify_token("anything", settings=cfg)
