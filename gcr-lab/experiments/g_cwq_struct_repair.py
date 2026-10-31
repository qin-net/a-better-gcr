"""Experiment G: structural repair of dropped CWQ training questions.

Target: the 1,286 CWQ training questions where no gold answer appears in the
question subgraph (and thus no training path exists). Question: using only
knowledge already inside the dataset's own subgraphs (no LLM, no web), how
many can be reconnected?

Three increasingly generous pools:
  P1  the question's own subgraph                      (by definition 0)
  P2  subgraphs of the same questions' neighbours      -- not applicable, skip
  P3  the union of all CWQ training subgraphs          (a global KB built
      from the data itself, still no external text)

For each dropped question we look for a path q -> ... -> gold_answer in the
global graph. Any hit is a real repair; every node/edge used comes from the
dataset, so the gold answer verifies it for free.

Also reports the shortest connecting distance, so we know whether repairs are
1 hop (trivial completion) or 2+ hops (real multi-hop completion).
"""

import argparse
import collections
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from rog_io import iter_rows  # noqa: E402


def load_global(paths, max_rows=0):
    out = collections.defaultdict(set)
    rows = []
    n = 0
    for p in paths:
        for row in iter_rows(p):
            n += 1
            rows.append(row)
            for h, r, t in row["graph"]:
                out[h].add(t)
            if max_rows and n >= max_rows:
                return out, rows
    return out, rows


def bounded_bfs(adj, starts, goals, max_depth):
    """Shortest distance from any start to any goal, capped at max_depth."""
    goals = set(goals)
    seen = set(starts)
    frontier = [(s, 0) for s in starts]
    while frontier:
        nxt = []
        for u, d in frontier:
            if u in goals:
                return d
            if d >= max_depth:
                continue
            for v in adj.get(u, ()):
                if v not in seen:
                    seen.add(v)
                    nxt.append((v, d + 1))
        frontier = nxt
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("train", nargs="+")
    ap.add_argument("--max-depth", type=int, default=3)
    args = ap.parse_args()

    print("building global graph from CWQ train subgraphs ...")
    g, rows = load_global(args.train)
    edges = sum(len(v) for v in g.values())
    print(f"  questions={len(rows)} entities={len(g)} edges={edges}")

    def in_subgraph(row, node):
        return any(h == node or t == node for h, _, t in row["graph"])

    def reachable_in_subgraph(row, starts, goals):
        adj = collections.defaultdict(set)
        for h, r, t in row["graph"]:
            adj[h].add(t)
        return bounded_bfs(adj, starts, goals, max_depth=99)

    dropped = 0
    repaired = 0
    by_dist = collections.Counter()
    examples = []

    for row in rows:
        q, a = row["q_entity"], row["a_entity"]
        if not q or not a:
            continue
        if reachable_in_subgraph(row, q, a) is not None:
            continue
        dropped += 1
        # the answer must at least exist somewhere in the global graph
        present_global = [x for x in a if x in g or any(t == x for _, t in g.get(x, ()))]
        if not present_global:
            by_dist["answer not in global graph"] += 1
            continue
        d = bounded_bfs(g, q, present_global, args.max_depth)
        if d is None:
            by_dist["unreachable within depth"] += 1
        else:
            repaired += 1
            by_dist[d] += 1
            if len(examples) < 8:
                examples.append({
                    "question": row["question"][:80],
                    "q": q, "answer": present_global[:3], "hops": d,
                })

    print(f"\ndropped questions            {dropped}")
    print(f"repaired via global graph    {repaired}  ({repaired / max(1, dropped):.1%})")
    print("\nbreakdown:")
    for k, v in sorted(by_dist.items(), key=lambda kv: str(kv[0])):
        print(f"  {str(k):>28}  {v}")

    print("\nexamples:")
    for ex in examples:
        print(f"  [{ex['hops']} hop] {ex['question']}")
        print(f"      q={ex['q']}  a={ex['answer']}")

    dest = os.path.join(os.path.dirname(__file__), "..", "out", "cwq_struct_repair.json")
    json.dump({"dropped": dropped, "repaired": repaired,
               "breakdown": {str(k): v for k, v in by_dist.items()},
               "examples": examples}, open(dest, "w"), ensure_ascii=False, indent=1)
    print("\nwrote out/cwq_struct_repair.json")


if __name__ == "__main__":
    main()
