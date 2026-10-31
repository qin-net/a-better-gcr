"""Experiment M: are pool-repaired paths semantically right?

Each CWQ question ships with the SPARQL query that defines its answer. The
Freebase predicates in that query are the relations a correct reasoning path
should use. A path's *precision* is the share of its relations that appear in
the query; a path is *consistent* when every relation does.

Shortest paths are only weak supervision, so precision is reported for two
groups under the same metric:
  baseline  -- questions the official pipeline keeps: all shortest paths in
               the question's own subgraph (what GCR trains on today)
  repaired  -- dropped questions with paths from the pool (experiment L),
               split by hop count

Relation names are matched exactly. RoG subgraphs contain both directions of
many relations under different names, so the absolute numbers are a lower
bound; the comparison between the two groups is what matters.

Usage:
  python -I experiments/m_path_quality.py data/hf/cwq_full/train-*.parquet \
      --sparql data/hf/cwq_sparql_train.parquet --baseline-sample 3000
"""

import argparse
import collections
import json
import os
import random
import re
import sys

import pyarrow.parquet as pq

sys.path.insert(0, os.path.dirname(__file__))
from rog_io import iter_rows  # noqa: E402

PRED_RE = re.compile(r"ns:([a-z_0-9]+\.[a-z_0-9]+\.[a-z_0-9]+)")


def sparql_relations(path):
    t = pq.read_table(path, columns=["ID", "sparql"]).to_pydict()
    return {i: set(PRED_RE.findall(s or "")) for i, s in zip(t["ID"], t["sparql"])}


def all_shortest(adj, starts, goals):
    """All shortest node paths, unbounded depth (official get_truth_paths)."""
    goals = set(goals)
    dist = {s: 0 for s in starts}
    parents = collections.defaultdict(list)
    frontier = list(dist)
    hit = [s for s in frontier if s in goals]
    d = 0
    while not hit and frontier:
        d += 1
        nxt = []
        for u in frontier:
            for v in adj.get(u, ()):
                if v not in dist:
                    dist[v] = d
                    nxt.append(v)
                if dist[v] == d:
                    parents[v].append(u)
        frontier = nxt
        hit = [v for v in frontier if v in goals]
    out = []

    def back(v, suffix):
        if len(out) >= 50:
            return
        if dist[v] == 0:
            out.append([v] + suffix)
            return
        for u in parents[v]:
            back(u, [v] + suffix)

    for g in hit:
        back(g, [])
    return d if hit else None, out


def score(paths, gold_rels):
    """Per-question summary over its relation sequences."""
    if not paths:
        return None
    precs = [sum(r in gold_rels for r in rels) / len(rels) for rels in paths]
    return {"best": max(precs), "mean": sum(precs) / len(precs),
            "any_consistent": any(p == 1.0 for p in precs),
            "share_consistent": sum(p == 1.0 for p in precs) / len(precs),
            "any_overlap": any(p > 0 for p in precs)}


def aggregate(scores):
    scores = [s for s in scores if s]
    n = len(scores)
    if not n:
        return {"n": 0}
    return {"n": n,
            "best_precision": sum(s["best"] for s in scores) / n,
            "mean_precision": sum(s["mean"] for s in scores) / n,
            "q_with_consistent_path": sum(s["any_consistent"] for s in scores) / n,
            "share_of_paths_consistent": sum(s["share_consistent"] for s in scores) / n,
            "q_with_no_overlap": 1 - sum(s["any_overlap"] for s in scores) / n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cwq", nargs="+")
    ap.add_argument("--sparql", required=True)
    ap.add_argument("--pool-paths", default=os.path.join(
        os.path.dirname(__file__), "..", "out", "pool_paths.jsonl"))
    ap.add_argument("--baseline-sample", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    gold = sparql_relations(args.sparql)
    print(f"SPARQL queries: {len(gold)}")

    base_scores = collections.defaultdict(list)
    matched = missing = 0
    rng = random.Random(args.seed)
    for p in args.cwq:
        for row in iter_rows(p):
            q, a = row["q_entity"], row["a_entity"]
            if not q or not a or row["id"] not in gold:
                missing += row["id"] not in gold
                continue
            if rng.random() > args.baseline_sample / 22088:
                continue
            adj = collections.defaultdict(dict)
            for h, r, t in row["graph"]:
                adj[h][t] = r
            d, node_paths = all_shortest(adj, q, a)
            if not d:
                continue
            matched += 1
            rel_paths = [[adj[u][v] for u, v in zip(np_, np_[1:])] for np_ in node_paths]
            base_scores[d].append(score(rel_paths, gold[row["id"]]))
    print(f"baseline questions scored: {matched}   rows without SPARQL: {missing}")

    rep_scores = collections.defaultdict(list)
    no_sparql = 0
    examples = collections.defaultdict(list)
    for line in open(args.pool_paths):
        row = json.loads(line)
        if row["hops"] is None:
            continue
        if row["id"] not in gold:
            no_sparql += 1
            continue
        rel_paths = [[r for _, r, _ in p] for p in row["ground_truth_paths"]]
        s = score(rel_paths, gold[row["id"]])
        rep_scores[row["hops"]].append(s)
        bucket = "consistent" if s and s["any_consistent"] else "no_overlap" if s and not s["any_overlap"] else None
        if bucket and len(examples[(row["hops"], bucket)]) < 3:
            examples[(row["hops"], bucket)].append({
                "question": row["question"], "answer": row["a_entity"][:3],
                "sparql_relations": sorted(gold[row["id"]]),
                "path": row["ground_truth_paths"][0]})

    out = {"baseline": {}, "repaired": {}}
    print(f"\n{'group':<14}{'n':>6}{'best prec':>11}{'mean prec':>11}"
          f"{'q w/ consistent':>17}{'paths consistent':>18}{'q no overlap':>14}")

    def show(name, agg):
        if agg["n"]:
            print(f"{name:<14}{agg['n']:>6}{agg['best_precision']:>11.1%}"
                  f"{agg['mean_precision']:>11.1%}{agg['q_with_consistent_path']:>17.1%}"
                  f"{agg['share_of_paths_consistent']:>18.1%}{agg['q_with_no_overlap']:>14.1%}")

    for d in sorted(base_scores):
        out["baseline"][d] = aggregate(base_scores[d])
        show(f"baseline {d}h", out["baseline"][d])
    out["baseline"]["all"] = aggregate([s for v in base_scores.values() for s in v])
    show("baseline all", out["baseline"]["all"])
    for d in sorted(rep_scores):
        out["repaired"][d] = aggregate(rep_scores[d])
        show(f"repaired {d}h", out["repaired"][d])
    out["repaired"]["all"] = aggregate([s for v in rep_scores.values() for s in v])
    show("repaired all", out["repaired"]["all"])
    print(f"\nrepaired rows without SPARQL: {no_sparql}")

    for (d, bucket), exs in sorted(examples.items()):
        print(f"\n--- repaired {d}h, {bucket} ---")
        for ex in exs:
            print(f"  Q: {ex['question'][:90]}   A: {ex['answer']}")
            print(f"     SPARQL: {ex['sparql_relations']}")
            print(f"     path:   {' -> '.join(f'{h} [{r}]' for h, r, _ in ex['path'])} -> {ex['path'][-1][2]}")

    out["examples"] = {f"{d}h_{b}": v for (d, b), v in examples.items()}
    dest = os.path.join(os.path.dirname(__file__), "..", "out", "path_quality.json")
    json.dump(out, open(dest, "w"), ensure_ascii=False, indent=1)
    print("\nwrote out/path_quality.json")


if __name__ == "__main__":
    main()
