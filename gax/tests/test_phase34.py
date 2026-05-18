from __future__ import annotations

import json
from pathlib import Path

import pytest

from gax.compliance import export_soc2_csv, load_audit_lines
from gax.openapi_gen import generate_manifests, load_spec, write_manifests
from gax.registry import Registry
from gax.spiffe import workload_identity
from gax.vault import vault_get, vault_put


def test_openapi_generate(tmp_path: Path) -> None:
    spec_path = Path(__file__).resolve().parent.parent / "examples" / "petstore-openapi.json"
    spec = load_spec(spec_path)
    manifests = generate_manifests(spec, prefix="pet", adapter="mock")
    assert len(manifests) >= 2
    paths = write_manifests(manifests, tmp_path)
    assert paths[0].exists()


def test_vault_file_roundtrip() -> None:
    vault_put("test-tenant", "api_key", "secret123")
    assert vault_get("test-tenant", "api_key") == "secret123"


def test_workload_identity_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GAX_SPIFFE_ID", "spiffe://example.com/gaxd")
    wi = workload_identity()
    assert wi["enabled"] is True
    assert "example.com" in wi["spiffe_id"]


def test_new_manifests_registered() -> None:
    reg = Registry()
    assert reg.get("kubectl.get.pods")
    assert reg.get("aws.s3.list")
    assert reg.get("jira.issue.get")
    assert reg.get("mcp.github.list_pulls")


def test_compliance_export(tmp_path: Path) -> None:
    from gax.audit import log_event

    log_event(
        audit_id="aud_test_export",
        tenant_id="default",
        subject="test",
        command="demo.echo",
        args={"message": "x"},
        ok=True,
        duration_ms=1.0,
    )
    out = tmp_path / "soc2.csv"
    n = export_soc2_csv(out)
    assert n >= 1
    assert "audit_id" in out.read_text()


@pytest.mark.skipif(
    not __import__("os").environ.get("GITHUB_TOKEN")
    and not __import__("os").environ.get("GITHUB_PERSONAL_ACCESS_TOKEN"),
    reason="GITHUB_TOKEN required for live MCP",
)
def test_mcp_bridge_live() -> None:
    from gax.caps import mint_capability
    from gax.executor import invoke

    cap = mint_capability(
        commands=["mcp.github.list_pulls"],
        scopes=["github:pull_request:read"],
    )
    env, code = invoke(
        Registry(),
        command="mcp.github.list_pulls",
        args={"repo": "octocat/Hello-World", "state": "open"},
        capability=cap,
    )
    assert code == 0, env
    assert env.get("ok")
