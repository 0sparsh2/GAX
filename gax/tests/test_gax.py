from __future__ import annotations

import os

import pytest

from gax.caps import mint_capability
from gax.executor import invoke
from gax.registry import Registry


@pytest.fixture
def registry() -> Registry:
    return Registry()


@pytest.fixture
def cap() -> str:
    return mint_capability(
        commands=["demo.echo", "gh.pr.list"],
        scopes=["demo:echo", "github:pull_request:read"],
        ttl_seconds=3600,
    )


def test_demo_echo(registry: Registry, cap: str) -> None:
    env, code = invoke(
        registry,
        command="demo.echo",
        args={"message": "test"},
        surface="model",
        capability=cap,
    )
    assert code == 0
    assert env["ok"] is True
    assert env["data"]["echo"] == "test"
    assert env["audit_id"].startswith("aud_")


def test_policy_denied(registry: Registry) -> None:
    cap = mint_capability(commands=["demo.echo"], scopes=["demo:echo"])
    env, code = invoke(
        registry,
        command="gh.pr.list",
        args={"repo": "a/b"},
        capability=cap,
    )
    assert code == 2
    assert env["ok"] is False
    assert env["error"]["kind"] == "policy_denied"


def test_search(registry: Registry) -> None:
    hits = registry.search("pull")
    assert any(m.command == "gh.pr.list" for m in hits)


def test_projection_truncation(registry: Registry, cap: str, monkeypatch) -> None:
    # CI runners often have `gh` but no GITHUB_TOKEN — force mock adapter.
    monkeypatch.setattr("gax.adapters.exec_adapter._gh_available", lambda: False)
    env, code = invoke(
        registry,
        command="gh.pr.list",
        args={"repo": "octocat/Hello-World"},
        surface="model",
        capability=cap,
    )
    assert code == 0
    assert env["ok"] is True
    assert "items" in env["data"]
    assert len(env["data"]["items"]) >= 1


def test_projection_truncates_many_rows() -> None:
    from gax.projection import project_data

    data = {"items": [{"number": i, "title": f"pr-{i}"} for i in range(25)]}
    projected, meta = project_data(data, "model")
    assert len(projected["items"]) == 10
    assert meta.get("truncated") is True
    assert meta.get("row_count") == 25
