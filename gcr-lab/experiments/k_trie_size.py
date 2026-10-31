"""Experiment K: how big does the KG-Trie get at depth 2 vs 3?

The official index (`workflow/build_graph_index.py`) runs `dfs` from every
q_entity over the question's DiGraph and keeps every walk of length <= K
(nodes may repeat). The trie is built over those walks, so the walk count is
a direct proxy for trie size and build time.

Walks are counted without enumerating them:
    f_0(v) = 0,   f_k(v) = sum_{u in N(v)} (1 + f_{k-1}(u))
f_K(q) is the number of walks of length 1..K starting at q.

Two graphs are measured:
  private  -- the question's own subgraph (what GCR uses today)
  pool     -- the union of all CWQ + WebQSP training subgraphs, i.e. what
              the trie would be built on if inference also used the pool

It also checks whether depth 3 on the private subgraph reaches any gold
answer that depth 2 misses. If not, 3-hop training paths can only be decoded
when inference uses the pool.

Usage:
  python -I experiments/k_trie_size.py data/hf/cwq_full/train-*.parquet \
      --webqsp data/hf/train.parquet --sample 3000
"""

import argparse
import collections
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
from rog_io import iter_rows  # noqa: E402


def walk_counts(adj, starts, K):
    """Walks of length 1..k from starts, for k = 1..K, on a small graph."""
    memo = {}

    def f(v, k):
        if k == 0:
            return 0
        key = (v, k)
        if key not in memo:
            memo[key] = sum(1 + f(u, k - 1) for u in adj.get(v, ()))
        return memo[key]

    return [sum(f(s, k) for s in set(starts)) for k in range(1, K + 1)]


def min_hops(adj, starts, goals, cap):
    goals = set(goals)
    seen = set(starts)
    frontier = list(seen)
    for d in range(cap + 1):
        if goals & set(frontier):
            return d
        nxt = []
        for u in frontier:
            for v in adj.get(u, ()):
                if v not in seen:
                    seen.add(v)
                    nxt.append(v)
        frontier = nxt
    return None


def quantiles(xs):
    xs = sorted(xs)
    if not xs:
        return {}
    pick = lambda q: xs[min(len(xs) - 1, int(q * len(xs)))]
    return {"median": pick(0.5), "p90": pick(0.9), "p99": pick(0.99),
            "max": xs[-1], "mean": sum(xs) / len(xs)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cwq", nargs="+")
    ap.add_argument("--webqsp", nargs="*", default=[])
    ap.add_argument("--sample", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    import pyarrow.parquet as pq
    total = sum(pq.ParquetFile(p).metadata.num_rows for p in args.cwq)
    picked = set(random.Random(args.seed).sample(range(total), min(args.sample, total)))
    rows = (r for i, r in enumerate(r for p in args.cwq for r in iter_rows(p))
            if i in picked and r["q_entity"] and r["a_entity"])

    priv = {2: [], 3: []}
    reach = collections.Counter()
    q_entities = []
    for row in rows:
        adj = collections.defaultdict(set)
        for h, r, t in row["graph"]:
            adj[h].add(t)
        c2, c3 = walk_counts(adj, row["q_entity"], 3)[1:]
        priv[2].append(c2)
        priv[3].append(c3)
        d2 = min_hops(adj, row["q_entity"], row["a_entity"], 2)
        d3 = min_hops(adj, row["q_entity"], row["a_entity"], 3)
        reach["<=2"] += d2 is not None
        reach["<=3"] += d3 is not None
        q_entities.append(row["q_entity"])
    print(f"sampled {len(q_entities)} CWQ training questions")

    print("building pool ...")
    pool = collections.defaultdict(set)
    for p in list(args.cwq) + list(args.webqsp):
        for row in iter_rows(p):
            for h, r, t in row["graph"]:
                pool[sys.intern(h)].add(sys.intern(t))
    print(f"  {len(pool)} source nodes, {sum(len(v) for v in pool.values())} edges")

    f1 = {v: len(us) for v, us in pool.items()}
    f2 = {v: sum(1 + f1.get(u, 0) for u in us) for v, us in pool.items()}
    pool_cnt = {2: [], 3: []}
    for qs in q_entities:
        qs = set(qs)
        pool_cnt[2].append(sum(f2.get(q, 0) for q in qs))
        pool_cnt[3].append(sum(sum(1 + f2.get(u, 0) for u in pool.get(q, ()))
                               for q in qs))

    n = len(q_entities)
    out = {
        "sample": n,
        "private_reach": {k: v / n for k, v in reach.items()},
        "walks": {
            "private@2": quantiles(priv[2]),
            "private@3": quantiles(priv[3]),
            "pool@2": quantiles(pool_cnt[2]),
            "pool@3": quantiles(pool_cnt[3]),
        },
    }
    print(f"\nprivate subgraph, gold reachable: <=2 hops {reach['<=2'] / n:.1%}"
          f"   <=3 hops {reach['<=3'] / n:.1%}")
    print(f"\n{'walks per question':<14}{'median':>14}{'p90':>14}{'p99':>16}{'max':>18}")
    for name, qs in out["walks"].items():
        print(f"{name:<14}{qs['median']:>14,}{qs['p90']:>14,}{qs['p99']:>16,}{qs['max']:>18,}")

    dest = os.path.join(os.path.dirname(__file__), "..", "out", "trie_size.json")
    json.dump(out, open(dest, "w"), indent=1)
    print("\nwrote out/trie_size.json")


if __name__ == "__main__":
    main()
