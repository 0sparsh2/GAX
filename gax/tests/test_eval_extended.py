"""CI-safe tests for extended eval modules."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EVAL = REPO / "eval"
sys.path.insert(0, str(REPO / "gax"))
sys.path.insert(0, str(EVAL))

from ablations import run_gax_ablation_schema_preload  # noqa: E402
from mcp_catalog import load_server_catalog, probe_catalog_all  # noqa: E402
from session_transcript import programmatic_mcp_turn, Transcript  # noqa: E402
from gax.registry import Registry  # noqa: E402
from gax.caps import mint_capability  # noqa: E402


def test_mcp_catalog_mock_probes() -> None:
    probes = probe_catalog_all(mock_only=True)
    ids = {p["id"] for p in probes}
    assert "mock_github" in ids
    assert "mock_filesystem" in ids
    mock_gh = next(p for p in probes if p["id"] == "mock_github")
    assert mock_gh["ok"] is True
    assert mock_gh["schema_tokens"] > 0


def test_programmatic_mcp_tokens_lower_than_naive_fixture() -> None:
    t = Transcript()
    tok = programmatic_mcp_turn(
        t,
        system="test",
        code_snippet="await execute('x')",
        tool_output="ok",
        schema_tokens=1000,
    )
    assert tok < 5000


def test_schema_preload_ablation_adds_tax() -> None:
    reg = Registry()
    cap = mint_capability(commands=["demo.echo"], scopes=["demo:echo"])
    task = {
        "id": "echo",
        "category": "happy_path",
        "gax_command": "demo.echo",
        "gax_args": {"message": "x"},
    }

    def row_fn(**kwargs):
        return kwargs

    def gax_invoke(registry, c, cmd, args):
        from gax.executor import invoke

        env, code = invoke(
            registry, command=cmd, args=args, surface="model", capability=c
        )
        return env, code, 0.0

    def gax_transcript_tokens(cmd, env):
        return 100

    row = run_gax_ablation_schema_preload(
        task,
        reg,
        cap,
        row_fn=row_fn,
        gax_invoke=gax_invoke,
        gax_transcript_tokens=gax_transcript_tokens,
        schema_tokens=44000,
    )
    assert row["tokens"] == 44100


def test_catalog_has_popular_servers() -> None:
    ids = {s["id"] for s in load_server_catalog()}
    assert "github" in ids
    assert "filesystem" in ids
    assert "fetch" in ids
