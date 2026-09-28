"""
Tests for pluggable command search, including the Jev reranker.

Jev's *ranking quality* can only be measured live (eval/run_search_eval.py
--backend jev, with TYPESAFE_API_KEY). What is tested here is everything that
must hold regardless of how good the model is: the request is well-formed and
sends nothing it shouldn't, a reply cannot introduce a command, and any failure
degrades to local search instead of breaking it.
"""

from __future__ import annotations

import httpx
import pytest

from gax.registry import CommandManifest
from gax.search import (
    JEV_MAX_OPTIONS,
    BM25Search,
    JevRerank,
    KeywordSearch,
    get_searcher,
    tokenize,
)


def _m(cmd, desc, category="test"):
    return CommandManifest(
        command=cmd, version="1.0.0", description=desc, category=category, adapter="mock"
    )


COMMANDS = [
    _m("k8s.pod.logs", "Fetch recent logs for a pod", "kubernetes"),
    _m("k8s.pod.delete", "Delete a pod in a namespace", "kubernetes"),
    _m("gh.run.list", "List recent GitHub Actions runs", "github"),
    _m("gh.pr.merge", "Merge a pull request", "github"),
]


class FakeJev:
    """Stands in for api.typesafe.ai; records what it was sent."""

    def __init__(self, pick=None, reply=None, exc=None):
        self.pick, self.reply, self.exc = pick, reply, exc
        self.bodies = []

    def __call__(self, body):
        self.bodies.append(body)
        if self.exc:
            raise self.exc
        if self.reply is not None:
            return self.reply
        criteria = body["questions"]["command"]["criteria"]
        key = next(k for k, v in criteria.items() if v.startswith(self.pick + ":"))
        probs = {k: (0.9 if k == key else 0.1 / (len(criteria) - 1)) for k in criteria}
        return {"answers": {"command": {"type": "choice", "choice": key,
                                        "probabilities": probs, "confidence": 0.82}}}


# -- tokenization / lexical backends --------------------------------------


def test_tokenize_splits_ids_and_folds_plurals():
    assert tokenize("k8s.pod.logs") == ["k8s", "pod", "log"]
    assert tokenize("Pull Requests") == ["pull", "request"]


def test_tokenize_drops_stopwords():
    assert tokenize("what is the pod") == ["pod"]


def test_keyword_is_default():
    """Measured better than BM25 on the eval set; must stay the default."""
    assert isinstance(get_searcher(), KeywordSearch)


def test_unknown_backend_rejected(monkeypatch):
    monkeypatch.setenv("GAX_SEARCH", "nope")
    with pytest.raises(ValueError, match="unknown GAX_SEARCH"):
        get_searcher()


def test_bm25_ranks_literal_match_first():
    hits = BM25Search().search("pod logs", COMMANDS).hits
    assert hits[0].manifest.command == "k8s.pod.logs"


# -- Jev: request shape and data egress ------------------------------------


def test_jev_sends_query_and_descriptions_only():
    fake = FakeJev(pick="gh.run.list")
    JevRerank(transport=fake).search("what broke in CI", COMMANDS)
    body = fake.bodies[0]
    assert body["model"] == "jev-latest"
    assert body["state"] == "what broke in CI"
    q = body["questions"]["command"]
    assert q["type"] == "choice"
    # Option keys are opaque, never raw command ids (which contain dots).
    assert all(k.startswith("c") and "." not in k for k in q["criteria"] if k != "none")
    # Only id + description leave the machine — no args, caps, scopes, audit.
    sent = str(body)
    for forbidden in ("capability", "audit", "required_scopes", "tenant"):
        assert forbidden not in sent


def test_jev_reranks_intent_query():
    fake = FakeJev(pick="gh.run.list")
    res = JevRerank(transport=fake).search("what broke in CI", COMMANDS)
    assert res.backend == "jev"
    assert res.hits[0].manifest.command == "gh.run.list"
    assert res.confidence == pytest.approx(0.82)


