"""
Tests for command profiles — bundled sets of ready-to-use commands.

The adoption problem: GAX shipped 11 mostly-mock commands, so a new user's first
task was authoring YAML for everything they cared about. Profiles fix that.

The property that matters most here is that **installing a profile grants
nothing**. It registers commands; invoking them still requires a capability that
names the command, holds the scope, and reaches the side-effect ceiling. If a
future change makes `--profile` hand out power, these tests fail.
"""

from __future__ import annotations

import importlib

import pytest

import gax.profiles as profiles_mod


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.delenv("GAX_CAP", raising=False)

    import gax.paths

    importlib.reload(gax.paths)
    for name in ("gax.caps", "gax.profiles", "gax.registry", "gax.onboarding"):
        importlib.reload(importlib.import_module(name))
    return tmp_path


@pytest.fixture
def profiles(fake_home):
    return importlib.import_module("gax.profiles")


# -- shape ---------------------------------------------------------------


def test_bundled_profiles_exist(profiles):
    available = profiles.available_profiles()
    assert "k8s" in available
    assert "github" in available


@pytest.mark.parametrize("name", ["k8s", "github"])
def test_profile_spans_the_danger_ladder(profiles, name):
    """
    A profile of only read commands would leave the side-effect ceiling
    untestable in practice — and the ceiling is the thing worth demonstrating.
    """
    p = profiles.get_profile(name)
    assert p.by_level("read"), f"{name} has no read commands"
    assert p.by_level("write"), f"{name} has no write commands"
    assert p.by_level("destructive"), f"{name} has no destructive commands"


@pytest.mark.parametrize("name", ["k8s", "github"])
def test_every_profile_command_declares_scope_and_danger(profiles, name):
    """An undeclared side_effects is treated as destructive — never leave it implicit."""
    for cmd in profiles.get_profile(name).commands:
        assert cmd.required_scopes, f"{cmd.command} declares no scopes"
        assert cmd.side_effects in {"read", "write", "destructive"}, cmd.command
        assert cmd.description, f"{cmd.command} has no description"


@pytest.mark.parametrize("name", ["k8s", "github"])
def test_profile_commands_have_adapter_handlers(profiles, name):
    """
    A manifest with no handler registers a command that fails at invoke time.
    Catch that here rather than in the user's terminal.
    """
    from gax.adapters import exec_adapter, k8s_adapter

    tables = {**k8s_adapter._HANDLERS, **exec_adapter._HANDLERS}
    for cmd in profiles.get_profile(name).commands:
        assert cmd.command in tables, f"{cmd.command} has no adapter handler"


@pytest.mark.parametrize("name", ["k8s", "github"])
def test_mutating_commands_offer_dry_run(profiles, name):
    """Anything that changes state must be previewable before it runs."""
    import yaml

    p = profiles.get_profile(name)
    for cmd in p.commands:
        if cmd.side_effects == "read":
            continue
        path = p.path / f"{cmd.command}.yaml"
        schema = (yaml.safe_load(path.read_text()) or {}).get("input_schema") or {}
        assert "dry_run" in (schema.get("properties") or {}), (
            f"{cmd.command} is {cmd.side_effects} but has no dry_run"
        )


# -- install -------------------------------------------------------------


def test_install_copies_into_user_manifests(profiles, fake_home):
    result = profiles.install_profile("k8s")
    target = fake_home / ".gax" / "manifests"
    assert target.is_dir()
    assert len(list(target.glob("*.yaml"))) == len(result["installed"])


def test_installed_commands_are_registered(profiles, fake_home):
    profiles.install_profile("k8s")
    from gax.registry import Registry

    registered = {m.command for m in Registry().list_commands()}
    assert "k8s.pod.logs" in registered
    assert "k8s.namespace.delete" in registered


def test_user_manifests_survive_alongside_packaged(profiles):
    """Profiles must add to the packaged set, not replace it."""
    from gax.registry import Registry

    before = {m.command for m in Registry().list_commands()}
    profiles.install_profile("k8s")
    after = {m.command for m in Registry().list_commands()}
    assert before.issubset(after), "installing a profile dropped packaged commands"


def test_reinstall_does_not_clobber_local_edits(profiles, fake_home):
    profiles.install_profile("k8s")
    edited = fake_home / ".gax" / "manifests" / "k8s.pod.logs.yaml"
    edited.write_text(edited.read_text() + "\n# local edit\n")

    result = profiles.install_profile("k8s")
    assert "k8s.pod.logs" in result["skipped"]
    assert "# local edit" in edited.read_text()


def test_force_overwrites(profiles, fake_home):
    profiles.install_profile("k8s")
    edited = fake_home / ".gax" / "manifests" / "k8s.pod.logs.yaml"
    edited.write_text("# clobbered\n")
    profiles.install_profile("k8s", force=True)
    assert "# clobbered" not in edited.read_text()


def test_unknown_profile_raises(profiles):
    with pytest.raises(KeyError):
        profiles.install_profile("does-not-exist")


# -- the guarantee: installing grants nothing ----------------------------


def test_init_profile_capability_covers_read_only(fake_home):
    """
    `init --profile k8s` must make the profile's *read* commands usable, and must
    not silently grant its write/destructive ones.
    """
    from gax.caps import decode_capability
    from gax.onboarding import run_init

    report = run_init(start_daemon=False, profiles=["k8s"])
    claims = decode_capability(report["capability"])

    assert claims["max_side_effect"] == "read"
    granted = set(claims["commands"])
    assert "k8s.pod.logs" in granted, "read command should be usable after init"
    assert "k8s.namespace.delete" not in granted
    assert "k8s.deployment.restart" not in granted


def test_profile_destructive_command_denied_by_init_capability(fake_home, monkeypatch):
    """End-to-end: the destructive command from a profile is refused, and audited."""
    monkeypatch.setenv("GAX_K8S_MOCK", "1")
    from gax.executor import invoke
    from gax.onboarding import run_init
    from gax.registry import Registry

    report = run_init(start_daemon=False, profiles=["k8s"])
    env, code = invoke(
        Registry(),
        command="k8s.namespace.delete",
        args={"namespace": "prod"},
        capability=report["capability"],
    )
    assert env["ok"] is False
    assert env["error"]["kind"] == "policy_denied"
    assert env["audit_id"], "denial must be audited"
    assert code == 2


def test_profile_read_command_works_after_init(fake_home, monkeypatch):
    monkeypatch.setenv("GAX_K8S_MOCK", "1")
    from gax.executor import invoke
    from gax.onboarding import run_init
    from gax.registry import Registry

    report = run_init(start_daemon=False, profiles=["k8s"])
    env, code = invoke(
        Registry(),
        command="k8s.pod.logs",
        args={"namespace": "prod", "pod": "web-1"},
        capability=report["capability"],
    )
    assert env["ok"] is True, env
    assert code == 0


def test_profile_installed_later_triggers_capability_remint(fake_home):
    """
    A profile installed after the capability was minted must not leave its read
    commands registered-but-uncallable.
    """
    from gax.caps import decode_capability
    from gax.onboarding import run_init

    first = run_init(start_daemon=False)
    assert "k8s.pod.logs" not in decode_capability(first["capability"])["commands"]

    second = run_init(start_daemon=False, profiles=["k8s"])
    assert "k8s.pod.logs" in decode_capability(second["capability"])["commands"]


def test_unknown_profile_in_init_is_reported_not_fatal(fake_home):
    from gax.onboarding import run_init

    report = run_init(start_daemon=False, profiles=["nope"])
    assert report["capability"], "init must still complete"
    assert any("unknown profile" in s for s in report["steps"])
