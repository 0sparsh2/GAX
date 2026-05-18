"""MCP bridge against offline mock stdio server (CI-safe, no GITHUB_TOKEN)."""

from __future__ import annotations

from pathlib import Path

import yaml

from gax.caps import mint_capability
from gax.executor import invoke
from gax.registry import Registry

REPO = Path(__file__).resolve().parents[2]
MOCK_SERVER = REPO / "eval" / "mock_mcp" / "github_stdio_mock.py"
FIXTURE = REPO / "eval" / "fixtures" / "mcp.github.list_pulls.mock.yaml"


def test_mcp_bridge_mock_stdio(tmp_path) -> None:
    data = yaml.safe_load(FIXTURE.read_text())
    data["mcp"]["server_args"] = [str(MOCK_SERVER)]
    (tmp_path / "mcp.github.list_pulls.mock.yaml").write_text(yaml.dump(data))

    reg = Registry(manifests_dir=tmp_path)
    cap = mint_capability(
        commands=["mcp.github.list_pulls.mock"],
        scopes=["github:pull_request:read"],
    )
    env, code = invoke(
        reg,
        command="mcp.github.list_pulls.mock",
        args={"repo": "octocat/Hello-World"},
        surface="model",
        capability=cap,
    )
    assert code == 0, env
    assert env.get("ok") is True
    assert env.get("audit_id")
    items = (env.get("data") or {}).get("items") or []
    assert len(items) >= 1
    assert items[0].get("number") == 1
