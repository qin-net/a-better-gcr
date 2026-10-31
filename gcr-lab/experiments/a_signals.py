"""Experiment A: how much structural signal does the RoG graph carry?

Three measurements, all computable from (h, r, t) alone:
  A1 functional-ness   -- share of (h, r) pairs with a unique tail
  A2 inverse pairs     -- relation r pairs whose mirror r' connects the same entities
  A3 rule usefulness   -- given (h, r1, x) and (x, r2, t), how often does
                          (h, r2, t) hold?  (a 2-hop meta-path rule)
"""

import argparse
import collections
import json
import sys

sys.path.insert(0, __import__("os").path.dirname(__file__))
from rog_io import iter_rows  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("train")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    hr_tails = collections.defaultdict(set)
    out_edges = collections.defaultdict(set)
    rel_counts = collections.Counter()
    n_rows = 0
    for row in iter_rows(args.train):
        for h, r, t in row["graph"]:
            hr_tails[(h, r)].add(t)
            out_edges[h].add((r, t))
            rel_counts[r] += 1
        n_rows += 1
        if args.limit and n_rows >= args.limit:
            break

    print(f"rows={n_rows} distinct_edges={sum(len(v) for v in out_edges.values())} "
          f"(h,r) pairs={len(hr_tails)} relations={len(rel_counts)} "
          f"entities={len(out_edges)}")

    # A1: functional-ness. Ignore (h,r) seen only once globally -- their
    # uniqueness may just mean sparse coverage, but report both views.
    by_rel = collections.defaultdict(lambda: [0, 0, 0])  # single,total,tails
    for (h, r), tails in hr_tails.items():
        v = by_rel[r]
        v[0] += len(tails) == 1
        v[1] += 1
        v[2] += len(tails)
    print("\nA1 functional-ness (top relations by frequency)")
    print(f"{'relation':<46}{'(h,r)':>7}{'single-tail':>13}{'avg tails':>11}")
    for r, c in rel_counts.most_common(15):
        single, total, tails = by_rel[r]
        print(f"{r:<46}{total:>7}{single / total:>13.2f}{tails / total:>11.2f}")

    # A2: inverse relation pairs. r and r' are inverses if a large share of
    # (h,r,t) has (t,r',h) present.
    support = collections.Counter()
    for (h, r), tails in hr_tails.items():
        for t in tails:
            support[r] += 1
    best = {}
    for (h, r), tails in hr_tails.items():
        for t in tails:
            for r2, t2 in out_edges.get(t, ()):
                if t2 == h and r2 != r:
                    best[(r, r2)] = best.get((r, r2), 0) + 1
    pairs = []
    for (r, r2), n in best.items():
        if r >= r2:
            continue
        share = n / max(1, min(support[r], support[r2]))
        if share >= 0.3 and n >= 20:
            pairs.append((share, n, r, r2))
    pairs.sort(reverse=True)
    print("\nA2 inverse relation pairs (share >= 0.3, support >= 20)")
    for share, n, r, r2 in pairs[:12]:
        print(f"  {share:.2f}  n={n:<6} {r}  <->  {r2}")

    # A3: 2-hop meta-path rule precision. For each (h, r1, x), look at what
    # else h has; measure how often the pair (h, r2) and (x, r2) share tails.
    # We sample from high-degree entities to keep this linear-ish.
    print("\nA3 meta-path: P((h,r2,t) | (h,r1,x), (x,r2,t))")
    rel2_pairs = collections.Counter()
    rel2_hits = collections.Counter()
    for h, edges in out_edges.items():
        if len(edges) > 24:
            continue
        for r1, x in edges:
            for r2, t in out_edges.get(x, ()):
                if r2 == r1 or t == h:
                    continue
                rel2_pairs[(r1, r2)] += 1
                if (r2, t) in edges:
                    rel2_hits[(r1, r2)] += 1
    total_c = sum(rel2_pairs.values())
    total_h = sum(rel2_hits.values())
    print(f"  candidate meta-paths: {total_c}, confirmed: {total_h} "
          f"({total_h / max(1, total_c):.3f})")
    robust = []
    for (r1, r2), n in rel2_pairs.items():
        hit = rel2_hits[(r1, r2)]
        if n >= 200 and hit >= 30:
            robust.append((hit / n, n, r1, r2))
    robust.sort(reverse=True)
    print("  most precise pairs (n >= 200):")
    for p, n, r1, r2 in robust[:12]:
        print(f"  {p:.3f}  n={n:<8} {r1}  ->  {r2}")

    json.dump({
        "rows": n_rows,
        "relations": len(rel_counts),
        "entities": len(out_edges),
        "functional": {r: by_rel[r][0] / by_rel[r][1]
                       for r, _ in rel_counts.most_common(50)},
        "inverse_pairs": [[round(s, 3), n, r, r2] for s, n, r, r2 in pairs],
        "meta_path_precision": total_h / max(1, total_c),
        "meta_path_candidates": total_c,
    }, open(__import__("os").path.join(
        __import__("os").path.dirname(__file__), "..", "out", "signals.json"), "w"),
        indent=1)
    print("\nwrote out/signals.json")


if __name__ == "__main__":
    main()