def test_small_registry_sends_every_command():
    """
    Intent queries share no words with the right command, so a lexical
    prefilter would drop it. Below the candidate cap, nothing is filtered.
    """
    fake = FakeJev(pick="gh.run.list")
    JevRerank(transport=fake).search("what broke in CI", COMMANDS)
    criteria = fake.bodies[0]["questions"]["command"]["criteria"]
    assert len(criteria) == len(COMMANDS) + 1  # plus the "none" option


def test_large_registry_is_capped_and_never_exceeds_api_limit():
    many = [_m(f"svc.t{i}.run", f"tool number {i}") for i in range(400)]
    fake = FakeJev(reply={"answers": {"command": {"probabilities": {"c0": 1.0}}}})
    JevRerank(transport=fake, candidates=1000).search("tool", many)
    n = len(fake.bodies[0]["questions"]["command"]["criteria"])
    assert n <= JEV_MAX_OPTIONS


def test_large_registry_prefilter_keeps_lexical_matches():
    many = [_m(f"svc.t{i}.run", "unrelated filler") for i in range(200)]
    many.append(_m("k8s.pod.logs", "Fetch recent logs for a pod"))
    fake = FakeJev(pick="k8s.pod.logs")
    JevRerank(transport=fake, candidates=20).search("pod logs", many)
    sent = fake.bodies[0]["questions"]["command"]["criteria"].values()
    assert any(v.startswith("k8s.pod.logs:") for v in sent)


# -- Jev: a reply cannot widen the result set -----------------------------


def test_reply_cannot_introduce_a_command():
    """Keys we never sent are ignored — the ranking is over our set only."""
    reply = {"answers": {"command": {"probabilities":
             {"c0": 0.1, "cEVIL": 0.9, "rm.rf": 0.99}}}}
    res = JevRerank(transport=FakeJev(reply=reply)).search("logs", COMMANDS)
    assert [h.manifest.command for h in res.hits] == ["k8s.pod.logs"]


def test_reply_with_only_unknown_keys_falls_back():
    reply = {"answers": {"command": {"probabilities": {"zzz": 1.0}}}}
    res = JevRerank(transport=FakeJev(reply=reply)).search("pod logs", COMMANDS)
    assert res.backend == "keyword"
    assert "no known options" in res.fallback_reason


# -- Jev: failure degrades, never breaks ----------------------------------


@pytest.mark.parametrize(
    "exc",
    [
        httpx.ConnectError("down"),
        httpx.ReadTimeout("slow"),
        httpx.HTTPStatusError("429", request=httpx.Request("POST", "x"),
                              response=httpx.Response(429)),
        ValueError("bad json"),
    ],
)
def test_any_failure_falls_back_to_keyword(exc):
    res = JevRerank(transport=FakeJev(exc=exc)).search("pod logs", COMMANDS)
    assert res.backend == "keyword"
    assert res.hits[0].manifest.command == "k8s.pod.logs"
    assert res.fallback_reason.startswith("jev unavailable")


def test_outage_is_never_worse_than_default():
    """Fallback must equal the default backend exactly, not a weaker one."""
    down = JevRerank(transport=FakeJev(exc=httpx.ConnectError("down")))
    for q in ["pod logs", "what broke in CI", "remove a pod"]:
        a = [h.manifest.command for h in down.search(q, COMMANDS).hits]
        b = [h.manifest.command for h in KeywordSearch().search(q, COMMANDS).hits]
        assert a == b, q


@pytest.mark.parametrize("reply", [{}, {"answers": {}}, {"answers": {"command": {}}}])
def test_malformed_reply_falls_back(reply):
    res = JevRerank(transport=FakeJev(reply=reply)).search("pod logs", COMMANDS)
    assert res.backend == "keyword"


