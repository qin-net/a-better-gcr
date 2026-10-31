"""Experiment N: repair dropped CWQ questions with SPARQL-constrained search.

Experiment M showed that unconstrained shortest paths in the pool are almost
all spurious hub shortcuts. Here BFS may only cross an edge whose relation
appears in the question's own SPARQL (training annotation, not test
information). Two variants:
  * directed: edges are followed head -> tail only, as in GCR;
  * +reverse: a gold-relation edge may also be crossed tail -> head, to
    measure how much is lost to relations stored in the opposite direction.

Paths are written as (u, relation, v, reversed) in traversal order: for the
directed variant in `ground_truth_paths` (reversed is always false), for the
+reverse variant in `paths_with_reverse`.

Output: out/constrained_paths.jsonl, out/constrained_paths.json (summary).

Usage:
  python -I experiments/n_constrained_paths.py data/hf/cwq_full/train-*.parquet \
      --webqsp data/hf/train.parquet --sparql data/hf/cwq_sparql_train.parquet
"""

import argparse
import collections
import itertools
import json
import os
import re
import sys
import time

import pyarrow.parquet as pq

sys.path.insert(0, os.path.dirname(__file__))
from l_pool_paths import build_pool, reachable  # noqa: E402
from rog_io import iter_rows  # noqa: E402

PRED_RE = re.compile(r"ns:([a-z_0-9]+\.[a-z_0-9]+\.[a-z_0-9]+)")


def load_sparql_relations(path):
    t = pq.read_table(path, columns=["ID", "sparql"]).to_pydict()
    return {i: set(PRED_RE.findall(s or "")) for i, s in zip(t["ID"], t["sparql"])}


def build_reverse(pool):
    rev = collections.defaultdict(dict)
    for h, nbrs in pool.items():
        for t, rels in nbrs.items():
            rev[t][h] = rels
    return rev


def constrained_bfs(pool, rev, starts, goals, gold, max_depth, node_cap):
    """Shortest constrained paths. Each step is (u, r, v, reversed)."""
    goals = set(goals)
    dist = {s: 0 for s in starts}
    parents = collections.defaultdict(list)
    frontier = list(dist)
    hit = [s for s in frontier if s in goals]
    depth = 0
    while not hit and frontier and depth < max_depth and len(dist) < node_cap:
        depth += 1
        nxt = []
        for u in frontier:
            steps = [(v, rels, False) for v, rels in pool.get(u, {}).items()]
            if rev is not None:
                steps += [(v, rels, True) for v, rels in rev.get(u, {}).items()]
            for v, rels, back in steps:
                ok = rels & gold
                if not ok:
                    continue
                if v not in dist:
                    dist[v] = depth
                    nxt.append(v)
                if dist[v] == depth:
                    parents[v].append((u, sorted(ok), back))
        frontier = nxt
        hit = [v for v in frontier if v in goals]
    return (depth, hit, parents, dist) if hit else (None, [], parents, dist)


def enumerate_paths(hit, parents, dist, max_paths):
    """Paths as lists of (u, r, v, reversed), in traversal order u -> v."""
    out = []

    def back(v, suffix):
        if len(out) >= max_paths:
            return
        if dist[v] == 0:
            for rels in itertools.product(*[s[1] for s in suffix]):
                out.append([(u, r, w, b) for (u, _, w, b), r in zip(suffix, rels)])
                if len(out) >= max_paths:
                    return
            return
        for u, rels, b in parents[v]:
            back(u, [(u, rels, v, b)] + suffix)

    for g in hit:
        back(g, [])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cwq", nargs="+")
    ap.add_argument("--webqsp", nargs="*", default=[])
    ap.add_argument("--sparql", required=True)
    ap.add_argument("--max-depth", type=int, default=6)
    ap.add_argument("--node-cap", type=int, default=400000)
    ap.add_argument("--max-paths", type=int, default=50)
    args = ap.parse_args()

    t0 = time.time()
    gold = load_sparql_relations(args.sparql)

    dropped = []
    for p in args.cwq:
        for row in iter_rows(p):
            q, a = row["q_entity"], row["a_entity"]
            if not q or not a:
                continue
            adj = collections.defaultdict(set)
            for h, r, t in row["graph"]:
                adj[h].add(t)
            if not reachable(adj, q, a):
                dropped.append({"id": row["id"], "question": row["question"],
                                "q_entity": q, "a_entity": a})
    print(f"dropped: {len(dropped)}  ({time.time() - t0:.0f}s)")

    pool = build_pool(list(args.cwq) + list(args.webqsp))
    rev = build_reverse(pool)
    print(f"pool: {len(pool)} source nodes  ({time.time() - t0:.0f}s)")

    directed = collections.Counter()
    both = collections.Counter()
    no_gold = 0
    dest = os.path.join(os.path.dirname(__file__), "..", "out", "constrained_paths.jsonl")
    with open(dest, "w") as f:
        for i, row in enumerate(dropped):
            g = gold.get(row["id"], set())
            no_gold += not g
            d1, hit, parents, dist = constrained_bfs(
                pool, None, row["q_entity"], row["a_entity"], g,
                args.max_depth, args.node_cap)
            d2, hit2, parents2, dist2 = constrained_bfs(
                pool, rev, row["q_entity"], row["a_entity"], g,
                args.max_depth, args.node_cap)
            directed[d1 if d1 is not None else "none"] += 1
            both[d2 if d2 is not None else "none"] += 1
            paths = enumerate_paths(hit, parents, dist, args.max_paths) if d1 else []
            paths2 = enumerate_paths(hit2, parents2, dist2, args.max_paths) if d2 else []
            f.write(json.dumps({**row, "hops": d1, "hops_with_reverse": d2,
                                "ground_truth_paths": paths,
                                "paths_with_reverse": paths2}, ensure_ascii=False) + "\n")
            if (i + 1) % 1000 == 0:
                print(f"  {i + 1}/{len(dropped)}  ({time.time() - t0:.0f}s)")

    n = len(dropped)

    def table(c):
        cum, rows = 0, {}
        for d in range(0, args.max_depth + 1):
            cum += c.get(d, 0)
            rows[f"<={d}"] = {"exact": c.get(d, 0), "cum": cum, "cum_pct": cum / n}
        return rows

    summary = {"dropped": n, "no_sparql_relations": no_gold,
               "directed": table(directed), "with_reverse": table(both)}
    print(f"\nquestions with empty SPARQL relation set: {no_gold}")
    print(f"{'depth':>6} {'directed':>18} {'+reverse':>18}")
    for k in summary["directed"]:
        a, b = summary["directed"][k], summary["with_reverse"][k]
        print(f"{k:>6} {a['exact']:>6} {a['cum_pct']:>10.1%} {b['exact']:>6} {b['cum_pct']:>10.1%}")
    with open(dest.replace(".jsonl", ".json"), "w") as f:
        json.dump(summary, f, indent=1)
    print(f"wrote out/constrained_paths.jsonl  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
