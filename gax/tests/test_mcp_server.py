"""
Conformance + governance tests for `gax-mcp` (GAX exposed as an MCP server).

Two things must hold:

1. **Protocol conformance** — initialize / tools/list / tools/call behave like an
   MCP stdio server, so unmodified clients work.
2. **The enforcement boundary survives the new surface.** Exposing GAX over MCP
   must not create a bypass: capability, scope, and policy checks still run before
   any adapter, unregistered commands stay unreachable, and every invoke emits an
   `audit_id`. These are the tests that would catch a regression turning GAX into
   a plain tool proxy.
"""

from __future__ import annotations

import io
import json

import pytest

from gax.caps import mint_capability
from gax.mcp_server import TOOLS, GaxMcpServer, serve


@pytest.fixture
def server():
    cap = mint_capability(
        commands=["demo.echo"],
        scopes=["demo:echo"],
    )
    return GaxMcpServer(capability=cap)


def _call(server: GaxMcpServer, name: str, args: dict) -> dict:
    resp = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        }
    )
    return json.loads(resp["result"]["content"][0]["text"])


# -- protocol conformance ------------------------------------------------


def test_initialize_reports_protocol_and_server_info(server):
    resp = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    result = resp["result"]
    assert result["protocolVersion"]
    assert result["serverInfo"]["name"] == "gax"
    assert "tools" in result["capabilities"]


def test_notifications_get_no_response(server):
    """A message with no id is a notification; replying to it corrupts the stream."""
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_unknown_method_returns_jsonrpc_error(server):
    resp = server.handle({"jsonrpc": "2.0", "id": 7, "method": "does/not/exist"})
    assert resp["error"]["code"] == -32601
    assert "result" not in resp


def test_tool_surface_is_constant_size(server):
    """
    The whole point of the three-tool design: schema cost must not grow with the
    registry. If someone adds one tool per command, this fails.
    """
    resp = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = [t["name"] for t in resp["result"]["tools"]]
    assert names == ["gax_search", "gax_doc", "gax_invoke"]

    n_commands = len(server._registry.list_commands())
    assert n_commands > len(names), "registry should exceed the exposed tool count"


def test_tool_schemas_are_wellformed():
    for tool in TOOLS:
        assert tool["name"] and tool["description"]
        schema = tool["inputSchema"]
        assert schema["type"] == "object"
        for req in schema.get("required", []):
            assert req in schema["properties"], f"{tool['name']}: {req} not in properties"


def test_serve_loop_roundtrips_over_stdio():
    """End-to-end through the actual stdio loop, not just handle()."""
    stdin = io.StringIO(
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        + "\n"
        + json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
        + "\n"
        + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        + "\n"
    )
    stdout = io.StringIO()
    serve(stdin, stdout)

    lines = [json.loads(x) for x in stdout.getvalue().strip().split("\n")]
    assert len(lines) == 2, "notification must not produce a response"
    assert [m["id"] for m in lines] == [1, 2]


def test_malformed_json_does_not_kill_the_session():
    stdin = io.StringIO(
        "{not json\n" + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping"}) + "\n"
    )
    stdout = io.StringIO()
    serve(stdin, stdout)

    lines = [json.loads(x) for x in stdout.getvalue().strip().split("\n")]
    assert lines[0]["error"]["code"] == -32700
    assert lines[1]["id"] == 2, "server kept serving after a parse error"


# -- discovery -----------------------------------------------------------


def test_search_returns_names_not_schemas(server):
    """Search must stay cheap: descriptions only, no input schemas inlined."""
    out = _call(server, "gax_search", {"query": "echo"})
    assert out["results"]
    for r in out["results"]:
        assert "input_schema" not in r and "inputSchema" not in r


def test_doc_unknown_command_is_flagged_as_error(server):
    resp = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "gax_doc", "arguments": {"command": "nope.nope"}},
        }
    )
    assert resp["result"]["isError"] is True


# -- governance boundary (the part that must not regress) ----------------


def test_invoke_emits_audit_id(server):
    env = _call(server, "gax_invoke", {"command": "demo.echo", "args": {"message": "hi"}})
    assert env["ok"] is True
    assert env["audit_id"].startswith("aud_")


def test_command_outside_capability_is_denied(server):
    """The cap only grants demo.echo; gh.pr.list must fail closed."""
    env = _call(server, "gax_invoke", {"command": "gh.pr.list", "args": {"repo": "o/r"}})
    assert env["ok"] is False
    assert env["error"]["kind"] == "policy_denied"


def test_unregistered_command_is_unreachable(server):
    env = _call(server, "gax_invoke", {"command": "rm.rf.slash", "args": {}})
    assert env["ok"] is False
    assert env["error"]["kind"] == "not_found"


def test_missing_capability_fails_closed(monkeypatch):
    """No capability must deny, never default-allow."""
    monkeypatch.delenv("GAX_CAP", raising=False)
    env = _call(
        GaxMcpServer(capability=None),
        "gax_invoke",
        {"command": "demo.echo", "args": {"message": "hi"}},
    )
    assert env["ok"] is False
    assert env["error"]["kind"] == "capability_invalid"


def test_denials_are_marked_iserror_for_the_client(server):
    """
    A denial is a real result, but clients should surface it rather than treat it
    as ordinary data.
    """
    resp = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "gax_invoke",
                "arguments": {"command": "gh.pr.list", "args": {"repo": "o/r"}},
            },
        }
    )
    assert resp["result"]["isError"] is True


def test_capability_read_from_env_at_call_time(monkeypatch):
    """A cap minted after startup is still honored (no startup-time snapshot)."""
    srv = GaxMcpServer(capability=None)
    monkeypatch.setenv(
        "GAX_CAP", mint_capability(commands=["demo.echo"], scopes=["demo:echo"])
    )
    env = _call(srv, "gax_invoke", {"command": "demo.echo", "args": {"message": "x"}})
    assert env["ok"] is True
