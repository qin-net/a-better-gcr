"""Experiment L: build ground_truth_paths for dropped CWQ questions from the pool.

Same contract as the official `get_truth_paths`: all shortest q_entity ->
a_entity paths, each a list of (head, relation, tail) triples. The only
difference is the graph: the union of all CWQ + WebQSP training subgraphs
instead of the question's own subgraph.

Two deviations, both needed on a 7M-edge graph:
  * BFS stops after --node-cap explored nodes (same cap as experiment H);
  * at most --max-paths paths are kept per question. `n_paths` records the
    true count before truncation, so the cap's effect is measurable.

Where the pool has several relations between the same (u, v), every relation
is a separate path. The official DiGraph keeps only the last one inserted.

Output: out/pool_paths.jsonl, one dropped question per line.

Usage:
  python -I experiments/l_pool_paths.py data/hf/cwq_full/train-*.parquet \
      --webqsp data/hf/train.parquet --max-depth 4
"""

import argparse
import collections
import itertools
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from rog_io import iter_rows  # noqa: E402


def build_pool(paths):
    pool = collections.defaultdict(lambda: collections.defaultdict(set))
    for p in paths:
        for row in iter_rows(p):
            for h, r, t in row["graph"]:
                pool[sys.intern(h)][sys.intern(t)].add(sys.intern(r))
    return pool


def reachable(adj, starts, goals):
    goals = set(goals)
    seen = set(starts)
    frontier = list(seen)
    while frontier:
        if goals & set(frontier):
            return True
        nxt = []
        for u in frontier:
            for v in adj.get(u, ()):
                if v not in seen:
                    seen.add(v)
                    nxt.append(v)
        frontier = nxt
    return False


def shortest_paths(pool, starts, goals, max_depth, node_cap, max_paths):
    """All shortest node paths from starts to the nearest goals.

    Returns (depth, node paths, true path count) or (None, [], 0).
    """
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
            for v in pool.get(u, ()):
                if v not in dist:
                    dist[v] = depth
                    nxt.append(v)
                if dist[v] == depth:
                    parents[v].append(u)
        frontier = nxt
        hit = [v for v in frontier if v in goals]
    if not hit:
        return None, [], 0

    count = {s: 1 for s in starts}

    def n_paths(v):
        if v not in count:
            count[v] = sum(n_paths(u) for u in parents[v])
        return count[v]

    total = sum(n_paths(g) for g in hit)

    out = []

    def back(v, suffix):
        if len(out) >= max_paths:
            return
        if dist[v] == 0:
            out.append([v] + suffix)
            return
        for u in parents[v]:
            back(u, [v] + suffix)

    for g in hit:
        back(g, [])
    return depth, out, total


def with_relations(pool, node_path, budget):
    hops = [sorted(pool[u][v]) for u, v in zip(node_path, node_path[1:])]
    for rels in itertools.islice(itertools.product(*hops), budget):
        yield [(u, r, v) for (u, v), r in zip(zip(node_path, node_path[1:]), rels)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cwq", nargs="+")
    ap.add_argument("--webqsp", nargs="*", default=[])
    ap.add_argument("--max-depth", type=int, default=4)
    ap.add_argument("--node-cap", type=int, default=400000)
    ap.add_argument("--max-paths", type=int, default=50)
    args = ap.parse_args()

    t0 = time.time()
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
    print(f"pool: {len(pool)} source nodes  ({time.time() - t0:.0f}s)")

    dest = os.path.join(os.path.dirname(__file__), "..", "out", "pool_paths.jsonl")
    by_depth = collections.Counter()
    truncated = 0
    with open(dest, "w") as f:
        for i, row in enumerate(dropped):
            depth, node_paths, total = shortest_paths(
                pool, row["q_entity"], row["a_entity"], args.max_depth,
                args.node_cap, args.max_paths)
            paths = []
            for np_ in node_paths:
                for tp in with_relations(pool, np_, args.max_paths - len(paths)):
                    paths.append(tp)
                if len(paths) >= args.max_paths:
                    break
            by_depth[depth if depth is not None else "none"] += 1
            truncated += total > len(node_paths)
            f.write(json.dumps({**row, "hops": depth, "n_paths": total,
                                "ground_truth_paths": paths}, ensure_ascii=False) + "\n")
            if (i + 1) % 500 == 0:
                print(f"  {i + 1}/{len(dropped)}  ({time.time() - t0:.0f}s)")

    print(f"\nrepaired by depth: {dict(sorted(by_depth.items(), key=str))}")
    print(f"questions whose path list was truncated at {args.max_paths}: {truncated}")
    print(f"wrote out/pool_paths.jsonl  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
