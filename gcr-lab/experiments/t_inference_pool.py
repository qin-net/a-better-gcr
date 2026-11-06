"""Experiment T: how much of the CWQ test gap can a training-only pool close?

19.3% of CWQ test questions have no answer entity in their own subgraph, and no
training change can help them. This measures the ceiling of inference-side
completion: merge the question's own subgraph with a pool built from training
subgraphs, then ask whether the answer becomes reachable. Answers and SPARQL are
used only to score, never to build the pool.

CWQ questions are rewrites of WebQSP questions (id prefix = seed), so a pool that
holds the "mother" subgraph of a test question may inflate the result. Each pool
triple carries source bits, and three pools are reported:
  strict  CWQ train + WebQSP train, minus any question sharing a seed with the
          CWQ test or validation set
  cwq     CWQ train only
  full    strict + the WebQSP mother questions of test questions

Reachability alone proved misleading in FINDINGS M, so the oracle column repeats
the search along SPARQL relations only, without type relations or class nodes as
start points (the N filter). It is an upper bound: SPARQL is unavailable at test.

  .venv/bin/python -I experiments/t_inference_pool.py   (from gcr-lab/)
"""
import collections
import glob
import gzip
import json
import os
import pickle
import time

import numpy as np
import pyarrow.compute as pc
import pyarrow.parquet as pq

CACHE = 'out/pool_cache.pkl'
CWQ_TRAIN = sorted(glob.glob('data/hf/cwq_full/train-*.parquet'))
WQ_TRAIN = ['data/hf/train.parquet']
CWQ_TEST = sorted(glob.glob('data/hf/cwq_eval/test-*.parquet'))
CWQ_VAL = sorted(glob.glob('data/hf/cwq_eval/validation-*.parquet'))
TYPE_RELS = {'common.topic.notable_types', 'people.person.gender', 'type.object.type', 'common.topic.notable_for',
             'people.marriage.type_of_union', 'government.government_position_held.basic_title'}
CWQ_BIT, WQ_BIT, WQ_MOTHER_BIT = 1, 2, 4
POOLS = {'cwq': CWQ_BIT, 'strict': CWQ_BIT | WQ_BIT, 'full': CWQ_BIT | WQ_BIT | WQ_MOTHER_BIT}


def seed(qid):
    return qid.split('_')[0]


def ids(files):
    return [i for f in files for i in pq.read_table(f, columns=['id']).column('id').to_pylist()]


class Vocab(dict):
    def encode(self, values):
        """Map a list of strings to ids, adding new ones."""
        return np.fromiter((self.setdefault(v, len(self)) for v in values), np.int32, len(values))


def file_triples(path, ent, rel, keep=None):
    """Encoded (h, r, t) of one parquet file, optionally only rows whose id passes keep."""
    table = pq.read_table(path, columns=['id', 'graph'])
    if keep is not None:
        table = table.filter(np.array([keep(i) for i in table.column('id').to_pylist()]))
    flat = pc.list_flatten(pc.list_flatten(table.column('graph').combine_chunks()))
    coded = flat.dictionary_encode()
    words = coded.dictionary.to_pylist()
    codes = coded.indices.to_numpy(zero_copy_only=False)
    h, r, t = codes[0::3], codes[1::3], codes[2::3]
    ent_map = np.full(len(words), -1, np.int32)
    rel_map = np.full(len(words), -1, np.int32)
    used = np.unique(np.concatenate([h, t]))
    ent_map[used] = ent.encode([words[i] for i in used])
    used = np.unique(r)
    rel_map[used] = rel.encode([words[i] for i in used])
    return ent_map[h], rel_map[r], ent_map[t]


