"""Build the v2 training sets that fix the two path-selection problems of C/D.

Problems found in the 2026-11-04 decoding run (FINDINGS.md section R):
  1. WebQSP questions were never SPARQL-constrained in C/D/E (the builder
     assumed WebQSP had no SPARQL); their paths were plain multi-graph
     shortest paths, only 29.8% of the chosen ones faithful (A: 73.6%).
  2. Training uses one path per question, picked by (length, alphabetical
     order). On the multi-graph with reverse steps that picks a path with a
     reversed step for 59.5% of WebQSP and 79.2% of CWQ questions, although
     about half of them have a forward, faithful path of the same length.

Variants (2x2 over the two fixes, plus D2):
  C_wq   WebQSP SPARQL-constrained too, old selection (random 10, then alphabetical)
  C_fwd  paths exactly as in C, forward-first selection that does not look at SPARQL
  C2     both fixes, full ranked selection
  D2     C2 + pool-repaired CWQ paths (<= 2 hops), full ranked selection

Full ranked selection orders a question's paths by
  (relations not all inside one SPARQL parse, reversed steps, type/constraint
   relations, length, text);
forward-first drops the first key. Both keep the first 10, and the packed row
carries "path_order": "ranked" so train_cuda_lora.py trains on the first path
as stored instead of re-sorting.

Relations are read from SPARQL with the build_gold_relations.py pattern, which
keeps relations with more than three segments whole (C used a 3-segment
pattern); the stats report how many CWQ questions that changes.

Usage (from gcr-lab/, about 10 minutes):
  .venv/bin/python -I train_variants/build_v2.py
"""

import argparse
import collections
import glob
import gzip
import importlib.util
import json
import os
import random
import re
import time

import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)
_spec = importlib.util.spec_from_file_location("build_variants", os.path.join(HERE, "build_variants.py"))
v1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v1)
multi, iter_rows, TYPE_RELS = v1.multi, v1.iter_rows, v1.TYPE_RELS

PRED_RE = re.compile(r"ns:([a-z_0-9]+(?:\.[a-z_0-9]+){2,})")
CAP = 10
VARIANTS = ("C_wq", "C_fwd", "C2", "D2")


def path_text(p):
    return " -> ".join([p[0][0]] + [x for _, r, t in p for x in (r, t)])


def rank_key(p, parses, n_reversed):
    """parses=None ranks without SPARQL (forward-first only)."""
    rels = {r for _, r, _ in p}
    unfaithful = parses is not None and not any(rels <= g for g in parses)
    return (unfaithful, n_reversed, sum(r in TYPE_RELS for r in rels), len(p), path_text(p))


def ranked(paths, parses, n_reversed):
    return sorted(paths, key=lambda p: rank_key(p, parses, n_reversed(p)))[:CAP]


def sampled(paths, qid):
    """Old pack.py behaviour: a seeded random 10; training then sorts by (length, text)."""
    return random.Random(qid).sample(paths, CAP) if len(paths) > CAP else paths


def constrained(row, allowed):
    sub = [x for x in row["graph"] if x[1].strip() in allowed]
    return v1.usable(multi.get_truth_paths(row["q_entity"], row["a_entity"], multi.build_graph(sub)))


def webqsp_parses(paths):
    out = {}
    for path in paths:
        for q in json.load(open(path))["Questions"]:
            out[q["QuestionId"]] = [set(PRED_RE.findall(p["Sparql"] or "")) for p in q["Parses"]]
    return out


