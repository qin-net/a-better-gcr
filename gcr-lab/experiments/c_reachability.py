"""Experiment C: how often is the gold answer unreachable for GCR at all?

GCR enumerates paths from q_entity within K hops *inside the provided
subgraph*, so any answer that no K-hop path reaches is unreachable by
construction -- no decoder, however strong, can produce it.

For each test question:
  reach@K   -- is some gold answer reachable from q_entity in <= K hops?
  present   -- does the gold answer appear in the subgraph at all?
  only_via_unreachable -- present, but not reachable in K hops
"""

import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from rog_io import iter_rows  # noqa: E402


def reachable(adj, start, k):
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("test")
    ap.add_argument("--hops", type=int, nargs="+", default=[1, 2, 3])
    args = ap.parse_args()

    adj = collections.defaultdict(set)
    counts = {k: {"reach": 0, "present": 0, "present_unreachable": 0}
              for k in args.hops}
    n = 0
    multi = 0
    node_counts = []

    for row in iter_rows(args.test):
        n += 1
        q = row["q_entity"]
        gold = row["a_entity"]
        if not q or not gold:
            continue
        adj.clear()
        for h, r, t in row["graph"]:
            adj[h].add(t)
        node_counts.append(len(adj))
        starts = reachable(adj, q[0], max(args.hops))
        present = set(t for _, _, t in
                      [(h, r, t) for h, r, t in row["graph"]])
        has_ans = any(g in present for g in gold)
        for k in args.hops:
            rk = reachable(adj, q[0], k)
            hit = any(g in rk for g in gold)
            counts[k]["reach"] += hit
            counts[k]["present"] += has_ans
            counts[k]["present_unreachable"] += (has_ans and not hit)

    print(f"questions={n}")
    print(f"{'K':>3}{'gold reachable':>18}{'gold present':>16}"
          f"{'present but >K hops':>22}")
    out = {"questions": n}
    for k in args.hops:
        c = counts[k]
        print(f"{k:>3}{c['reach'] / n:>18.3f}{c['present'] / n:>16.3f}"
              f"{c['present_unreachable'] / max(1, c['present']):>22.3f}")
        out[f"reach@{k}"] = c["reach"] / n
        out[f"present@{k}"] = c["present"] / n
        out[f"unreachable_share@{k}"] = c["present_unreachable"] / max(1, c["present"])
    out["missing_at_k"] = {k: 1 - counts[k]["reach"] / n for k in args.hops}

    dest = os.path.join(os.path.dirname(__file__), "..", "out", "reachability.json")
    json.dump(out, open(dest, "w"), indent=1)
    print("\nwrote out/reachability.json")


if __name__ == "__main__":
    main()