def build_cache():
    test_seeds = {seed(i) for i in ids(CWQ_TEST + CWQ_VAL)}
    shared = {seed(i) for i in ids(CWQ_TRAIN)} & test_seeds
    print(f'test+val seeds {len(test_seeds)}, shared with CWQ train {len(shared)}', flush=True)
    ent, rel, parts = Vocab(), Vocab(), []
    jobs = [(f, CWQ_BIT, lambda i: seed(i) not in test_seeds) for f in CWQ_TRAIN]
    jobs += [(f, WQ_BIT, lambda i: i not in test_seeds) for f in WQ_TRAIN]
    jobs += [(f, WQ_MOTHER_BIT, lambda i: i in test_seeds) for f in WQ_TRAIN]
    for f, bit, keep in jobs:
        h, r, t = file_triples(f, ent, rel, keep)
        parts.append((h, r, t, np.full(len(h), bit, np.int8)))
        print(f'  {os.path.basename(f)} bit {bit}: {len(h):,} triples, {len(ent):,} entities', flush=True)
    h, r, t, bits = (np.concatenate(c) for c in zip(*parts))
    key = (h.astype(np.int64) * len(rel) + r) * len(ent) + t
    order = np.argsort(key, kind='stable')
    key, h, r, t, bits = key[order], h[order], r[order], t[order], bits[order]
    start = np.flatnonzero(np.r_[True, key[1:] != key[:-1]])
    bits = np.bitwise_or.reduceat(bits, start)
    h, r, t = h[start], r[start], t[start]
    print(f'unique triples {len(h):,}', flush=True)
    with open(CACHE, 'wb') as f:
        pickle.dump({'ent': dict(ent), 'rel': dict(rel), 'h': h, 'r': r, 't': t, 'bits': bits}, f, protocol=4)


class Graph:
    """Undirected CSR over a triple list; each neighbour keeps its relation id."""

    def __init__(self, h, r, t, n):
        src, dst, rels = np.r_[h, t], np.r_[t, h], np.r_[r, r]
        order = np.argsort(src, kind='stable')
        self.dst, self.rel = dst[order], rels[order]
        self.ptr = np.zeros(n + 1, np.int64)
        np.cumsum(np.bincount(src, minlength=n), out=self.ptr[1:])

    def step(self, nodes, allowed=None):
        """Neighbours of nodes, optionally through allowed relation ids only."""
        lo, hi = self.ptr[nodes], self.ptr[nodes + 1]
        size = hi - lo
        total = int(size.sum())
        if not total:
            return np.empty(0, np.int32)
        idx = np.repeat(lo - np.r_[0, np.cumsum(size)[:-1]], size) + np.arange(total)
        if allowed is not None:
            idx = idx[np.isin(self.rel[idx], allowed)]
        return self.dst[idx]


def distance(graphs, starts, goals, depth, allowed=None):
    """Hops from starts to any goal across the union of graphs, or None."""
    seen = set(starts)
    frontier = np.array(sorted(seen), np.int32)
    goals = set(goals)
    if seen & goals:
        return 0
    for d in range(1, depth + 1):
        nxt = np.unique(np.concatenate([g.step(frontier, allowed) for g in graphs]))
        fresh = [v for v in nxt.tolist() if v not in seen]
        if goals & set(fresh):
            return d
        if not fresh:
            return None
        seen.update(fresh)
        frontier = np.array(fresh, np.int32)
    return None


class Local:
    """A small per-question graph with the same step() as Graph, keyed by dicts."""

    def __init__(self, triples):
        self.adj = collections.defaultdict(list)
        for a, b, c in triples:
            self.adj[a].append((c, b))
            self.adj[c].append((a, b))

    def step(self, nodes, allowed=None):
        ok = None if allowed is None else set(allowed.tolist())
        return np.array([v for u in nodes.tolist() for v, r in self.adj.get(u, ())
                         if ok is None or r in ok], np.int32)


class Padded:
    """Pool Graph that tolerates ids added after it was built."""

    def __init__(self, graph):
        self.graph, self.n = graph, len(graph.ptr) - 1

    def step(self, nodes, allowed=None):
        return self.graph.step(nodes[nodes < self.n], allowed)


