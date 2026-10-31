"""Experiment B: can structural rules recover a held-out edge?

Setup, designed to avoid leakage:
  1. Build a graph from the *train* subgraphs (the pool the model would have).
  2. For each edge in the test subgraphs, keep it only if its (h,r,t) is not
     already in the train graph -- those are the "missing" edges we care about.
     Crucially, we also require (h, r, ?) to have at least one other tail in
     the train graph, so the model has at least a local signal to work with.
  3. For each such edge, remove it (it was never there), then rank candidate
     tails by several rules and look at where the true tail lands.

Rules compared
  random      -- uniform
  popularity  -- tail frequency in the train graph
  meta-path   -- h -r1-> x -r2-> t, aggregated over x and r1
  inverse     -- if edge is (h, r, t), check whether (t, r_inv, h) exists
                 in train; score by the inverse pair's measured support
"""

import argparse
import collections
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
from rog_io import iter_rows  # noqa: E402


def load_graph(path, limit=0):
    out = collections.defaultdict(set)
    hr_tails = collections.defaultdict(set)
    n = 0
    for row in iter_rows(path):
        for h, r, t in row["graph"]:
            out[h].add((r, t))
            hr_tails[(h, r)].add(t)
        n += 1
        if limit and n >= limit:
            break
    return out, hr_tails


def inverse_map(out, hr_tails):
    """r -> r' when (t, r', h) holds for most (h, r, t)."""
    hits = collections.Counter()
    supp = collections.Counter()
    for h, edges in out.items():
        for r, t in edges:
            supp[r] += 1
            for r2, t2 in out.get(t, ()):
                if t2 == h and r2 != r:
                    hits[(r, r2)] += 1
    inv = {}
    for (r, r2), n in hits.items():
        if r in inv or r2 in inv:
            continue
        if n / max(1, min(supp[r], supp[r2])) >= 0.5 and n >= 20:
            inv[r] = r2
            inv[r2] = r
    return inv


def meta_scores(h, r, out, depth=2, max_expand=200):
    """Score tails t reachable by h -r1-> x -r-> t, then one more hop."""
    scores = collections.Counter()
    frontier = [(h, 1.0)]
    seen = {h}
    for _ in range(depth):
        nxt = []
        for node, w in frontier[:max_expand]:
            for r1, x in out.get(node, ()):
                if r1 == r:
                    continue
                if x not in seen:
                    seen.add(x)
                    nxt.append((x, w * 0.5))
                if (r, x) in out.get(node, ()):  # direct edge at this hop
                    scores[x] += w
                for r2, t in out.get(x, ()):
                    if r2 == r and t != h:
                        scores[t] += w * 0.5
        frontier = nxt
        if not frontier:
            break
    return scores


def rank_of(scores, gold, universe):
    """1-based rank of gold among universe; ties broken deterministically."""
    items = [(scores.get(t, 0.0), t) for t in universe]
    items.sort(key=lambda kv: (-kv[0], kv[1]))
    for i, (_, t) in enumerate(items, 1):
        if t == gold:
            return i
    return len(items) + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("train")
    ap.add_argument("test")
    ap.add_argument("--train-limit", type=int, default=0)
    ap.add_argument("--max-eval", type=int, default=800)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    print("loading train graph ...")
    out, hr_tails = load_graph(args.train, args.train_limit)
    inv = inverse_map(out, hr_tails)
    print(f"  train edges={sum(len(v) for v in out.values())} "
          f"entities={len(out)} inverse pairs={len(inv) // 2}")

    pop = collections.Counter()
    rel_tails = collections.defaultdict(set)
    for h, edges in out.items():
        for r, t in edges:
            pop[t] += 1
            rel_tails[r].add(t)
    top_pop = [t for t, _ in pop.most_common(3000)]
    print(f"  candidate pool: relation tails + top-{len(top_pop)} frequent entities")

    metrics = {k: {"mrr": 0.0, "h1": 0, "h3": 0, "h10": 0}
               for k in ("random", "popularity", "meta-path", "inverse+meta")}
    n_eval = 0
    seen_q = set()

    for row in iter_rows(args.test):
        for h, r, t in row["graph"]:
            if n_eval >= args.max_eval:
                break
            if (r, t) in out.get(h, ()):
                continue  # already known -- not a missing edge
            if (h, r) not in hr_tails:
                continue  # no local signal; not fair to any rule
            gold = t
            cand = sorted(rel_tails[r]) + [x for x in top_pop if x not in rel_tails[r]]
            cand = [x for x in cand if x != h and x not in hr_tails[(h, r)]]
            if gold not in cand:
                cand.append(gold)
            n_eval += 1

            m = meta_scores(h, r, out)
            sc = {
                "random": {x: rng.random() for x in cand},
                "popularity": {x: float(pop[x]) for x in cand},
                "meta-path": {x: m.get(x, 0.0) for x in cand},
                "inverse+meta": {x: m.get(x, 0.0) + (3.0 if x in out.get(h, ())
                                                     else 0.0) for x in cand},
            }
            # inverse rule: if (t, r_inv, h) exists, t gets a strong prior
            rin = inv.get(r)
            if rin:
                for x in cand:
                    if (rin, h) in out.get(x, ()):
                        sc["inverse+meta"][x] += 5.0
            for name, s in sc.items():
                rk = rank_of(s, gold, cand)
                d = metrics[name]
                d["mrr"] += 1.0 / rk
                d["h1"] += rk <= 1
                d["h3"] += rk <= 3
                d["h10"] += rk <= 10
        if n_eval >= args.max_eval:
            break

    print(f"\nevaluated missing edges: {n_eval}")
    print(f"{'rule':<16}{'MRR':>8}{'Hit@1':>8}{'Hit@3':>8}{'Hit@10':>8}")
    result = {}
    for name, d in metrics.items():
        mrr = d["mrr"] / n_eval
        h1, h3, h10 = (d[k] / n_eval for k in ("h1", "h3", "h10"))
        print(f"{name:<16}{mrr:>8.3f}{h1:>8.3f}{h3:>8.3f}{h10:>8.3f}")
        result[name] = {"mrr": mrr, "h1": h1, "h3": h3, "h10": h10}

    dest = os.path.join(os.path.dirname(__file__), "..", "out", "completion.json")
    json.dump({"n_eval": n_eval, "metrics": result}, open(dest, "w"), indent=1)
    print("\nwrote out/completion.json")


if __name__ == "__main__":
    main()
