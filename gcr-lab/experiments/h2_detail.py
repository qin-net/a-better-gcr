"""Experiment H2: exact repair-distance breakdown for dropped CWQ questions.

One BFS per question against the merged CWQ+WebQSP pool, depth capped at 6.
Classifies each dropped question into:
  repaired@d   -- shortest q->gold path has d hops
  absent       -- gold answer entity appears nowhere in the pool
  too_deep     -- present but no path within 6 hops
"""

import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from rog_io import iter_rows  # noqa: E402


def bfs(adj, starts, goals, cap=6, node_cap=400000):
    goals = set(goals)
    seen = set(starts)
    frontier = [(s, 0) for s in starts]
    explored = 0
    while frontier:
        nxt = []
        for u, d in frontier:
            explored += 1
            if u in goals:
                return d
            if d >= cap or explored > node_cap:
                continue
            for v in adj.get(u, ()):
                if v not in seen:
                    seen.add(v)
                    nxt.append((v, d + 1))
        frontier = nxt
        if explored > node_cap:
            return None
    return None


def main():
    cwq = ["data/hf/cwq_train_0000.parquet", "data/hf/cwq_train_0001.parquet"]
    webqsp = ["data/hf/train.parquet"]

    pool = collections.defaultdict(set)
    rows = []
    for p in cwq:
        for row in iter_rows(p):
            rows.append(row)
            for h, r, t in row["graph"]:
                pool[h].add(t)
    for p in webqsp:
        for row in iter_rows(p):
            for h, r, t in row["graph"]:
                pool[h].add(t)

    dist = collections.Counter()
    absent, too_deep = 0, 0
    multi_answer = collections.Counter()
    for row in rows:
        q, a = row["q_entity"], row["a_entity"]
        if not q or not a:
            continue
        sub = collections.defaultdict(set)
        for h, r, t in row["graph"]:
            sub[h].add(t)
        if bfs(sub, q, a, cap=99) is not None:
            continue  # not dropped
        present = [x for x in a if x in pool]
        if not present:
            absent += 1
            dist["answer absent"] += 1
            continue
        d = bfs(pool, q, present)
        if d is None:
            too_deep += 1
            dist[">6 hops"] += 1
        else:
            dist[d] += 1
            multi_answer[str(d)] += len(present) > 1

    total = sum(dist.values())
    print(f"dropped CWQ questions: {total}")
    print(f"{'shortest q->gold distance':>30}{'count':>8}{'cumulative':>12}")
    cum = 0
    for k in sorted([x for x in dist if isinstance(x, int)]):
        cum += dist[k]
        print(f"{k:>30}{dist[k]:>8}{cum / total:>12.1%}")
    print(f"{'answer absent from pool':>30}{absent:>8}{'':>12}")
    print(f"{'>6 hops / search cap':>30}{too_deep:>8}{'':>12}")
    print(f"\nrepairable at <=3 hops: {sum(v for k, v in dist.items() if isinstance(k, int) and k <= 3)}")

    dest = os.path.join(os.path.dirname(__file__), "..", "out", "stage2_detail.json")
    json.dump({"dropped": total,
               "by_distance": {str(k): v for k, v in dist.items()},
               "absent": absent, "too_deep": too_deep},
              open(dest, "w"), indent=1)
    print("wrote out/stage2_detail.json")


if __name__ == "__main__":
    main()