def test_no_api_key_never_touches_network(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("JEV_API_KEY", raising=False)

    def boom(*a, **k):
        raise AssertionError("network call attempted without a key")

    monkeypatch.setattr(httpx, "post", boom)
    res = JevRerank().search("pod logs", COMMANDS)
    assert res.backend == "keyword"
    assert res.fallback_reason.startswith("no Jev API key")


def test_opt_in_only(monkeypatch):
    """A key in the environment must not switch backends on by itself."""
    monkeypatch.setenv("TYPESAFE_API_KEY", "sk-test")
    monkeypatch.delenv("GAX_SEARCH", raising=False)
    assert isinstance(get_searcher(), KeywordSearch)


# -- MCP surface -----------------------------------------------------------


def test_mcp_search_reports_low_confidence(monkeypatch):
    from gax import search as search_mod
    from gax.mcp_server import GaxMcpServer

    flat = {"answers": {"command": {"probabilities": {"c0": 0.3, "c1": 0.3},
                                    "confidence": 0.12}}}
    monkeypatch.setattr(search_mod, "get_searcher",
                        lambda name=None: JevRerank(transport=FakeJev(reply=flat)))
    out = GaxMcpServer().tool_search({"query": "agents and MCP stuff"})
    assert out["confidence"] == pytest.approx(0.12)
    assert "Ask the user" in out["hint"]


def test_mcp_search_keyword_has_no_confidence_field():
    from gax.mcp_server import GaxMcpServer

    out = GaxMcpServer().tool_search({"query": "echo"})
    assert "confidence" not in out


def test_jev_api_key_alias(monkeypatch):
    from gax.search import jev_api_key

    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setenv("JEV_API_KEY", "sk-alias")
    assert jev_api_key() == "sk-alias"
    monkeypatch.setenv("TYPESAFE_API_KEY", "sk-primary")
    assert jev_api_key() == "sk-primary"


# -- "nothing fits" ---------------------------------------------------------


def _none_reply(conf):
    return {"answers": {"command": {"choice": "none", "confidence": conf,
            "probabilities": {"none": conf, "c0": 1 - conf}}}}


def test_none_option_is_offered_but_is_not_a_command():
    fake = FakeJev(pick="gh.run.list")
    JevRerank(transport=fake).search("x", COMMANDS)
    criteria = fake.bodies[0]["questions"]["command"]["criteria"]
    assert "none" in criteria
    assert criteria["none"].startswith("none:")


def test_confident_none_returns_no_match():
    res = JevRerank(transport=FakeJev(reply=_none_reply(0.95))).search("order a pizza", COMMANDS)
    assert res.no_match is True
    assert res.hits == []
    assert res.fallback_reason is None, "a judged no-match is not a failure"


def test_unsure_none_still_returns_ranked_commands():
    """
    A false 'nothing fits' strands the agent. Measured: real out-of-scope
    queries chose none at >=0.90; the one false none was 0.51.
    """
    res = JevRerank(transport=FakeJev(reply=_none_reply(0.51))).search("wipe staging", COMMANDS)
    assert res.no_match is False
    assert [h.manifest.command for h in res.hits] == ["k8s.pod.logs"]


def test_none_never_appears_as_a_hit():
    reply = {"answers": {"command": {"choice": "c0", "confidence": 0.4,
             "probabilities": {"none": 0.45, "c0": 0.4, "c1": 0.15}}}}
    res = JevRerank(transport=FakeJev(reply=reply)).search("x", COMMANDS)
    assert "none" not in [h.manifest.command for h in res.hits]


def test_candidate_cap_leaves_room_for_none():
    many = [_m(f"svc.t{i}.run", f"tool {i}") for i in range(400)]
    fake = FakeJev(reply={"answers": {"command": {"probabilities": {"c0": 1.0}}}})
    JevRerank(transport=fake, candidates=10_000).search("tool", many)
    assert len(fake.bodies[0]["questions"]["command"]["criteria"]) == JEV_MAX_OPTIONS


def test_mcp_search_says_plainly_when_nothing_fits(monkeypatch):
    from gax import search as search_mod
    from gax.mcp_server import GaxMcpServer

    monkeypatch.setattr(search_mod, "get_searcher",
                        lambda name=None: JevRerank(transport=FakeJev(reply=_none_reply(0.97))))
    out = GaxMcpServer().tool_search({"query": "order a pizza"})
    assert out["results"] == []
    assert "not available" in out["hint"]
