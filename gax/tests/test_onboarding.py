"""
Tests for `gax init` / `gax doctor` — the on-ramp.

We measured the pre-existing first-run path in a clean virtualenv: a new engineer
hit two dead ends (daemon not running, then no capability) before their first
successful command. These tests pin the properties that removed them, so a future
refactor cannot quietly reintroduce either.

Every test redirects `~` to a tmp dir — none of them touch the developer's real
`~/.gax`.
"""

from __future__ import annotations

import importlib
import json

import pytest


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Point ~ at a tmp dir and reload the modules that cache paths at import."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.delenv("GAX_CAP", raising=False)

    import gax.paths

    importlib.reload(gax.paths)
    import gax.caps
    import gax.onboarding

    importlib.reload(gax.caps)
    importlib.reload(gax.onboarding)
    return tmp_path


@pytest.fixture
def onboarding(fake_home):
    import gax.onboarding

    return gax.onboarding


# -- init ----------------------------------------------------------------


def test_init_creates_home_config_and_capability(onboarding, fake_home):
    report = onboarding.run_init(start_daemon=False)
    gax_home = fake_home / ".gax"
    assert gax_home.is_dir()
    assert (gax_home / "config.json").exists()
    assert (gax_home / "dev_cap.jwt").exists()
    assert report["capability"]


def test_init_dev_capability_is_read_only(onboarding):
    """
    The capability `init` hands out must not be able to delete anything. Raising
    the ceiling should be a conscious act, never a side effect of setup.
    """
    report = onboarding.run_init(start_daemon=False)
    from gax.caps import decode_capability

    claims = decode_capability(report["capability"])
    assert claims["max_side_effect"] == "read"

    from gax.side_effects import exceeds_ceiling

    assert exceeds_ceiling(claims, "destructive") is True
    assert exceeds_ceiling(claims, "write") is True


def test_init_generates_unique_signing_secret(onboarding, fake_home):
    """A shipped default secret would make every install forge the others' tokens."""
    onboarding.run_init(start_daemon=False)
    cfg = json.loads((fake_home / ".gax" / "config.json").read_text())
    secret = cfg["jwt_secret"]
    assert secret
    assert secret != "gax-dev-secret-change-in-production"
    assert len(secret) >= 32


def test_init_is_idempotent_and_preserves_capability(onboarding):
    """Re-running init must not invalidate a capability already in use."""
    first = onboarding.run_init(start_daemon=False)
    second = onboarding.run_init(start_daemon=False)
    assert second["capability"] == first["capability"]


def test_init_force_remints(onboarding, fake_home):
    """
    --force must re-mint rather than reuse. Two mints inside the same second
    produce an identical JWT (iat/exp are second-resolution), so assert on the
    write itself rather than on token inequality.
    """
    onboarding.run_init(start_daemon=False)
    cap_file = fake_home / ".gax" / "dev_cap.jwt"
    cap_file.write_text("stale-token-should-be-replaced")

    forced = onboarding.run_init(start_daemon=False, force=True)
    assert forced["capability"] != "stale-token-should-be-replaced"
    assert cap_file.read_text().strip() == forced["capability"]


def test_init_capability_file_is_owner_only(onboarding, fake_home):
    onboarding.run_init(start_daemon=False)
    mode = (fake_home / ".gax" / "dev_cap.jwt").stat().st_mode & 0o777
    assert mode == 0o600, f"capability file is {oct(mode)}, expected 0o600"


def test_init_reports_what_it_did(onboarding):
    report = onboarding.run_init(start_daemon=False)
    assert report["steps"], "init must report its actions, not act silently"


# -- capability fallback (dead end #2) -----------------------------------


def test_saved_capability_used_without_env(onboarding, monkeypatch):
    """
    The fix for the second dead end: after `init`, commands work with no export.
    """
    onboarding.run_init(start_daemon=False)
    monkeypatch.delenv("GAX_CAP", raising=False)

    import gax.cli

    importlib.reload(gax.cli)
    assert gax.cli._capability(), "CLI must fall back to the saved capability"


def test_env_capability_wins_over_saved(onboarding, monkeypatch):
    onboarding.run_init(start_daemon=False)
    monkeypatch.setenv("GAX_CAP", "explicit-token")

    import gax.cli

    importlib.reload(gax.cli)
    assert gax.cli._capability() == "explicit-token"


