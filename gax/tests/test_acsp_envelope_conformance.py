"""Minimal ACSP-1.0 envelope v1 conformance checks for the reference implementation."""

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
