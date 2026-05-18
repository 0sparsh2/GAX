"""Generate GAX manifests from OpenAPI 3.x (subset: GET operations)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml


def _slug(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", ".", s.strip("/"))
    return s.strip(".").lower()[:80] or "op"


def generate_manifests(
    spec: dict[str, Any],
    *,
    prefix: str = "api",
    adapter: str = "mock",
) -> list[dict[str, Any]]:
    paths = spec.get("paths") or {}
    out: list[dict[str, Any]] = []
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method, op in methods.items():
            if method.lower() != "get" or not isinstance(op, dict):
                continue
            op_id = op.get("operationId") or f"{method}_{_slug(path)}"
            cmd = f"{prefix}.{_slug(op_id)}"
            params = op.get("parameters") or []
            props: dict[str, Any] = {}
            required: list[str] = []
            path_params: list[str] = []
            query_params: list[str] = []
            for p in params:
                if not isinstance(p, dict):
                    continue
                name = p.get("name")
                if not name:
                    continue
                loc = p.get("in", "query")
                props[name] = {"type": "string", "description": p.get("description", "")}
                if p.get("required"):
                    required.append(name)
                if loc == "path":
                    path_params.append(name)
                elif loc == "query":
                    query_params.append(name)
            manifest: dict[str, Any] = {
                "command": cmd,
                "version": "1.0.0",
                "description": op.get("summary") or op.get("description") or cmd,
                "category": prefix,
                "adapter": adapter,
                "required_scopes": [f"{prefix}:read"],
                "side_effects": "read",
                "idempotent": True,
                "input_schema": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
                "output_schema": {"type": "object"},
            }
            if adapter == "http":
                servers = spec.get("servers") or [{"url": "https://api.example.com"}]
                base = servers[0].get("url", "").rstrip("/")
                manifest["http"] = {
                    "method": "GET",
                    "url": base + path,
                    "path_params": path_params,
                    "query_params": query_params,
                }
            out.append(manifest)
    return out


def write_manifests(manifests: list[dict[str, Any]], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for m in manifests:
        path = out_dir / f"{m['command'].replace('.', '_')}.yaml"
        path.write_text(yaml.safe_dump(m, sort_keys=False))
        written.append(path)
    return written


def load_spec(path: Path) -> dict[str, Any]:
    text = path.read_text()
    if path.suffix in (".yaml", ".yml"):
        return yaml.safe_load(text) or {}
    return json.loads(text)
