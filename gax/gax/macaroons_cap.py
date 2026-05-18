from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from gax.caps import jwt_secret


def _sign(data: bytes, key: bytes) -> str:
    return base64.urlsafe_b64encode(hmac.new(key, data, hashlib.sha256).digest()).decode().rstrip("=")


def mint_macaroon(
    *,
    tenant_id: str,
    subject: str,
    commands: list[str],
    scopes: list[str],
    ttl_seconds: int = 3600,
    caveats: list[dict[str, Any]] | None = None,
) -> str:
    """HMAC-chained capability (macaroon-style attenuation, MVP)."""
    root_key = jwt_secret().encode()
    now = int(time.time())
    payload: dict[str, Any] = {
        "v": 1,
        "tenant_id": tenant_id,
        "sub": subject,
        "commands": commands,
        "scopes": scopes,
        "iat": now,
        "exp": now + ttl_seconds,
        "caveats": caveats or [],
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    sig = _sign(body, root_key)
    for caveat in caveats or []:
        sig = _sign(f"{sig}|{json.dumps(caveat, sort_keys=True)}".encode(), root_key)
    blob = base64.urlsafe_b64encode(json.dumps({"p": payload, "s": sig}).encode()).decode()
    return f"gaxm_{blob}"


def verify_macaroon(token: str) -> dict[str, Any]:
    if token.startswith("gaxm_"):
        token = token[5:]
    try:
        pad = "=" * (-len(token) % 4)
        raw = json.loads(base64.urlsafe_b64decode(token + pad))
    except Exception as e:
        raise ValueError("invalid macaroon") from e
    payload = raw.get("p") or {}
    sig = raw.get("s", "")
    root_key = jwt_secret().encode()
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    expected = _sign(body, root_key)
    for caveat in payload.get("caveats") or []:
        expected = _sign(f"{expected}|{json.dumps(caveat, sort_keys=True)}".encode(), root_key)
    if not hmac.compare_digest(expected, sig):
        raise ValueError("macaroon signature mismatch")
    if int(payload.get("exp", 0)) < time.time():
        raise ValueError("macaroon expired")
    return payload


def macaroon_allows_command(claims: dict[str, Any], command: str) -> bool:
    allowed = claims.get("commands") or []
    if "*" in allowed:
        return True
    return command in allowed


def macaroon_allows_scopes(claims: dict[str, Any], required: list[str]) -> bool:
    held = set(claims.get("scopes") or [])
    if "*" in held:
        return True
    return set(required).issubset(held)
