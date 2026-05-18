"""Multi-tenant secret vault (file MVP; HashiCorp Vault hook via env)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

from gax.paths import GAX_HOME, ensure_gax_home
from gax.secrets import load_secret, save_secret

VAULT_DIR = GAX_HOME / "vault"


def _tenant_path(tenant: str) -> Path:
    ensure_gax_home()
    d = VAULT_DIR / tenant
    d.mkdir(parents=True, exist_ok=True)
    return d / "secrets.json"


def vault_put(tenant: str, key: str, value: str) -> None:
    hv = os.environ.get("GAX_HASHICORP_VAULT_ADDR")
    if hv:
        _vault_hc_put(hv, tenant, key, value)
        return
    path = _tenant_path(tenant)
    data = load_secret(tenant, "vault", file_path=path) or {}
    data[key] = value
    save_secret(tenant, "vault", data, file_path=path)


def vault_get(tenant: str, key: str) -> str | None:
    hv = os.environ.get("GAX_HASHICORP_VAULT_ADDR")
    if hv:
        return _vault_hc_get(hv, tenant, key)
    path = _tenant_path(tenant)
    data = load_secret(tenant, "vault", file_path=path) or {}
    return data.get(key)


def _vault_hc_headers() -> dict[str, str]:
    tok = os.environ.get("GAX_HASHICORP_VAULT_TOKEN", "")
    h = {"Content-Type": "application/json"}
    if tok:
        h["X-Vault-Token"] = tok
    return h


def _vault_hc_put(addr: str, tenant: str, key: str, value: str) -> None:
    path = f"{addr.rstrip('/')}/v1/secret/data/gax/{tenant}/{key}"
    httpx.post(
        path,
        headers=_vault_hc_headers(),
        json={"data": {"value": value}},
        timeout=15.0,
    ).raise_for_status()


def _vault_hc_get(addr: str, tenant: str, key: str) -> str | None:
    path = f"{addr.rstrip('/')}/v1/secret/data/gax/{tenant}/{key}"
    r = httpx.get(path, headers=_vault_hc_headers(), timeout=15.0)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return (r.json().get("data") or {}).get("data", {}).get("value")
