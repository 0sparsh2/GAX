from __future__ import annotations

from gax.caps import mint_capability
from gax.executor import invoke
from gax.plan import load_plan, render_value, run_plan
from gax.registry import Registry


def test_render_template() -> None:
    ctx = {"steps": {"list": {"data": {"items": [{"number": 42}]}}}}
    assert render_value("{{ steps.list.data.items[0].number }}", ctx) == 42


def test_run_plan_local() -> None:
    registry = Registry()
    cap = mint_capability(
        commands=["demo.echo", "gh.pr.list", "gh.pr.view"],
        scopes=["demo:echo", "github:pull_request:read"],
    )
    plan = {
        "name": "test",
        "steps": [
            {"id": "a", "command": "demo.echo", "args": {"message": "plan"}},
        ],
    }
    env, code = run_plan(registry, plan, capability=cap)
    assert code == 0
    assert env["ok"] is True
    assert env["data"]["steps"]["a"]["data"]["echo"] == "plan"


def test_load_example_plan() -> None:
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "examples" / "plan-demo.yaml"
    plan = load_plan(str(path))
    assert plan["name"] == "pr-inspect-demo"
    assert len(plan["steps"]) == 2
