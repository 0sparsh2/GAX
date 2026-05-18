from __future__ import annotations

import json
import os
from typing import Any

import httpx

from gax.paths import DEFAULT_HOST, DEFAULT_PORT


def base_url(host: str | None = None, port: int | None = None) -> str:
    h = host or os.environ.get("GAX_HOST", DEFAULT_HOST)
    p = port or int(os.environ.get("GAX_PORT", DEFAULT_PORT))
    return f"http://{h}:{p}"


def capability_header() -> dict[str, str]:
    cap = os.environ.get("GAX_CAP", "").strip()
    if not cap:
        return {}
    return {"GAX-Capability": cap}


def remote_invoke(
    command: str,
    args: dict[str, Any],
    *,
    surface: str = "model",
    host: str | None = None,
    port: int | None = None,
) -> tuple[dict[str, Any], int]:
    url = base_url(host, port) + "/invoke"
    body = {"command": command, "args": args, "surface": surface}
    r = httpx.post(url, json=body, headers=capability_header(), timeout=120.0)
    data = r.json()
    env = data.get("envelope", data)
    exit_code = int(data.get("exit_code", 1 if not env.get("ok") else 0))
    return env, exit_code


def remote_doc(command: str, host: str | None = None, port: int | None = None) -> dict[str, Any]:
    r = httpx.get(f"{base_url(host, port)}/commands/{command}/doc", timeout=10.0)
    r.raise_for_status()
    return r.json()


def remote_search(query: str, host: str | None = None, port: int | None = None) -> dict[str, Any]:
    r = httpx.get(f"{base_url(host, port)}/search", params={"q": query}, timeout=10.0)
    r.raise_for_status()
    return r.json()


def remote_schema(command: str, host: str | None = None, port: int | None = None) -> dict[str, Any]:
    r = httpx.get(f"{base_url(host, port)}/schema/{command}", timeout=10.0)
    r.raise_for_status()
    return r.json()
