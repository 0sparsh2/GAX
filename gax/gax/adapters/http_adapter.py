"""Generic HTTP adapter for OpenAPI-generated manifests."""

from __future__ import annotations

from typing import Any

import httpx

from gax.registry import CommandManifest


def run(manifest: CommandManifest, args: dict[str, Any], **_: Any) -> dict[str, Any]:
    http = (manifest.raw or {}).get("http") or {}
    method = str(http.get("method", "GET")).upper()
    url_template = str(http.get("url", ""))
    if not url_template:
        raise RuntimeError(f"http.url missing for {manifest.command}")

    url = url_template
    path_params = http.get("path_params") or []
    query_params = http.get("query_params") or []
    for p in path_params:
        url = url.replace("{" + p + "}", str(args[p]))
    query = {p: args[p] for p in query_params if p in args}

    headers = dict(http.get("headers") or {})
    with httpx.Client(timeout=60.0) as client:
        resp = client.request(method, url, params=query, headers=headers)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {"text": resp.text}
