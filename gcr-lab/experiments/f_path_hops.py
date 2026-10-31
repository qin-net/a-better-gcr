"""Experiment F: what path lengths does the training signal actually use?

The SFT pipeline builds ground_truth_paths with nx.all_shortest_paths, which
has NO hop limit. Inference, however, constrains decoding to the K-hop trie.
Paths longer than K are therefore training examples the decoder can never
reproduce.

Reports the hop-length distribution of the shortest q->a paths per question.
"""

import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from rog_io import iter_rows  # noqa: E402


def shortest_hop(adj, starts, goals):
    """Min hops from any start to any goal (unweighted BFS)."""
    goals = set(goals)
    seen = set(starts)
    frontier = [(s, 0) for s in starts]
    while frontier:
        nxt = []
        for u, d in frontier:
            if u in goals:
                return d
            for v in adj.get(u, ()):
                if v not in seen:
                    seen.add(v)
                    nxt.append((v, d + 1))
        frontier = nxt
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("train", nargs="+")
    args = ap.parse_args()

    hops = collections.Counter()
    n = 0
    for path in args.train:
        for row in iter_rows(path):
            q, a = row["q_entity"], row["a_entity"]
            if not q or not a:
                continue
            n += 1
            adj = collections.defaultdict(set)
            for h, r, t in row["graph"]:
                adj[h].add(t)
            d = shortest_hop(adj, q, a)
            hops[d if d is not None else -1] += 1

    print(f"questions={n}")
    print(f"{'hops':>6}{'count':>10}{'share':>9}")
    for k in sorted(hops):
        label = "unreachable" if k == -1 else str(k)
        print(f"{label:>6}{hops[k]:>10}{hops[k] / n:>9.1%}")

    long_share = sum(v for k, v in hops.items() if k == -1 or k > 2) / n
    print(f"\nshare of training questions whose shortest path is >2 hops or "
          f"unreachable: {long_share:.1%}")

    dest = os.path.join(os.path.dirname(__file__), "..", "out", "path_hops.json")
    json.dump({"questions": n, "hops": {str(k): v for k, v in hops.items()},
               "long_or_unreachable_share": long_share}, open(dest, "w"), indent=1)
    print("wrote out/path_hops.json")


if __name__ == "__main__":
    main()
