"""Experiment E: training coverage gap.

The official SFT pipeline keeps a question only if
`get_truth_paths(q_entity, a_entity, subgraph)` is non-empty. Every other
question silently contributes zero training examples.

This script reproduces that filter on the RoG training split and splits the
dropped questions into two kinds, because they need different repairs:
  A) answer entity absent from the subgraph   -> knowledge is missing
  B) answer present but unreachable (directed)

Usage: python -I experiments/e_train_coverage.py data/hf/train.parquet
"""

import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from rog_io import iter_rows  # noqa: E402


def bfs_reach(adj, starts):
    seen = set(starts)
    frontier = list(starts)
    while frontier:
        nxt = []
        for u in frontier:
            for v in adj.get(u, ()):
                if v not in seen:
                    seen.add(v)
                    nxt.append(v)
        frontier = nxt
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("train", nargs="+")
    args = ap.parse_args()

    n = 0
    kept = 0
    dropped_absent = 0
    dropped_unreach = 0
    path_chunks = 0
    unreach_examples = []
    kept_degrees = []
    dropped_degrees = []
    rel_of_dropped = collections.Counter()
    multi_answer = 0

    for path in args.train:
        for row in iter_rows(path):
            n += 1
            q = row["q_entity"]
            ans = row["a_entity"]
            if not q or not ans:
                dropped_absent += 1
                continue
            adj = collections.defaultdict(set)
            for h, r, t in row["graph"]:
                adj[h].add(t)

            reach = bfs_reach(adj, q)
            hit = [a for a in ans if a in reach]
            present = [a for a in ans if a in adj or a in {t for _, _, t in row["graph"]}]

            if hit:
                kept += 1
                path_chunks += len(hit)
                kept_degrees.append(len(adj))
            else:
                if present:
                    dropped_unreach += 1
                    dropped_degrees.append(len(adj))
                    if len(unreach_examples) < 8:
                        # what does the answer look like from the graph side?
                        inbound = [(h, r) for h, r, t in row["graph"] if t == present[0]]
                        unreach_examples.append({
                            "question": row["question"],
                            "q_entity": q,
                            "answer": ans,
                            "inbound_edges_to_answer": inbound[:5],
                            "subgraph_nodes": len(adj),
                        })
                else:
                    dropped_absent += 1
                    dropped_degrees.append(len(adj))

            if len(ans) > 1:
                multi_answer += 1

    print(f"train rows                      {n}")
    print(f"kept (path to gold exists)      {kept}  ({kept / n:.1%})")
    print(f"dropped: answer absent          {dropped_absent}  ({dropped_absent / n:.1%})")
    print(f"dropped: present, unreachable   {dropped_unreach}  ({dropped_unreach / n:.1%})")
    print(f"dropped total                   {dropped_absent + dropped_unreach}"
          f"  ({(dropped_absent + dropped_unreach) / n:.1%})")
    print(f"gold path chunks per kept q     {path_chunks / max(1, kept):.2f}")
    print(f"median subgraph out-degree      kept={sorted(kept_degrees)[len(kept_degrees)//2]}"
          f"  dropped={sorted(dropped_degrees)[len(dropped_degrees)//2] if dropped_degrees else '-'}")

    print("\nexamples where the answer exists in the subgraph but cannot be reached:")
    for ex in unreach_examples:
        print(f"  Q: {ex['question'][:70]}")
        print(f"     q={ex['q_entity']}  a={ex['answer']}")
        print(f"     inbound to answer: {ex['inbound_edges_to_answer']}")

    out = {
        "train_rows": n,
        "kept": kept,
        "dropped_answer_absent": dropped_absent,
        "dropped_present_unreachable": dropped_unreach,
        "kept_ratio": kept / n,
        "dropped_ratio": (dropped_absent + dropped_unreach) / n,
        "unreachable_examples": unreach_examples,
    }
    dest = os.path.join(os.path.dirname(__file__), "..", "out", "train_coverage.json")
    json.dump(out, open(dest, "w"), ensure_ascii=False, indent=1)
    print("\nwrote out/train_coverage.json")


if __name__ == "__main__":
    main()