# -- doctor --------------------------------------------------------------


def _by_name(checks):
    return {c.name: c for c in checks}


def test_doctor_flags_missing_setup(onboarding):
    checks = _by_name(onboarding.run_doctor())
    assert checks["config"].ok is False
    assert checks["config"].fix, "a failing check must tell the user what to run"


def test_doctor_passes_after_init(onboarding):
    onboarding.run_init(start_daemon=False)
    checks = _by_name(onboarding.run_doctor())
    assert checks["gax home"].ok
    assert checks["config"].ok
    assert checks["capability"].ok
    assert "ceiling=read" in checks["capability"].detail


def test_doctor_does_not_flag_unexported_cap_as_failure(onboarding, monkeypatch):
    """
    Commands work from the saved capability, so reporting a missing GAX_CAP as an
    error would be a false alarm — and false alarms train people to ignore doctor.
    """
    onboarding.run_init(start_daemon=False)
    monkeypatch.delenv("GAX_CAP", raising=False)
    for check in onboarding.run_doctor():
        if "GAX_CAP" in check.name:
            assert check.ok is True


def test_doctor_detects_expired_capability(onboarding, fake_home):
    from gax.caps import mint_capability

    expired = mint_capability(commands=["demo.echo"], scopes=["demo:echo"], ttl_seconds=-10)
    (fake_home / ".gax").mkdir(parents=True, exist_ok=True)
    (fake_home / ".gax" / "dev_cap.jwt").write_text(expired)

    cap = _by_name(onboarding.run_doctor())["capability"]
    assert cap.ok is False
    assert "gax init --force" in cap.fix


def test_doctor_reports_missing_daemon_with_fix(onboarding):
    """Dead end #1: the daemon being down must produce actionable guidance."""
    checks = _by_name(onboarding.run_doctor(port=59999))
    sidecar = checks["gaxd sidecar"]
    assert sidecar.ok is False
    assert "--local" in sidecar.fix or "gaxd start" in sidecar.fix


def test_doctor_detects_daemon_with_mismatched_config(onboarding, monkeypatch):
    """
    A daemon started against a different ~/.gax accepts connections but rejects
    every capability with "Signature verification failed" — which reads as a bad
    token rather than a stale process. Found while testing a clean install.
    """
    monkeypatch.setattr(onboarding, "daemon_running", lambda *a, **k: True)
    monkeypatch.setattr(
        onboarding, "daemon_health", lambda *a, **k: {"ok": True, "config_fingerprint": "deadbeef1234"}
    )
    checks = _by_name(onboarding.run_doctor())
    assert "gaxd config" in checks
    assert checks["gaxd config"].ok is False
    assert "gaxd stop" in checks["gaxd config"].fix


def test_matching_daemon_config_is_not_flagged(onboarding, monkeypatch):
    monkeypatch.setattr(onboarding, "daemon_running", lambda *a, **k: True)
    monkeypatch.setattr(
        onboarding,
        "daemon_health",
        lambda *a, **k: {"ok": True, "config_fingerprint": onboarding.config_fingerprint()},
    )
    assert "gaxd config" not in _by_name(onboarding.run_doctor())


def test_old_daemon_without_fingerprint_is_not_flagged(onboarding, monkeypatch):
    """Backwards compatible: a daemon predating the fingerprint must not error."""
    monkeypatch.setattr(onboarding, "daemon_running", lambda *a, **k: True)
    monkeypatch.setattr(onboarding, "daemon_health", lambda *a, **k: {"ok": True})
    assert onboarding.daemon_config_matches() is None
    assert "gaxd config" not in _by_name(onboarding.run_doctor())


def test_missing_backend_binary_is_not_a_failure(onboarding, monkeypatch):
    """gh/kubectl absent falls back to mocks, so it must not read as broken."""
    monkeypatch.setattr("shutil.which", lambda _: None)
    for check in onboarding.run_doctor():
        if check.name.endswith("binary"):
            assert "mock" in check.detail.lower()


def test_doctor_reports_search_backend(onboarding, monkeypatch):
    checks = _by_name(onboarding.run_doctor())
    assert "keyword" in checks["command search"].detail  # default, no key
    assert checks["command search"].ok is True

    monkeypatch.setenv("JEV_API_KEY", "sk-test")
    checks = _by_name(onboarding.run_doctor())
    assert checks["command search"].detail.startswith("jev")
