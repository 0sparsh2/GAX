#!/usr/bin/env python3
"""
Measure `gax_search` backends against eval/search_queries.yaml.

    python eval/run_search_eval.py                    # keyword + bm25
    python eval/run_search_eval.py --backend jev      # needs TYPESAFE_API_KEY

Metrics per bucket (literal / synonym / intent):
  hit@1  — the agent's first pick is right; no extra turn
  hit@3  — right answer visible in a normal result list
  MRR    — mean reciprocal rank of the first correct command
  empty  — queries that returned nothing at all (forces a rephrase)

Runs against the packaged manifests plus the k8s and github profiles, loaded
from the repo — it never reads or writes ~/.gax.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "gax"))

from gax.registry import Registry  # noqa: E402

sys.path.insert(0, str(ROOT / "eval"))
from load_env import load_repo_env  # noqa: E402

load_repo_env(ROOT)  # picks up JEV_API_KEY from repo-root .env; never printed
from gax.search import BACKENDS, get_searcher  # noqa: E402


def load_commands(extra_dirs=()):
    cmds = {}
    for d in [ROOT / "gax" / "manifests", ROOT / "gax" / "profiles" / "k8s",
              ROOT / "gax" / "profiles" / "github", *extra_dirs]:
        for m in Registry(manifests_dir=d).list_commands():
            cmds[m.command] = m
    return list(cmds.values())


def evaluate(backend, commands, queries):
    searcher = get_searcher(backend)
    rows, fallbacks, t0 = [], 0, time.perf_counter()
    for item in queries:
        q0 = time.perf_counter()
        res = searcher.search(item["q"], commands, limit=5)
        ms = (time.perf_counter() - q0) * 1000
        if res.fallback_reason:
            fallbacks += 1
        got = [h.manifest.command for h in res.hits]
        if item["expect"]:
            rank = next((i + 1 for i, c in enumerate(got) if c in item["expect"]), None)
        else:  # out of scope: correct only if nothing was returned
            rank = 1 if not got else None
        rows.append({**item, "got": got, "rank": rank, "confidence": res.confidence,
                     "ms": round(ms, 1), "usage": res.usage,
                     "fallback": res.fallback_reason})
    elapsed = time.perf_counter() - t0
    return rows, fallbacks, elapsed


def summarize(rows):
    out = {}
    for bucket in ["literal", "synonym", "intent", "out_of_scope", "all"]:
        rs = rows if bucket == "all" else [r for r in rows if r["bucket"] == bucket]
        n = len(rs)
        if not n:
            continue
        out[bucket] = {
            "n": n,
            "hit@1": round(sum(r["rank"] == 1 for r in rs) / n, 3),
            "hit@3": round(sum(bool(r["rank"]) and r["rank"] <= 3 for r in rs) / n, 3),
            "mrr": round(sum(1 / r["rank"] for r in rs if r["rank"]) / n, 3),
            # Empty results on queries that had an answer — forced rephrases.
            "empty": sum(not r["got"] for r in rs if r["expect"]),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", action="append", choices=sorted(BACKENDS))
    ap.add_argument("--misses", action="store_true", help="print failed queries")
    ap.add_argument("--json", type=Path, help="write full results here")
    ap.add_argument("--extra-dir", type=Path, action="append", default=[],
                    help="also load manifests from here (e.g. imported MCP servers)")
    ap.add_argument("--queries", type=Path, default=ROOT / "eval" / "search_queries.yaml")
    args = ap.parse_args()

    commands = load_commands(args.extra_dir)
    queries = yaml.safe_load(args.queries.read_text())["queries"]
    backends = args.backend or ["keyword", "bm25"]

    report = {"commands": len(commands), "queries": len(queries), "backends": {}}
    print(f"\n{len(queries)} queries · {len(commands)} commands\n")
    print(f"{'backend':9} {'bucket':8} {'hit@1':>6} {'hit@3':>6} {'MRR':>6} {'empty':>6}")
    for b in backends:
        rows, fallbacks, elapsed = evaluate(b, commands, queries)
        s = summarize(rows)
        report["backends"][b] = {"summary": s, "fallbacks": fallbacks,
                                 "seconds": round(elapsed, 2), "rows": rows}
        for bucket, m in s.items():
            print(f"{b:9} {bucket:8} {m['hit@1']:>6} {m['hit@3']:>6} {m['mrr']:>6} {m['empty']:>6}")
        lat = sorted(r["ms"] for r in rows)
        p50, p95 = lat[len(lat) // 2], lat[min(len(lat) - 1, int(len(lat) * 0.95))]
        tok = [r["usage"]["input_tokens"] for r in rows if r.get("usage")]
        note = f"  latency p50 {p50:.0f} ms · p95 {p95:.0f} ms"
        if tok:
            note += f" · ~{sum(tok) // len(tok)} input tokens/query"
        report["backends"][b].update({"p50_ms": p50, "p95_ms": p95})
        if fallbacks:
            note += f" · {fallbacks} fell back to local search (no key or API error)"
        print(note + "\n")
        if args.misses:
            for r in rows:
                if r["rank"] != 1:
                    want = r["expect"][0] if r["expect"] else "(nothing)"
                    conf = f" conf={r['confidence']:.2f}" if r["confidence"] is not None else ""
                    print(f"   ✗ {r['q']!r:42} want {want:24} got {r['got'][:3]}{conf}")
            print()
    if args.json:
        args.json.write_text(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
