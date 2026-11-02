"""Build the A–E training sets for the training-side repair comparison.

Every variant keeps all training questions and writes the official
`ground_truth_paths` column; questions with no path are kept with an empty
list, which the official `input_formatter` skips, exactly as upstream.

  A  official: shortest paths in the question's own subgraph, directed graph
  B  same, on the multi-relation graph with reverse steps
     (graph-constrained-reasoning/src/multi_relation_graph.py, `--graph multi` at inference)
  C  B, but CWQ paths may only use relations from the question's SPARQL;
     falls back to B when the constrained search finds nothing
  D  C + pool-repaired paths (experiment N) for CWQ questions C leaves empty, <=2 hops
  E  C + pool-repaired paths, <=3 hops (needs a 3-hop trie at inference)

The official undirected graph is not a variant: it keeps one relation per
entity pair, so 36.7% of CWQ questions would have no SPARQL-constrained path
its trie can decode (FINDINGS.md section O).

WebQSP has no SPARQL in this repo, so its paths are identical in B–E.

Repaired paths come from out/constrained_paths.jsonl (`paths_with_reverse`),
filtered like FINDINGS.md section N: no type relations anywhere on the path
and no start at a class-like node (the tail of any type relation in the pool).
Steps are written in traversal order, which is how the official undirected
graph prints a reversed edge.

Output: out/train_variants/<V>/{cwq,webqsp}.jsonl and out/train_variants/stats.json

Usage:
  python -I train_variants/build_variants.py --cwq data/hf/cwq_full/train-*.parquet \
      --webqsp data/hf/train.parquet --sparql data/hf/cwq_sparql_train.parquet \
      --repaired out/constrained_paths.jsonl
"""

import argparse
import collections
import importlib.util
import json
import os
import re
import sys
import time

import networkx as nx
import pyarrow.parquet as pq

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "experiments"))
from rog_io import iter_rows  # noqa: E402

_spec = importlib.util.spec_from_file_location("multi_relation_graph", os.path.join(
    HERE, "..", "..", "graph-constrained-reasoning", "src", "multi_relation_graph.py"))
multi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(multi)

PRED_RE = re.compile(r"ns:([a-z_0-9]+\.[a-z_0-9]+\.[a-z_0-9]+)")
TYPE_RELS = {"common.topic.notable_types", "people.person.gender", "type.object.type",
             "common.topic.notable_for", "people.marriage.type_of_union",
             "government.government_position_held.basic_title"}
VARIANTS = "ABCDE"


# Copied verbatim from graph-constrained-reasoning/src/utils/graph_utils.py;
# importing it fails on Python 3.9 because of its `nx.DiGraph | nx.Graph` annotation.
def build_graph(graph, undirected=False):
    if undirected:
        G = nx.Graph()
    else:
        G = nx.DiGraph()
    for triplet in graph:
        h, r, t = triplet
        G.add_edge(h.strip(), t.strip(), relation=r.strip())
    return G


def get_truth_paths(q_entity, a_entity, graph):
    paths = []
    for h in q_entity:
        if h not in graph:
            continue
        for t in a_entity:
            if t not in graph:
                continue
            try:
                for p in nx.all_shortest_paths(graph, h, t):
                    paths.append(p)
            except:  # noqa: E722
                pass
    result_paths = []
    for p in paths:
        tmp = []
        for i in range(len(p) - 1):
            u = p[i]
            v = p[i + 1]
            tmp.append((u, graph[u][v]["relation"], v))
        result_paths.append(tmp)
    return result_paths


def load_sparql_relations(path):
    t = pq.read_table(path, columns=["ID", "sparql"]).to_pydict()
    return {i: set(PRED_RE.findall(s or "")) for i, s in zip(t["ID"], t["sparql"])}


def usable(paths):
    return [p for p in paths if p]


