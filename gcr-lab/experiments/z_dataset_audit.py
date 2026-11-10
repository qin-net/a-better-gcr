"""Experiment Z: how much of the error is the dataset, how much the model?

For the CWQ and WebQSP test sets: share of questions whose answer is not in the
question's own subgraph (no subgraph method can answer them), share reachable
in 2 hops, and labels where the gold answer is the question entity itself.
Then splits v2 C2's misses (seed 42) into "answer not in subgraph" and "answer
there, model missed", and breaks CWQ hit down by constraint type
(conjunction / composition from the CWQ annotation; superlative = ORDER BY,
numeric/time = a comparison filter in the SPARQL).

Hit here is a lower-cased substring match of any gold answer in the joined
answers, close to the official eval_hit.

  .venv/bin/python -I experiments/z_dataset_audit.py   (from gcr-lab/, ~1 min)
"""
import collections
import glob
import json
import re

import pyarrow.parquet as pq

R = 'experiments/cuda_results/'
CWQ = sorted(glob.glob('data/hf/cwq_eval/test-*.parquet'))
WEBQSP = ['data/hf/test.parquet']


def reach2(graph, starts):
    adj = collections.defaultdict(set)
    for h, _, t in graph:
        adj[h].add(t)
        adj[t].add(h)
    seen = frontier = set(starts)
    for _ in range(2):
        frontier = {v for u in frontier for v in adj[u]} - seen
        seen = seen | frontier
    return seen


def load(files):
    out = {}
    for f in files:
        for r in pq.read_table(f, columns=['id', 'q_entity', 'a_entity', 'graph']).to_pylist():
            g, a = r['graph'] or [], set(r['a_entity'] or [])
            nodes = {x for h, _, t in g for x in (h, t)}
            out[r['id']] = dict(gap=not a & nodes, in2=bool(a & reach2(g, r['q_entity'] or [])),
                                a_is_q=bool(a & set(r['q_entity'] or [])))
    return out


def hit(row):
    s = ' '.join(t.split('# Answer:', 1)[1].strip() for t in row['prediction'] if '# Answer:' in t).lower()
    return any(a.lower() in s for a in row['ground_truth'])


def kind(row):
    q = row['sparql']
    if re.search(r'ORDER BY', q, re.I):
        return 'superlative'
    if re.search(r'FILTER\s*\(\s*\?\w+\s*[<>]', q) or (
            re.search(r'xsd:(dateTime|float|integer)', q) and re.search(r'[<>]=?', q.split('WHERE', 1)[-1])):
        return 'numeric/time'
    return row['compositionality_type']


def main():
    data = {'cwq': load(CWQ), 'webqsp': load(WEBQSP)}
    for name, d in data.items():
        n = len(d)
        print(f'{name:7s} {n:5d} questions: answer not in subgraph {sum(v["gap"] for v in d.values()) / n:.1%}, '
              f'within 2 hops {sum(v["in2"] for v in d.values()) / n:.1%}, '
              f'gold answer is the question entity {sum(v["a_is_q"] for v in d.values())}')
    print('\nC2 seed 42 misses: answer not in subgraph / answer there but missed')
    for name, ds, path in (('cwq_500', 'cwq', 'v2/cwq_500/C2'), ('webqsp_1628', 'webqsp', 'v2/webqsp_1628/C2'),
                           ('cwq_500 official', 'cwq', 'ae_full/cwq_500/official')):
        rows = [json.loads(line) for line in open(R + path + '/predictions.jsonl', encoding='utf-8')]
        gap = [r for r in rows if data[ds][r['id']]['gap']]
        rest = [r for r in rows if not data[ds][r['id']]['gap']]
        print(f'  {name:17s} n={len(rows)}  hit {sum(map(hit, rows))}  missed: {len(gap) - sum(map(hit, gap))} '
              f'not in subgraph, {len(rest) - sum(map(hit, rest))} in subgraph '
              f'(hit {sum(map(hit, rest)) / len(rest):.1%} of those)')
    sparql = {r['ID']: r for r in pq.read_table('data/hf/cwq_sparql_test.parquet').to_pylist()}
    rows = {r['id']: r for r in map(json.loads, open(R + 'v2/cwq_500/C2/predictions.jsonl', encoding='utf-8'))}
    tab = collections.defaultdict(lambda: [0, 0, 0, 0])
    for i, v in data['cwq'].items():
        t = tab[kind(sparql[i])]
        t[0] += 1
        t[1] += v['gap']
        if i in rows:
            t[2] += 1
            t[3] += hit(rows[i])
    print(f'\n{"CWQ type":14s} {"test":>5s} {"not in subgraph":>16s} {"first 500":>10s} {"C2 hit":>7s}')
    for k, (n, g, n5, h) in sorted(tab.items(), key=lambda x: -x[1][0]):
        print(f'{k:14s} {n:5d} {g / n:16.1%} {n5:10d} {h / max(n5, 1):7.1%}')


if __name__ == '__main__':
    main()
