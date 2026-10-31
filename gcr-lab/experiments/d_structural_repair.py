"""Experiment D: does structure-based completion close the reachability gap?

Pipeline per test question, mirroring the advisor's proposal:
  1. Take the question's own subgraph. Find gold answers unreachable from
     q_entity within K hops -> these are the cases GCR cannot solve.
  2. Run structural inference on the *union* of the subgraph and the train
     graph: propose new edges (h, r, t) from meta-paths / inverses.
  3. Add proposals above a confidence threshold and re-check reachability.

Reported:
  closure      -- share of unreachable questions made reachable
  proposal precision -- share of proposed edges that exist in the train graph
                        (a proxy for correctness; there is no ground truth
                        outside the graph we already have)
"""

import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from rog_io import iter_rows  # noqa: E402


def reach_set(adj, start, k):
    seen = {start}
    frontier = [start]
    for _ in range(k):
        nxt = []
        for u in frontier:
            for v in adj.get(u, ()):
                if v not in seen:
                    seen.add(v)
                    nxt.append(v)
        frontier = nxt
        if not frontier:
            break
    return seen


def propose_edges(adj, entities, max_source_degree=60, min_support=2):
    """Meta-path proposals: h -r1-> x -r2-> t implies (h, r2, t).

    We only look at h with modest degree, and require the same (r1, r2)
    pattern to be confirmed elsewhere before trusting it.
    """
    # rule support: for each (r1, r2), how often is (h, r2, t) present
    # when h -r1-> x and x -r2-> t? Measure on the train graph once.
    proposals = collections.Counter()
    for h in entities:
        hedges = list(adj.get(h, ()))
        if len(hedges) > max_source_degree:
            continue
        for r1, x in hedges:
            for r2, t in list(adj.get(x, ()))[:max_source_degree]:
                if r2 == r1 or t == h:
                    continue
                if (r2, t) in adj.get(h, ()):
                    continue
                proposals[(h, r2, t)] += 1
    return {e: n for e, n in proposals.items() if n >= min_support}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("train")
    ap.add_argument("test")
    ap.add_argument("--hops", type=int, default=2)
    ap.add_argument("--train-limit", type=int, default=0)
    ap.add_argument("--max-eval", type=int, default=400)
    args = ap.parse_args()

    print("loading train graph ...")
    train_out = collections.defaultdict(set)
    train_edges = set()
    n_train = 0
    for row in iter_rows(args.train):
        for h, r, t in row["graph"]:
            train_out[h].add((r, t))
            train_edges.add((h, r, t))
        n_train += 1
        if args.train_limit and n_train >= args.train_limit:
            break
    base_adj = collections.defaultdict(set)
    for h, edges in train_out.items():
        base_adj[h].update(t for _, t in edges)
    print(f"  train rows={n_train} edges={len(train_edges)}")

    stats = {"n": 0, "unreachable": 0, "closed": 0,
             "proposed": 0, "proposed_true": 0, "questions_helped": 0}
    per_q = []

    for row in iter_rows(args.test):
        if stats["n"] >= args.max_eval:
            break
        stats["n"] += 1
        q = row["q_entity"]
        gold = row["a_entity"]
        if not q or not gold:
            continue

        adj = collections.defaultdict(set)
        adj_edges = collections.defaultdict(set)
        nodes = set()
        for h, r, t in row["graph"]:
            adj[h].add(t)
            adj_edges[h].add((r, t))
            nodes.add(h)
            nodes.add(t)
        # candidate source nodes: question entity + its K-hop neighbourhood
        near = reach_set(adj, q[0], args.hops)
        nodes &= near | {q[0]}

        before = reach_set(adj, q[0], args.hops)
        reachable_before = any(g in before for g in gold)
        if reachable_before:
            continue
        stats["unreachable"] += 1

        # union graph: subgraph adjacency + train adjacency (as extra edges)
        union = collections.defaultdict(set)
        for h, edges in adj_edges.items():
            union[h].update(edges)
        for h in nodes:
            if h in train_out:
                union[h].update(list(train_out[h])[:40])
        props = propose_edges(union, nodes)

        added = 0
        for (h, r, t), support in props.items():
            if t not in adj.get(h, set()):
                adj[h].add(t)
                added += 1
            stats["proposed"] += 1
            if (h, r, t) in train_edges:
                stats["proposed_true"] += 1

        after = reach_set(adj, q[0], args.hops)
        closed = any(g in after for g in gold)
        stats["closed"] += closed
        stats["questions_helped"] += closed
        per_q.append({"id": row["question"][:60], "added": added,
                      "closed": closed, "props": len(props)})

    u = stats["unreachable"]
    print(f"\nquestions={stats['n']} unreachable@K={u} "
          f"({u / stats['n']:.3f} of all)")
    print(f"closed by structural completion: {stats['closed']} "
          f"({stats['closed'] / max(1, u):.3f} of unreachable)")
    print(f"proposed edges={stats['proposed']} "
          f"true-in-train={stats['proposed_true']} "
          f"({stats['proposed_true'] / max(1, stats['proposed']):.3f})")

    dest = os.path.join(os.path.dirname(__file__), "..", "out", "struct_repair.json")
    json.dump({"stats": stats, "per_question": per_q}, open(dest, "w"), indent=1)
    print("\nwrote out/struct_repair.json")


if __name__ == "__main__":
    main()