def repaired_paths(path, class_like, max_hops):
    """id -> filtered repaired paths with at most max_hops steps."""
    out = {}
    for line in open(path):
        r = json.loads(line)
        keep = [[(u, rel, v) for u, rel, v, _ in p] for p in r["paths_with_reverse"]
                if len(p) <= max_hops and p[0][0] not in class_like
                and not any(s[1] in TYPE_RELS for s in p)]
        if keep:
            out[r["id"]] = keep
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cwq", nargs="+", required=True)
    ap.add_argument("--webqsp", nargs="+", required=True)
    ap.add_argument("--sparql", required=True)
    ap.add_argument("--repaired", required=True)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "out",
                                                  "train_variants"))
    args = ap.parse_args()

    t0 = time.time()
    gold = load_sparql_relations(args.sparql)
    files = {v: {} for v in VARIANTS}
    for v in VARIANTS:
        os.makedirs(os.path.join(args.out, v), exist_ok=True)
        for ds in ("cwq", "webqsp"):
            files[v][ds] = open(os.path.join(args.out, v, f"{ds}.jsonl"), "w")

    # Pass 1: A/B/C per question, written immediately; D/E for CWQ deferred
    # until the class-like node set (needs every graph) is known.
    class_like = set()
    c_empty = []
    stats = collections.defaultdict(collections.Counter)
    for ds, paths in (("webqsp", args.webqsp), ("cwq", args.cwq)):
        for p in paths:
            for row in iter_rows(p):
                for h, r, t in row["graph"]:
                    if r in TYPE_RELS:
                        class_like.add(t.strip())
                base = {k: row[k] for k in ("id", "question", "q_entity", "a_entity")}
                a = usable(get_truth_paths(row["q_entity"], row["a_entity"],
                                           build_graph(row["graph"])))
                b = usable(multi.get_truth_paths(row["q_entity"], row["a_entity"],
                                                 multi.build_graph(row["graph"])))
                c, how = b, "webqsp_no_sparql"
                if ds == "cwq":
                    g = gold.get(row["id"], set())
                    sub = [x for x in row["graph"] if x[1].strip() in g]
                    c = usable(multi.get_truth_paths(row["q_entity"], row["a_entity"],
                                                     multi.build_graph(sub)))
                    how = "constrained"
                    if not c:
                        c, how = b, ("fallback_b" if b else "empty")
                    if not c:
                        c_empty.append(base)
                stats[ds]["questions"] += 1
                stats[ds]["C_" + how] += 1
                for v, ps in (("A", a), ("B", b), ("C", c)):
                    stats[ds][v + "_with_paths"] += bool(ps)
                    stats[ds][v + "_paths"] += len(ps)
                    files[v][ds].write(json.dumps({**base, "ground_truth_paths": ps},
                                                  ensure_ascii=False) + "\n")
                if ds == "webqsp" or c:
                    for v in "DE":
                        stats[ds][v + "_with_paths"] += bool(c)
                        stats[ds][v + "_paths"] += len(c)
                        files[v][ds].write(json.dumps({**base, "ground_truth_paths": c},
                                                      ensure_ascii=False) + "\n")
                if stats[ds]["questions"] % 2000 == 0:
                    print(f"  {ds} {stats[ds]['questions']}  ({time.time() - t0:.0f}s)",
                          flush=True)
    print(f"pass 1 done, class-like nodes {len(class_like)}  ({time.time() - t0:.0f}s)")

    # Pass 2: CWQ questions with no C path get repaired paths in D (<=2) and E (<=3).
    for v, hops in (("D", 2), ("E", 3)):
        rep = repaired_paths(args.repaired, class_like, hops)
        for base in c_empty:
            ps = rep.get(base["id"], [])
            stats["cwq"][v + "_repaired"] += bool(ps)
            stats["cwq"][v + "_with_paths"] += bool(ps)
            stats["cwq"][v + "_paths"] += len(ps)
            files[v]["cwq"].write(json.dumps({**base, "ground_truth_paths": ps},
                                             ensure_ascii=False) + "\n")
    for v in VARIANTS:
        for f in files[v].values():
            f.close()

    with open(os.path.join(args.out, "stats.json"), "w") as f:
        json.dump(stats, f, indent=1)
    for ds in ("webqsp", "cwq"):
        s = stats[ds]
        print(f"\n{ds}: {s['questions']} questions")
        for v in VARIANTS:
            print(f"  {v}: {s[v + '_with_paths']:>6} with paths  {s[v + '_paths']:>8} paths"
                  + (f"  (+{s[v + '_repaired']} repaired)" if s[v + "_repaired"] else ""))
        print("  C source:", {k[2:]: n for k, n in s.items() if k.startswith("C_")
                              and k not in ("C_with_paths", "C_paths")})
    print(f"wrote {args.out}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
