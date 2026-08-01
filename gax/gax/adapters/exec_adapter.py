from __future__ import annotations

import json
import os
import re
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

    handler = _HANDLERS.get(manifest.command)
    if handler is None:
        raise RuntimeError(f"exec adapter has no handler for {manifest.command}")
    if manifest.command in _MUTATING:
        return handler(args, tenant_id=tenant_id, dry_run=bool(args.get("dry_run")))
    return handler(args, tenant_id=tenant_id)


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


def _repo(args: dict[str, Any]) -> str:
    """Validate owner/name before it reaches the gh subprocess."""
    repo = str(args.get("repo") or "").strip()
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        raise ValueError(f"invalid repo {repo!r}; expected owner/name")
    return repo


def _gh(argv: list[str], tenant_id: str | None) -> str:
    proc = subprocess.run(
        ["gh", *argv], capture_output=True, text=True, timeout=60, env=_gh_env(tenant_id)
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"gh {' '.join(argv)} failed")
    return proc.stdout


def _gh_issue_list(args: dict[str, Any], *, tenant_id: str | None = None) -> dict[str, Any]:
    repo = _repo(args)
    argv = [
        "issue", "list", "--repo", repo,
        "--limit", str(int(args.get("limit", 30))),
        "--state", str(args.get("state", "open")),
        "--json", "number,title,state,url,author",
    ]
    rows = json.loads(_gh(argv, tenant_id) or "[]")
    return {
        "items": [
            {
                "number": r["number"],
                "title": r["title"],
                "state": r["state"],
                "url": r["url"],
                "author": (r.get("author") or {}).get("login", "unknown"),
            }
            for r in rows
        ]
    }


def _gh_issue_view(args: dict[str, Any], *, tenant_id: str | None = None) -> dict[str, Any]:
    repo = _repo(args)
    number = int(args["number"])
    row = json.loads(
        _gh(
            ["issue", "view", str(number), "--repo", repo,
             "--json", "number,title,body,state,url,author"],
            tenant_id,
        )
        or "{}"
    )
    return {
        "number": row.get("number"),
        "title": row.get("title"),
        "body": (row.get("body") or "")[:2000],
        "state": row.get("state"),
        "url": row.get("url"),
        "author": (row.get("author") or {}).get("login", "unknown"),
    }


def _gh_run_list(args: dict[str, Any], *, tenant_id: str | None = None) -> dict[str, Any]:
    repo = _repo(args)
    rows = json.loads(
        _gh(
            ["run", "list", "--repo", repo,
             "--limit", str(int(args.get("limit", 20))),
             "--json", "databaseId,displayTitle,status,conclusion,workflowName"],
            tenant_id,
        )
        or "[]"
    )
    return {
        "items": [
            {
                "id": r.get("databaseId"),
                "title": r.get("displayTitle"),
                "workflow": r.get("workflowName"),
                "status": r.get("status"),
                "conclusion": r.get("conclusion"),
            }
            for r in rows
        ]
    }


def _gh_pr_comment(
    args: dict[str, Any], *, tenant_id: str | None = None, dry_run: bool = False
) -> dict[str, Any]:
    repo = _repo(args)
    number = int(args["number"])
    body = str(args.get("body") or "").strip()
    if not body:
        raise ValueError("body is required")
    if dry_run:
        return {"posted": False, "repo": repo, "number": number, "dry_run": True}
    out = _gh(["pr", "comment", str(number), "--repo", repo, "--body", body], tenant_id)
    return {
        "posted": True,
        "repo": repo,
        "number": number,
        "dry_run": False,
        "url": out.strip(),
    }


def _gh_pr_merge(
    args: dict[str, Any], *, tenant_id: str | None = None, dry_run: bool = False
) -> dict[str, Any]:
    repo = _repo(args)
    number = int(args["number"])
    method = str(args.get("method") or "squash").lower()
    if method not in {"merge", "squash", "rebase"}:
        raise ValueError(f"invalid merge method {method!r}; expected merge|squash|rebase")
    if dry_run:
        return {
            "merged": False,
            "repo": repo,
            "number": number,
            "method": method,
            "dry_run": True,
        }
    out = _gh(["pr", "merge", str(number), "--repo", repo, f"--{method}"], tenant_id)
    return {
        "merged": True,
        "repo": repo,
        "number": number,
        "method": method,
        "dry_run": False,
        "output": out.strip(),
    }


# Table-driven so a new gh manifest needs one entry, not an if-branch.
# Mutating commands receive dry_run; read-only ones cannot accept one they'd ignore.
_HANDLERS = {
    "gh.pr.list": _gh_pr_list,
    "gh.pr.view": _gh_pr_view,
    "gh.issue.list": _gh_issue_list,
    "gh.issue.view": _gh_issue_view,
    "gh.run.list": _gh_run_list,
    "gh.pr.comment": _gh_pr_comment,
    "gh.pr.merge": _gh_pr_merge,
}

_MUTATING = {"gh.pr.comment", "gh.pr.merge"}
