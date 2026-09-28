"""
Command selection for `gax search` / `gax_search`.

The agent never sees the registry; it asks for commands in its own words and
picks from what comes back. A miss costs a round trip — search, junk, rephrase,
search again — and every turn re-sends the whole context. Selection quality is
therefore where GAX can still save tokens, so backends are pluggable and measured
against `eval/search_queries.yaml`.

Backends (``GAX_SEARCH``):

- ``keyword`` — the original substring scoring. The default: it measured
               better than BM25 on the eval set.
- ``bm25``    — term-frequency ranking over command id, description, category.
               Stdlib only. Stricter than keyword; used as Jev's prefilter.
- ``jev``     — BM25 prefilter, then TypeSafe's Jev reranks the candidates as a
               single ``choice`` question. Opt-in: needs ``TYPESAFE_API_KEY``.

**Search grants nothing.** It only orders names. Whatever it returns, invoking a
command still passes the capability, scope, ceiling and policy checks, so a bad
or manipulated ranking can waste a turn but cannot widen what an agent may do.

**Jev is a remote call.** It sends the agent's query and the candidate command
ids and descriptions to api.typesafe.ai — never invoke arguments, capabilities,
or audit data. That is why it is off by default: a governance tool should not
start sending data to a third party because an environment variable exists. Any
failure (network, timeout, 4xx/5xx, malformed reply) falls back to keyword search, so the
remote dependency can degrade ranking but never break search.
"""

from __future__ import annotations

import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Protocol

from gax.registry import CommandManifest

# Measured on eval/search_queries.yaml (30 queries, 22 commands): keyword 0.53
# hit@1, BM25 0.43. The substring scorer earns partial credit that strict term
# matching loses, so it stays the default. BM25 is used only as Jev's prefilter.
DEFAULT_BACKEND = "keyword"

JEV_URL = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-latest"
JEV_MAX_OPTIONS = 255  # hard API limit per choice question
JEV_CANDIDATES = 64  # sent to Jev when the registry is larger than this
JEV_TIMEOUT_S = 3.0
JEV_DESC_CHARS = 400


@dataclass
class Hit:
    manifest: CommandManifest
    score: float


@dataclass
class SearchResult:
    hits: list[Hit]
    backend: str
    # Only set by rerankers that produce a calibrated distribution. Lets the
    # agent ask for clarification instead of guessing on an ambiguous query.
    confidence: float | None = None
    fallback_reason: str | None = None


class Searcher(Protocol):
    name: str

    def search(
        self, query: str, commands: list[CommandManifest], limit: int = 5
    ) -> SearchResult: ...


# -- tokenization ----------------------------------------------------------

_SPLIT = re.compile(r"[^a-z0-9]+")
_STOP = frozenset(
    "a an the of in on for to is are my me i what which why how this that it "
    "and or with from by at be do does all any some".split()
)


def tokenize(text: str) -> list[str]:
    """Lowercase, split ids and prose alike (`k8s.pod.logs` → k8s pod logs)."""
    out = []
    for tok in _SPLIT.split(text.lower()):
        if not tok or tok in _STOP:
            continue
        # Crude plural folding so "logs"/"log", "requests"/"request" meet.
        if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
            tok = tok[:-1]
        out.append(tok)
    return out


def _doc_text(m: CommandManifest) -> str:
    return f"{m.command} {m.description} {m.category}"


# -- backends --------------------------------------------------------------


class KeywordSearch:
    """The original scorer, unchanged. Baseline only."""

    name = "keyword"

    def search(self, query, commands, limit=5):
        q = query.lower().strip()
        if not q:
            return SearchResult([Hit(m, 0.0) for m in commands[:limit]], self.name)
        scored = []
        for m in commands:
            hay = _doc_text(m).lower()
            score = 0
            if q in m.command.lower():
                score += 10
            if q in m.description.lower():
                score += 5
            for word in q.split():
                if word in hay:
                    score += 2
            if score > 0:
                scored.append(Hit(m, float(score)))
        scored.sort(key=lambda h: (-h.score, h.manifest.command))
        return SearchResult(scored[:limit], self.name)


