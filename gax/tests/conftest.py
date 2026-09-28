"""
Shared test setup.

Jev is the default search backend and calls a remote API whenever a key is in
the environment. Tests must never depend on — or spend money against — a
developer's real key, so every test starts with the keys removed. Tests that
exercise Jev inject a fake transport explicitly.
"""

import pytest

_JEV_KEYS = ("TYPESAFE_API_KEY", "JEV_API_KEY")


@pytest.fixture(autouse=True)
def _no_live_jev(monkeypatch):
    for var in _JEV_KEYS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("GAX_SEARCH", raising=False)
