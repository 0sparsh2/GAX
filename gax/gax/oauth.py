from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml

from gax.paths import GAX_HOME, ensure_gax_home

PROVIDERS_PATH = Path(__file__).resolve().parent.parent / "config" / "oauth_providers.yaml"


@dataclass
class OAuthProvider:
    name: str
    device_authorization_url: str
    token_url: str
    client_id_env: str
    scopes: list[str]
    audience: str | None = None

    @property
    def client_id(self) -> str:
        val = os.environ.get(self.client_id_env, "").strip()
        if not val:
            raise ValueError(
                f"Set {self.client_id_env} for OAuth client id (register an OAuth app for provider {self.name})"
            )
        return val


def load_providers() -> dict[str, OAuthProvider]:
    path = PROVIDERS_PATH
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text()) or {}
    out: dict[str, OAuthProvider] = {}
    for name, cfg in (raw.get("providers") or {}).items():
        out[name] = OAuthProvider(
            name=name,
            device_authorization_url=str(cfg["device_authorization_url"]),
            token_url=str(cfg["token_url"]),
            client_id_env=str(cfg.get("client_id_env", f"GAX_{name.upper()}_CLIENT_ID")),
            scopes=list(cfg.get("scopes") or []),
            audience=cfg.get("audience"),
        )
    return out


def token_path(tenant: str, provider: str) -> Path:
    ensure_gax_home()
    d = GAX_HOME / "tokens" / tenant
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{provider}.json"


def save_tokens(tenant: str, provider: str, data: dict[str, Any]) -> Path:
    from gax.secrets import save_secret

    path = token_path(tenant, provider)
    save_secret(tenant, provider, data, file_path=path)
    return path


def load_tokens(tenant: str, provider: str) -> dict[str, Any] | None:
    from gax.secrets import load_secret

    return load_secret(tenant, provider, file_path=token_path(tenant, provider))


def device_flow_login(
    provider: OAuthProvider,
    *,
    tenant: str,
    open_browser: bool = True,
    poll_interval: float | None = None,
) -> dict[str, Any]:
    """RFC 8628 device authorization grant."""
    body: dict[str, Any] = {
        "client_id": provider.client_id,
        "scope": " ".join(provider.scopes),
    }
    headers = {"Accept": "application/json"}
    if provider.name == "github":
        headers["Content-Type"] = "application/json"
        r = httpx.post(provider.device_authorization_url, json=body, headers=headers, timeout=30.0)
    else:
        r = httpx.post(provider.device_authorization_url, data=body, headers=headers, timeout=30.0)
    r.raise_for_status()
    device = r.json()

    verification_uri = device.get("verification_uri_complete") or device.get("verification_uri")
    user_code = device.get("user_code", "")
    device_code = device["device_code"]
    interval = poll_interval or float(device.get("interval", 5))
    expires_in = int(device.get("expires_in", 900))

    click_echo = __import__("click").echo
    click_echo(f"\nVisit: {verification_uri}")
    if user_code:
        click_echo(f"Code: {user_code}\n")
    if open_browser and verification_uri:
        try:
            import webbrowser

            webbrowser.open(verification_uri)
        except Exception:
            pass

    deadline = time.time() + expires_in
    token_body: dict[str, Any] = {
        "client_id": provider.client_id,
        "device_code": device_code,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
    }

    while time.time() < deadline:
        time.sleep(interval)
        if provider.name == "github":
            tr = httpx.post(
                provider.token_url,
                json=token_body,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                timeout=30.0,
            )
        else:
            tr = httpx.post(
                provider.token_url,
                data=token_body,
                headers={"Accept": "application/json"},
                timeout=30.0,
            )
        if tr.status_code == 200:
            tokens = tr.json()
            if "access_token" in tokens:
                tokens["obtained_at"] = time.time()
                tokens["provider"] = provider.name
                tokens["scopes"] = provider.scopes
                save_tokens(tenant, provider.name, tokens)
                return tokens
        err = tr.json() if tr.headers.get("content-type", "").startswith("application/json") else {}
        error = err.get("error", "")
        if error in ("authorization_pending", "slow_down"):
            if error == "slow_down":
                interval = min(interval + 2, 30)
            continue
        if error == "access_denied":
            raise RuntimeError("User denied authorization")
        if error == "expired_token":
            raise RuntimeError("Device code expired; run login again")
        if tr.status_code >= 400 and error not in ("authorization_pending",):
            raise RuntimeError(f"Token poll failed: {tr.text}")

    raise RuntimeError("Device flow timed out")


def mint_cap_from_oauth(
    tenant: str,
    provider: str,
    *,
    commands: list[str] | None = None,
    ttl_seconds: int = 3600,
) -> str:
    """After OAuth login, mint GAX capability JWT scoped to tenant + provider scopes."""
    from gax.caps import mint_capability

    tokens = load_tokens(tenant, provider)
    if not tokens:
        raise ValueError(f"No tokens for tenant={tenant} provider={provider}; run gax auth login first")
    scopes = tokens.get("scopes") or tokens.get("scope") or []
    if isinstance(scopes, str):
        scopes = [s for s in scopes.replace(",", " ").split() if s]
    return mint_capability(
        tenant_id=tenant,
        subject=tokens.get("subject") or f"oauth:{provider}",
        commands=commands or ["*"],
        scopes=list(scopes) if scopes else ["*"],
        ttl_seconds=ttl_seconds,
    )
