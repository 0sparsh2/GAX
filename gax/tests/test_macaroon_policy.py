from __future__ import annotations

import pytest

from gax.caps import decode_capability
from gax.executor import invoke
from gax.macaroons_cap import mint_macaroon
from gax.policy_bundle import PolicyDenied
from gax.policy_bundle import check_policy_bundle as check_bundle
from gax.registry import Registry


def test_macaroon_roundtrip() -> None:
    tok = mint_macaroon(
        tenant_id="t1",
        subject="u1",
        commands=["demo.echo"],
        scopes=["demo:echo"],
        ttl_seconds=300,
    )
    claims = decode_capability(tok)
    assert claims["tenant_id"] == "t1"
    assert "demo.echo" in claims["commands"]


def test_policy_repo_allowlist() -> None:
    reg = Registry()
    m = reg.get("gh.pr.list")
    assert m
    claims = {"tenant_id": "default"}
    policy = {
        "defaults": {"deny_destructive": True},
        "tenants": {
            "default": {
                "allowed_commands": ["gh.pr.list"],
                "repo_allowlist": ["allowed/repo"],
            }
        },
    }
    check_bundle(claims, m, {"repo": "allowed/repo"}, policy=policy)
    with pytest.raises(PolicyDenied):
        check_bundle(claims, m, {"repo": "other/repo"}, policy=policy)


def test_parallel_plan() -> None:
    from gax.plan import run_plan

    cap = mint_macaroon(
        tenant_id="default",
        subject="x",
        commands=["demo.echo"],
        scopes=["demo:echo"],
    )
    plan = {
        "name": "p",
        "steps": [
            {
                "parallel": [
                    {"id": "a", "command": "demo.echo", "args": {"message": "1"}},
                    {"id": "b", "command": "demo.echo", "args": {"message": "2"}},
                ]
            }
        ],
    }
    env, code = run_plan(Registry(), plan, capability=cap)
    assert code == 0
    assert env["data"]["steps"]["a"]["data"]["echo"] == "1"
