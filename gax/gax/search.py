"""
Command selection for `gax search` / `gax_search`.

The agent never sees the registry; it asks for commands in its own words and
picks from what comes back. A miss costs a round trip — search, junk, rephrase,
search again — and every turn re-sends the whole context. Selection quality is
therefore where GAX can still save tokens, so backends are pluggable and measured
against `eval/search_queries.yaml`.

Backends (``GAX_SEARCH``):

- ``keyword`` — the original substring scoring. What ``jev`` falls back to,
               and what you get with ``GAX_SEARCH=keyword``.
- ``bm25``    — term-frequency ranking over command id, description, category.
               Stdlib only. Stricter than keyword; used as Jev's prefilter.
- ``jev``     — the default. TypeSafe's Jev picks among the registered commands
               as a single ``choice`` question. Active only when a key is set
               (``TYPESAFE_API_KEY`` or ``JEV_API_KEY``); with no key it makes no
               network call and behaves exactly like ``keyword``.

**Search grants nothing.** It only orders names. Whatever it returns, invoking a
command still passes the capability, scope, ceiling and policy checks, so a bad
or manipulated ranking can waste a turn but cannot widen what an agent may do.

**Jev is a remote call.** It sends the agent's query and the candidate command
ids and descriptions to api.typesafe.ai — never invoke arguments, capabilities,
or audit data. It is the default because it measured far better where users do
not know command names (see DEFAULT_BACKEND), but it only leaves the machine
once a key is configured, and ``GAX_SEARCH=keyword`` turns it off entirely. Any
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

# Measured on eval/search_queries.yaml (36 queries), hit@1:
#   22 commands: keyword 0.47, jev 1.00 · 87 commands: keyword 0.40, jev 1.00
#   intent queries at 87 commands: keyword 0.00, jev 1.00
# Users rarely know exact command names, and keyword search degrades as MCP
# servers are imported, so Jev is the default. Without a key it falls back to
# keyword with no network call, so installs without a key are unaffected.
DEFAULT_BACKEND = "jev"

JEV_URL = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-latest"
JEV_MAX_OPTIONS = 255  # hard API limit per choice question
# Commands sent per query. Measured at 87 commands: sending all of them was both
# more accurate (30/30 vs 29/30) and no slower (p50 267 vs 257 ms) than
# prefiltering to 64. Cost scales ~57 input tokens per command. One slot is
# reserved for the "none" option. Override with GAX_JEV_CANDIDATES.
JEV_CANDIDATES = JEV_MAX_OPTIONS - 1
JEV_TIMEOUT_S = 3.0
JEV_DESC_CHARS = 400
NONE_KEY = "none"
# Honour "none" only when Jev is sure. Measured: six out-of-scope queries chose
# none at 0.90-1.00; the one false none on a real query ("wipe the staging
# environment") was 0.51. Below this, return the ranked commands instead — a
# false "nothing fits" strands the agent, a low-confidence list does not.
NONE_MIN_CONFIDENCE = 0.7


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
    # Remote token usage, when a backend calls a model (for cost accounting).
    usage: dict[str, int] | None = None
    # The reranker judged that no registered command fits the request.
    no_match: bool = False


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
        candidates: int | None = None,
        transport: Any = None,
    ) -> None:
        self.api_key = api_key or jev_api_key()
        self.url = url
        self.timeout = timeout
        if candidates is None:
            candidates = int(os.environ.get("GAX_JEV_CANDIDATES") or JEV_CANDIDATES)
        self.candidates = max(1, min(candidates, JEV_MAX_OPTIONS - 1))
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
        # An explicit way out. Without it Jev must pick *something*, and measured
        # confidence did not separate out-of-scope queries ("order a pizza" ->
        # firecrawl_interact at 0.72) from real ones. Not a command id, so it can
        # never be returned as a hit.
        criteria[NONE_KEY] = (
            "none: no registered command accomplishes this request; the agent "
            "should tell the user it cannot do this"
        )
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
            fallback.fallback_reason = "no Jev API key (TYPESAFE_API_KEY or JEV_API_KEY)"
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

        if answer.get("choice") == NONE_KEY and (confidence or 0) >= NONE_MIN_CONFIDENCE:
            # Deliberate "nothing fits": an empty result, not a fallback, so the
            # agent is told plainly rather than handed a plausible wrong command.
            return SearchResult([], self.name, confidence=confidence,
                                usage=reply.get("usage"), no_match=True)

        # Ignore any key we did not send — a reply cannot introduce a command.
        ranked = sorted(
            ((keys[k], float(p)) for k, p in probs.items() if k in keys),
            key=lambda kv: (-kv[1], kv[0].command),
        )
        if not ranked:
            fallback.fallback_reason = "jev returned no known options"
            return fallback
        return SearchResult(
            [Hit(m, p) for m, p in ranked[:limit]],
            self.name,
            confidence=confidence,
            usage=reply.get("usage"),
        )


# TYPESAFE_API_KEY is the vendor's documented name; JEV_API_KEY is accepted too.
JEV_KEY_VARS = ("TYPESAFE_API_KEY", "JEV_API_KEY")


def jev_api_key() -> str:
    for var in JEV_KEY_VARS:
        val = os.environ.get(var, "").strip()
        if val:
            return val
    return ""


BACKENDS = {"keyword": KeywordSearch, "bm25": BM25Search, "jev": JevRerank}


def get_searcher(name: str | None = None) -> Searcher:
    name = (name or os.environ.get("GAX_SEARCH") or DEFAULT_BACKEND).lower()
    cls = BACKENDS.get(name)
    if cls is None:
        raise ValueError(f"unknown GAX_SEARCH backend {name!r}; choose {sorted(BACKENDS)}")
    return cls()
