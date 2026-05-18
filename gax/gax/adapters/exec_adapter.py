from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any

from gax.adapters import mock_adapter
from gax.oauth import load_tokens
from gax.registry import CommandManifest


def _gh_available() -> bool:
    return shutil.which("gh") is not None


def _gh_env(tenant_id: str | None) -> dict[str, str]:
    env = os.environ.copy()
    if tenant_id:
        tokens = load_tokens(tenant_id, "github")
        if tokens and tokens.get("access_token"):
            env["GH_TOKEN"] = tokens["access_token"]
    return env


def run(
    manifest: CommandManifest,
    args: dict[str, Any],
    *,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    if not _gh_available():
        return mock_adapter.run(manifest, args)

    if manifest.command == "gh.pr.list":
        return _gh_pr_list(args, tenant_id=tenant_id)
    if manifest.command == "gh.pr.view":
        return _gh_pr_view(args, tenant_id=tenant_id)
    raise RuntimeError(f"exec adapter has no handler for {manifest.command}")


def _gh_pr_list(args: dict[str, Any], *, tenant_id: str | None = None) -> dict[str, Any]:
    repo = args["repo"]
    limit = int(args.get("limit", 30))
    state = args.get("state", "open")
    cmd = [
        "gh",
        "pr",
        "list",
        "--repo",
        repo,
        "--limit",
        str(limit),
        "--state",
        state,
        "--json",
        "number,title,state,url,author,isDraft",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=_gh_env(tenant_id))
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "gh pr list failed")
    raw = json.loads(proc.stdout or "[]")
    items = []
    for row in raw:
        author = row.get("author") or {}
        items.append(
            {
                "number": row["number"],
                "title": row["title"],
                "state": row["state"],
                "url": row["url"],
                "author": author.get("login", "unknown"),
                "draft": row.get("isDraft", False),
            }
        )
    return {"items": items}


def _gh_pr_view(args: dict[str, Any], *, tenant_id: str | None = None) -> dict[str, Any]:
    repo = args["repo"]
    number = int(args["number"])
    cmd = [
        "gh",
        "pr",
        "view",
        str(number),
        "--repo",
        repo,
        "--json",
        "number,title,body,state,url,author",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=_gh_env(tenant_id))
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "gh pr view failed")
    row = json.loads(proc.stdout or "{}")
    author = row.get("author") or {}
    return {
        "number": row["number"],
        "title": row["title"],
        "body": (row.get("body") or "")[:2000],
        "state": row["state"],
        "url": row["url"],
        "author": author.get("login", "unknown"),
    }