class BM25Search:
    """Okapi BM25. Command id tokens are counted twice — they carry the most signal."""

    name = "bm25"

    def __init__(self, k1: float = 1.2, b: float = 0.75) -> None:
        self.k1, self.b = k1, b

    def _docs(self, commands):
        return [tokenize(m.command) * 2 + tokenize(m.description + " " + m.category)
                for m in commands]

    def rank(self, query: str, commands: list[CommandManifest]) -> list[Hit]:
        q = tokenize(query)
        docs = self._docs(commands)
        n = len(docs)
        if not q or not n:
            return []
        avgdl = sum(len(d) for d in docs) / n
        df = Counter(t for d in docs for t in set(d))
        hits = []
        for m, d in zip(commands, docs):
            tf = Counter(d)
            score = 0.0
            for t in q:
                if t not in tf:
                    continue
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                f = tf[t]
                score += idf * f * (self.k1 + 1) / (
                    f + self.k1 * (1 - self.b + self.b * len(d) / avgdl)
                )
            if score > 0:
                hits.append(Hit(m, score))
        hits.sort(key=lambda h: (-h.score, h.manifest.command))
        return hits

    def search(self, query, commands, limit=5):
        if not query.strip():
            return SearchResult([Hit(m, 0.0) for m in commands[:limit]], self.name)
        return SearchResult(self.rank(query, commands)[:limit], self.name)


class JevRerank:
    """
    Two-stage: BM25 narrows, Jev decides.

    When the registry fits in ``JEV_CANDIDATES`` every command is sent, so the
    prefilter can never drop the right answer — intent queries like "what broke
    in CI" share no words with `gh.run.list` and would score zero in BM25. Above
    that, BM25's top candidates are sent, padded so Jev always has a real choice.
    """

    name = "jev"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        url: str = JEV_URL,
        timeout: float = JEV_TIMEOUT_S,
        candidates: int = JEV_CANDIDATES,
        transport: Any = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("TYPESAFE_API_KEY", "")
        self.url = url
        self.timeout = timeout
        self.candidates = min(candidates, JEV_MAX_OPTIONS)
        self._transport = transport  # injectable for tests
        self._bm25 = BM25Search()  # prefilter for large registries only
        self._fallback = KeywordSearch()  # best local ranker; see DEFAULT_BACKEND

    def _candidates(self, query, commands):
        if len(commands) <= self.candidates:
            return list(commands)
        ranked = [h.manifest for h in self._bm25.rank(query, commands)]
        seen = {m.command for m in ranked}
        pad = [m for m in commands if m.command not in seen]
        return (ranked + pad)[: self.candidates]

    def _request(self, query, cands):
        # Opaque option keys: command ids contain dots, and the API's key rules
        # are not documented, so never rely on them surviving as keys.
        keys = {f"c{i}": m for i, m in enumerate(cands)}
        criteria = {
            k: f"{m.command}: {m.description}"[:JEV_DESC_CHARS] for k, m in keys.items()
        }
        body = {
            "model": JEV_MODEL,
            "state": query,
            "questions": {
                "command": {
                    "type": "choice",
                    "instructions": (
                        "An AI agent wants to perform this request. Which registered "
                        "command best accomplishes it?"
                    ),
                    "criteria": criteria,
                }
            },
        }
        return body, keys

    def _post(self, body):
        if self._transport is not None:
            return self._transport(body)
        import httpx

        r = httpx.post(
            self.url,
            json=body,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()

    def search(self, query, commands, limit=5):
        # Degrade to the best local ranker, not the prefilter — BM25 measured
        # worse than keyword, so an outage must not make results worse than
        # never having enabled Jev.
        fallback = self._fallback.search(query, commands, limit)
        if not query.strip() or not commands:
            return fallback
        if not self.api_key and self._transport is None:
            fallback.fallback_reason = "TYPESAFE_API_KEY not set"
            return fallback

        cands = self._candidates(query, commands)
        body, keys = self._request(query, cands)
        try:
            reply = self._post(body)
            answer = reply["answers"]["command"]
            probs = answer["probabilities"]
            confidence = float(answer.get("confidence")) if answer.get("confidence") is not None else None
        except Exception as e:  # network, timeout, HTTP error, bad shape
            fallback.fallback_reason = f"jev unavailable: {type(e).__name__}"
            return fallback

        # Ignore any key we did not send — a reply cannot introduce a command.
        ranked = sorted(
            ((keys[k], float(p)) for k, p in probs.items() if k in keys),
            key=lambda kv: (-kv[1], kv[0].command),
        )
        if not ranked:
            fallback.fallback_reason = "jev returned no known options"
            return fallback
        return SearchResult(
            [Hit(m, p) for m, p in ranked[:limit]], self.name, confidence=confidence
        )


BACKENDS = {"keyword": KeywordSearch, "bm25": BM25Search, "jev": JevRerank}


def get_searcher(name: str | None = None) -> Searcher:
    name = (name or os.environ.get("GAX_SEARCH") or DEFAULT_BACKEND).lower()
    cls = BACKENDS.get(name)
    if cls is None:
        raise ValueError(f"unknown GAX_SEARCH backend {name!r}; choose {sorted(BACKENDS)}")
    return cls()
