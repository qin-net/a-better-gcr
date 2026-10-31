"""Experiment H: stage 2 -- how far can a bigger local pool + deeper search go?

Stage 1 (experiment G) repaired 911/1284 dropped CWQ questions using 3-hop
paths inside the CWQ training graph pool.

This stage asks what is left for an LLM/agent to do:
  1. deepen the search on the same pool (depth 4, 5, 6) with a visited cap
  2. merge the WebQSP training pool (cross-dataset)
  3. count questions whose gold answer entity exists in NEITHER pool --
     those are the ones only external knowledge can supply.

The gold answer still acts as the verifier, so every repair here is exact.
"""

import argparse
import collections
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from rog_io import iter_rows  # noqa: E402


def build_pool(paths, out):
    for p in paths:
        for row in iter_rows(p):
            for h, r, t in row["graph"]:
                out[h].add(t)
                out[t]  # ensure node exists even with no outgoing edges
    return out


def bfs_depth(adj, starts, goals, max_depth, node_cap=400000):
    """Shortest distance from starts to any goal, up to max_depth.

    Returns (distance or None, explored node count).
    """
    goals = set(goals)
    seen = set(starts)
    frontier = [(s, 0) for s in starts]
    explored = 0
    while frontier:
        nxt = []
        for u, d in frontier:
            explored += 1
            if u in goals:
                return d, explored
            if d >= max_depth or explored > node_cap:
                continue
            for v in adj.get(u, ()):
                if v not in seen:
                    seen.add(v)
                    nxt.append((v, d + 1))
        frontier = nxt
        if explored > node_cap:
            break
    return None, explored


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cwq", nargs="+")
    ap.add_argument("--webqsp", nargs="*", default=[])
    ap.add_argument("--depths", type=int, nargs="+", default=[3, 4, 5, 6])
    ap.add_argument("--out", default="stage2.json")
    args = ap.parse_args()

    t0 = time.time()
    print("building pools ...")
    pool_cwq = collections.defaultdict(set)
    build_pool(args.cwq, pool_cwq)
    print(f"  CWQ pool: {len(pool_cwq)} entities, "
          f"{sum(len(v) for v in pool_cwq.values())} edges")

    pool_all = collections.defaultdict(set)
    for h, tails in pool_cwq.items():
        pool_all[h].update(tails)
    if args.webqsp:
        build_pool(args.webqsp, pool_all)
        print(f"  CWQ+WebQSP pool: {len(pool_all)} entities, "
              f"{sum(len(v) for v in pool_all.values())} edges")

    # identify dropped questions
    dropped = []
    for p in args.cwq:
        for row in iter_rows(p):
            q, a = row["q_entity"], row["a_entity"]
            if not q or not a:
                continue
            adj = collections.defaultdict(set)
            for h, r, t in row["graph"]:
                adj[h].add(t)
            d, _ = bfs_depth(adj, q, a, max_depth=99)
            if d is None:
                dropped.append({"question": row["question"], "q_entity": q, "a_entity": a})
    print(f"\ndropped CWQ questions: {len(dropped)}")

    results = {}
    for name, pool in (("cwq", pool_cwq), ("cwq+webqsp", pool_all)):
        print(f"\npool={name}")
        for depth in args.depths:
            repaired = 0
            for row in dropped:
                a = row["a_entity"]
                present = [x for x in a if x in pool]
                if not present:
                    continue
                d, _ = bfs_depth(pool, row["q_entity"], present, max_depth=depth)
                repaired += d is not None
            results[f"{name}@{depth}"] = repaired
            print(f"  depth<={depth}: repaired {repaired}/{len(dropped)} "
                  f"({repaired / len(dropped):.1%})")

    # what is still impossible locally
    no_answer = 0
    examples = []
    for row in dropped:
        a = row["a_entity"]
        if not any(x in pool_all for x in a):
            no_answer += 1
            if len(examples) < 8:
                examples.append({"question": row["question"][:90],
                                 "q_entity": row["q_entity"],
                                 "answer": a[:3]})
    print(f"\nanswer entity absent from BOTH pools: {no_answer} "
          f"({no_answer / len(dropped):.1%}) -- external knowledge required")
    for ex in examples:
        print(f"  {ex['question']}")
        print(f"      q={ex['q_entity']}  a={ex['answer']}")

    dest = os.path.join(os.path.dirname(__file__), "..", "out", args.out)
    json.dump({"dropped": len(dropped), "repaired_by_depth": results,
               "answer_absent_both_pools": no_answer,
               "examples": examples}, open(dest, "w"), ensure_ascii=False, indent=1)
    print(f"\nwrote out/{args.out}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