def main():
    t0 = time.time()
    if not os.path.exists(CACHE):
        build_cache()
    with open(CACHE, 'rb') as f:
        c = pickle.load(f)
    ent, rel = c['ent'], c['rel']
    h, r, t, bits = c['h'], c['r'], c['t'], c['bits']
    n = len(ent)
    print(f'{n:,} entities, {len(h):,} triples ({time.time() - t0:.0f}s)', flush=True)
    for name, mask in POOLS.items():
        print(f'  pool {name}: {int((bits & mask != 0).sum()):,} triples', flush=True)

    gold = {x['id']: x['parses'] for x in map(json.loads, gzip.open('eval/gold_relations.jsonl.gz', 'rt'))}
    type_ids = np.array([rel[x] for x in TYPE_RELS if x in rel], np.int32)
    class_nodes = set(t[np.isin(r, type_ids)].tolist())
    pools = {name: Padded(Graph(h[keep], r[keep], t[keep], n))
             for name, keep in ((k, bits & m != 0) for k, m in POOLS.items())}
    print(f'pools indexed ({time.time() - t0:.0f}s)', flush=True)

    test = [row for f in CWQ_TEST for row in pq.read_table(
        f, columns=['id', 'q_entity', 'a_entity', 'graph']).to_pylist()]
    wq_train = set(ids(WQ_TRAIN))
    table = collections.Counter()
    records = []
    for i, row in enumerate(test):
        q, a = row['q_entity'] or [], row['a_entity'] or []
        graph = row['graph'] or []
        own_nodes = {x for tr in graph for x in (tr[0], tr[2])}
        if not q or not a:
            table['no_q_or_a'] += 1
            continue
        table['total'] += 1
        if own_nodes & set(a):
            continue
        table['gap'] += 1
        extra = {}  # names outside the pool get ids past it, for this question only

        def code(name):
            return ent[name] if name in ent else extra.setdefault(name, n + len(extra))

        qs, gs = [code(x) for x in q], [code(x) for x in a]
        local = Local([(code(x), rel.get(y, -1), code(z)) for x, y, z in graph])
        parses = [np.array([rel[x] for x in set(p) - TYPE_RELS if x in rel], np.int32) for p in gold.get(row['id'], [])]
        starts = [x for x in qs if x not in class_nodes] or []
        rec = {'id': row['id'], 'mother_in_wq_train': seed(row['id']) in wq_train}
        table['gap_mother'] += rec['mother_in_wq_train']
        for name, pool in pools.items():
            graphs = [pool, local]
            rec[f'{name}_in_pool'] = any(g < n and pool.graph.ptr[g + 1] > pool.graph.ptr[g] for g in gs)
            table[f'{name}_in_pool'] += rec[f'{name}_in_pool']
            d = distance(graphs, qs, gs, 4) if rec[f'{name}_in_pool'] else None
            rec[f'{name}_d'] = d
            o = None
            if rec[f'{name}_in_pool'] and starts and parses:
                hops = [x for x in (distance(graphs, starts, gs, 4, p) for p in parses if len(p)) if x is not None]
                o = min(hops) if hops else None
            rec[f'{name}_oracle_d'] = o
            for k in (2, 3, 4):
                table[f'{name}_reach{k}'] += d is not None and d <= k
                table[f'{name}_oracle{k}'] += o is not None and o <= k
        records.append(rec)
        if table['gap'] % 100 == 0:
            print(f"  {table['gap']} gap questions ({time.time() - t0:.0f}s)", flush=True)

    print(json.dumps(table, indent=1))
    with open('out/inference_pool.json', 'w') as f:
        json.dump({'table': table, 'records': records}, f)
    gap = table['gap']
    print(f"\nCWQ test {table['total']}, answer outside own subgraph {gap} ({gap / table['total']:.1%}), "
          f"mother in WebQSP train {table['gap_mother']}")
    print('pool    in pool  reach<=2  <=3  <=4   oracle<=2  <=3  <=4')
    for name in POOLS:
        print(f"{name:7} {table[name + '_in_pool'] / gap:6.1%}  " +
              '  '.join(f"{table[f'{name}_reach{k}'] / gap:6.1%}" for k in (2, 3, 4)) + '    ' +
              '  '.join(f"{table[f'{name}_oracle{k}'] / gap:6.1%}" for k in (2, 3, 4)))
    print(f'done ({time.time() - t0:.0f}s)')


if __name__ == '__main__':
    main()
