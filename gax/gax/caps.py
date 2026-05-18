from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from gax.paths import CONFIG_PATH, ensure_gax_home

DEFAULT_SECRET = "gax-dev-secret-change-in-production"
DEFAULT_TENANT = "default"


def _load_config() -> dict[str, Any]:
    ensure_gax_home()
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    cfg = {
        "jwt_secret": DEFAULT_SECRET,
        "tenant_id": DEFAULT_TENANT,
        "subject": "dev@local",
    }
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    return cfg


def jwt_secret() -> str:
    return _load_config().get("jwt_secret", DEFAULT_SECRET)


def mint_capability(
    *,
    tenant_id: str | None = None,
    subject: str | None = None,
    commands: list[str] | None = None,
    scopes: list[str] | None = None,
    ttl_seconds: int = 3600,
    budget: dict[str, int] | None = None,
) -> str:
    cfg = _load_config()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject or cfg.get("subject", "dev@local"),
        "tenant_id": tenant_id or cfg.get("tenant_id", DEFAULT_TENANT),
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
        "scopes": scopes or ["*"],
        "commands": commands or ["*"],
        "budget": budget or {"max_calls": 1000, "max_rows": 10_000},
    }
    return jwt.encode(payload, jwt_secret(), algorithm="HS256")


def decode_capability(token: str | None) -> dict[str, Any]:
    if not token:
        token = os.environ.get("GAX_CAP", "").strip()
    if not token:
        raise ValueError("missing capability token (set GAX_CAP or pass GAX-Capability header)")
    # JWT has three dot-separated segments; macaroon is a single base64 blob
    if token.count(".") == 2:
        return jwt.decode(token, jwt_secret(), algorithms=["HS256"])
    from gax.macaroons_cap import verify_macaroon

    return verify_macaroon(token)


def cap_allows_command(claims: dict[str, Any], command: str) -> bool:
    allowed = claims.get("commands") or []
    if "*" in allowed:
        return True
    return command in allowed


def cap_allows_scopes(claims: dict[str, Any], required: list[str]) -> bool:
    held = set(claims.get("scopes") or [])
    if "*" in held:
        return True
    return set(required).issubset(held)
