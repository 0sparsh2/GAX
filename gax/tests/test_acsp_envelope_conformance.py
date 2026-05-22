"""ACSP-1.0 teaser conformance checks for the GAX reference implementation.

Maps to docs/acsp/CONFORMANCE.md and ACSP-1.0 §3–§8.
"""

from __future__ import annotations

from gax.caps import mint_capability
from gax.executor import invoke
from gax.registry import Registry


def test_envelope_v1_success_shape() -> None:
    reg = Registry()
    cap = mint_capability(commands=["demo.echo"], scopes=["demo:echo"])
    env, code = invoke(
        reg,
        command="demo.echo",
        args={"message": "conformance"},
        surface="model",
        capability=cap,
    )
    assert code == 0
    assert env["v"] == 1
    assert env["ok"] is True
    assert isinstance(env.get("audit_id"), str) and env["audit_id"]
    assert isinstance(env.get("data"), dict)
    assert env.get("cmd")
    assert env.get("surface") == "model"
    assert env.get("meta") is not None


def test_envelope_v1_failure_shape() -> None:
    reg = Registry()
    cap = mint_capability(commands=["demo.echo"], scopes=["demo:echo"])
    env, code = invoke(
        reg,
        command="no.such.command",
        args={},
        surface="model",
        capability=cap,
    )
    assert code != 0
    assert env["v"] == 1
    assert env["ok"] is False
    assert env.get("audit_id")
    err = env.get("error") or {}
    assert err.get("kind")
    assert err.get("message")


def test_invoke_without_capability_is_capability_invalid() -> None:
    reg = Registry()
    env, code = invoke(
        reg,
        command="demo.echo",
        args={"message": "no-cap"},
        surface="model",
        capability=None,
    )
    assert code == 3
    assert env["ok"] is False
    assert (env.get("error") or {}).get("kind") == "capability_invalid"
    assert env.get("audit_id")


def test_policy_denied_still_emits_audit_id() -> None:
    reg = Registry()
    cap = mint_capability(commands=["demo.echo"], scopes=["demo:echo"])
    env, code = invoke(
        reg,
        command="gh.pr.list",
        args={"repo": "octocat/Hello-World"},
        surface="model",
        capability=cap,
    )
    assert code == 2
    assert env["ok"] is False
    assert (env.get("error") or {}).get("kind") == "policy_denied"
    assert env.get("audit_id")


def test_search_discovery_is_bounded() -> None:
    reg = Registry()
    hits = reg.search("list", limit=8)
    assert len(hits) <= 8
    for m in hits:
        assert m.command
        assert m.description