def cwq_parses(path):
    t = pq.read_table(path, columns=["ID", "sparql"]).to_pydict()
    return {i: [set(PRED_RE.findall(s or ""))] for i, s in zip(t["ID"], t["sparql"])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cwq", nargs="+", default=sorted(glob.glob(os.path.join(LAB, "data/hf/cwq_full/train-*.parquet"))))
    ap.add_argument("--webqsp", nargs="+", default=[os.path.join(LAB, "data/hf/train.parquet")])
    ap.add_argument("--cwq-sparql", default=os.path.join(LAB, "data/hf/cwq_sparql_train.parquet"))
    ap.add_argument("--webqsp-sparql", nargs="+",
                    default=[os.path.join(LAB, "data/webqsp_raw/WebQSP/data/WebQSP.train.json")])
    ap.add_argument("--repaired", default=os.path.join(LAB, "out/constrained_paths.jsonl"))
    ap.add_argument("--dst", default=os.path.join(HERE, "data"))
    args = ap.parse_args()
    if not args.cwq:
        ap.error("no CWQ parquet files found; pass --cwq")

    t0 = time.time()
    gold = {**webqsp_parses(args.webqsp_sparql), **cwq_parses(args.cwq_sparql)}
    old_cwq = v1.load_sparql_relations(args.cwq_sparql)
    out = {v: gzip.open(os.path.join(args.dst, f"{v}.jsonl.gz"), "wt", encoding="utf-8") for v in VARIANTS}
    stats = {v: collections.Counter() for v in VARIANTS}
    source = collections.Counter()
    chosen = {v: collections.Counter() for v in VARIANTS}
    class_like, cwq_empty = set(), []

    def write(v, base, paths, how, parses, n_reversed):
        if not paths:
            return
        row = {**base, "ground_truth_paths": paths}
        if how == "ranked":
            row["path_order"] = "ranked"
            first = paths[0]
        else:
            first = min(paths, key=lambda p: (len(p), path_text(p)))
        ds = "cwq" if "_" in base["id"] else "webqsp"
        stats[v][ds + "_questions"] += 1
        stats[v][ds + "_paths"] += len(paths)
        c = chosen[v]
        c[ds] += 1
        c[ds + "_faithful"] += any({r for _, r, _ in first} <= g for g in parses)
        c[ds + "_reversed"] += n_reversed(first) > 0
        out[v].write(json.dumps(row, ensure_ascii=False) + "\n")

    for ds, files in (("webqsp", args.webqsp), ("cwq", args.cwq)):
        for f in files:
            for row in iter_rows(f):
                for h, r, t in row["graph"]:
                    if r in TYPE_RELS:
                        class_like.add(t.strip())
                base = {k: row[k] for k in ("id", "question", "q_entity", "a_entity")}
                parses = [g for g in gold.get(row["id"], []) if g]
                forward = {(h.strip(), r.strip(), t.strip()) for h, r, t in row["graph"]}
                n_rev = lambda p: sum(tuple(s) not in forward for s in p)  # noqa: E731
                b = v1.usable(multi.get_truth_paths(row["q_entity"], row["a_entity"],
                                                    multi.build_graph(row["graph"])))
                c = constrained(row, set().union(*parses)) if parses else []
                how = "constrained" if c else ("fallback_b" if b else "empty")
                source[f"{ds}_{how}"] += 1
                if ds == "cwq" and old_cwq.get(row["id"], set()) != set().union(*parses):
                    source["cwq_relation_set_changed"] += 1
                c = c or b
                if ds == "webqsp":
                    old_c = b
                elif old_cwq.get(row["id"], set()) == set().union(*parses):
                    old_c = c
                else:
                    old_c = constrained(row, old_cwq.get(row["id"], set())) or b
                write("C_wq", base, sampled(c, row["id"]), "sampled", parses, n_rev)
                write("C_fwd", base, ranked(old_c, None, n_rev), "ranked", parses, n_rev)
                write("C2", base, ranked(c, parses, n_rev), "ranked", parses, n_rev)
                if c or ds == "webqsp":
                    write("D2", base, ranked(c, parses, n_rev), "ranked", parses, n_rev)
                else:
                    cwq_empty.append((base, parses))
                n = sum(source.values()) - source["cwq_relation_set_changed"]
                if n % 4000 == 0:
                    print(f"  {n} questions ({time.time() - t0:.0f}s)", flush=True)

    # D2: CWQ questions with no path in their own subgraph get pool-repaired paths.
    rep = {}
    for line in open(args.repaired):
        r = json.loads(line)
        rep[r["id"]] = [p for p in r["paths_with_reverse"] if len(p) <= 2 and p[0][0] not in class_like
                        and not any(s[1] in TYPE_RELS for s in p)]
    for base, parses in cwq_empty:
        # Repaired steps are (u, r, v, reversed); the pool, not the subgraph, decides direction.
        paths = rep.get(base["id"], [])
        rev = {path_text([s[:3] for s in p]): sum(s[3] for s in p) for p in paths}
        n_rev = lambda p: rev[path_text(p)]  # noqa: E731
        source["cwq_repaired_d2"] += bool(paths)
        write("D2", base, ranked([[s[:3] for s in p] for p in paths], parses, n_rev), "ranked",
              parses, n_rev)

    for f in out.values():
        f.close()
    summary = {"source": dict(source), "variants": {v: dict(stats[v]) for v in VARIANTS},
               "chosen_path": {v: {f"{ds}_{k}": round(chosen[v][f"{ds}_{k}"] / chosen[v][ds], 4)
                                   for ds in ("webqsp", "cwq") for k in ("faithful", "reversed")}
                               for v in VARIANTS}}
    with open(os.path.join(args.dst, "v2_stats.json"), "w") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps(summary, indent=1))
    print(f"wrote {args.dst}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
