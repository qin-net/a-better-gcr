"""Experiment V: are predicted-relation completions real, and does the answer rank high?

U reached the answer for many CWQ test gap questions using predicted relations,
and with K=100 even beat the SPARQL search, which should be an upper bound. That
is either hub shortcuts or inverse relation names the SPARQL search cannot follow.
This re-runs the search with path scores and reports, on gap questions:

  recall@N   the answer is among the top N reached nodes, by path score
  faithful   the best path to the answer uses only relations of one SPARQL parse,
             with inverse names merged (s_metric_audit). Only that single path is
             checked, so this is a lower bound.

Path score is the sum or the mean of relation similarities along a path. The
choice is made on validation and then reported on test.

  PYTHONPATH=experiments .venv/bin/python experiments/v_rank_completion.py
"""
import collections
import gzip
import json
import pickle
import random
import re
import time

import numpy as np

from s_metric_audit import load as load_canon
from t_inference_pool import CACHE, CWQ_TEST, CWQ_VAL, POOLS, TYPE_RELS, Graph, Padded
from u_detect_complete import RelationModel, load

KS = (20, 50, 100)
TOPS = (10, 100, 1000)
MID = re.compile(r'^[mg]\.[0-9a-z_]+$')


def edges(q, pool, nodes, score):
    """(src, dst, rel) of pool and own edges leaving nodes through relations with a score."""
    g = pool.graph
    known = nodes[nodes < pool.n]
    lo, hi = g.ptr[known], g.ptr[known + 1]
    size = hi - lo
    out = []
    if size.sum():
        idx = np.repeat(lo - np.r_[0, np.cumsum(size)[:-1]], size) + np.arange(int(size.sum()))
        src = np.repeat(known, size)
        keep = score[g.rel[idx]] > -1
        out.extend(zip(src[keep].tolist(), g.dst[idx][keep].tolist(), g.rel[idx][keep].tolist()))
    for u in nodes.tolist():
        out.extend((u, v, r) for v, r in q.local.adj.get(u, ()) if r >= 0 and score[r] > -1)
    return out


def search(q, pool, score, depth=3):
    """Node -> (path score sum, hops, parent, relation), best sum per node at its first depth."""
    best = {s: (0.0, 0, None, None) for s in q.starts}
    frontier = np.array(sorted(best), np.int32)
    for d in range(1, depth + 1):
        layer = {}
        for u, v, r in edges(q, pool, frontier, score):
            if v in best:
                continue
            s = best[u][0] + float(score[r])
            if v not in layer or s > layer[v][0]:
                layer[v] = (s, d, u, r)
        if not layer or len(best) > 300000:
            best.update(layer)
            break
        best.update(layer)
        frontier = np.array(sorted(layer), np.int32)
    return best


def path_rels(best, node):
    rels = []
    while best[node][2] is not None:
        rels.append(best[node][3])
        node = best[node][2]
    return rels[::-1]


def evaluate(gap, pool, model, n_rel, mid, rel_name, gold, canon, k):
    stats = {m: collections.Counter() for m in ('sum', 'mean')}
    cases = []
    for q in gap:
        ranked, scores = model.rank(q.text, q.names)
        score = np.full(n_rel, -2.0)
        score[ranked[:k]] = scores[:k]
        best = search(q, pool, score)
        found = [a for a in q.a if a in best and best[a][1] > 0]
        if not found:
            continue
        cands = [v for v, b in best.items() if b[1] > 0 and not (v < len(mid) and mid[v])]
        sums = np.array([best[v][0] for v in cands])
        hops = np.array([best[v][1] for v in cands])
        for m, value in (('sum', sums), ('mean', sums / hops)):
            order = {v: i for i, v in enumerate(np.array(cands)[np.argsort(-value, kind='stable')].tolist())}
            rank = min((order[a] for a in found if a in order), default=None)
            stats[m]['hit'] += rank is not None
            for n in TOPS:
                stats[m][n] += rank is not None and rank < n
        a = found[0]
        rels = [canon(rel_name[r]) for r in path_rels(best, a)]
        ok = any(set(rels) <= {canon(x) for x in p} for p in gold.get(q.id, []))
        stats['sum']['faithful'] += ok
        cases.append((q, [rel_name[r] for r in path_rels(best, a)], ok))
    return stats, cases


def main():
    t0 = time.time()
    with open(CACHE, 'rb') as f:
        c = pickle.load(f)
    ent, rel, h, r, t, bits = c['ent'], c['rel'], c['h'], c['r'], c['t'], c['bits']
    type_ids = np.array([rel[x] for x in TYPE_RELS if x in rel], np.int32)
    class_nodes = set(t[np.isin(r, type_ids)].tolist())
    keep = bits & POOLS['strict'] != 0
    pool = Padded(Graph(h[keep], r[keep], t[keep], len(ent)))
    mid = np.zeros(len(ent), bool)
    mid[[i for name, i in ent.items() if MID.match(name)]] = True
    rel_name = {i: name for name, i in rel.items()}
    model = RelationModel(rel)
    gold, _, canon = load_canon()
    print(f'loaded ({time.time() - t0:.0f}s)', flush=True)
    val = [q for q in load(CWQ_VAL, ent, rel, class_nodes) if q.gap]
    test = [q for q in load(CWQ_TEST, ent, rel, class_nodes) if q.gap]
    oracle = {x['id']: x['strict_oracle_d'] for x in json.load(open('out/inference_pool.json'))['records']}
    results = {}
    for name, gap in (('validation', val), ('test', test)):
        print(f'\n== {name}: {len(gap)} gap questions ==', flush=True)
        for k in KS:
            stats, cases = evaluate(gap, pool, model, len(rel), mid, rel_name, gold, canon, k)
            results[f'{name}@{k}'] = {m: dict(s) for m, s in stats.items()}
            n = len(gap)
            for m, s in stats.items():
                print(f"K={k:<3} {m:4} reached {s['hit'] / n:6.1%}  " +
                      '  '.join(f'recall@{x} {s[x] / n:6.1%}' for x in TOPS), flush=True)
            hit = stats['sum']['hit']
            print(f"      best path faithful {stats['sum']['faithful'] / max(hit, 1):6.1%} of hits, "
                  f"{stats['sum']['faithful'] / n:6.1%} of gap", flush=True)
            if name == 'test':
                extra = [x for x in cases if (oracle.get(x[0].id) or 9) > 3]
                print(f'      hits the SPARQL search missed: {len(extra)}, '
                      f'of which faithful with inverse names merged: {sum(x[2] for x in extra)}', flush=True)
                if k in (20, 100):
                    random.seed(k)
                    for q, rels, ok in random.sample([x for x in extra if not x[2]], 6):
                        print(f"      Q: {q.text[:95]}\n         {' / '.join(x.split('.', 1)[1] for x in rels)}", flush=True)
    with open('out/rank_completion.json', 'w') as f:
        json.dump(results, f, default=str)
    print(f'done ({time.time() - t0:.0f}s)')


if __name__ == '__main__':
    main()
