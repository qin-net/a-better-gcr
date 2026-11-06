"""Re-score decoding runs with a corrected faithfulness check (FINDINGS.md section S).

score_faithfulness.py calls a candidate faithful when its relation names are a
subset of one SPARQL parse. Two flaws:
  1. Freebase stores each fact under two inverse relation names
     (film.director.film / film.film.directed_by). SPARQL names one, the RoG
     subgraph edge often carries the other, so a correct forward path is
     unfaithful and a reversed walk that spells the SPARQL name is faithful.
  2. A first step that walks a type relation backwards from a class node
     (Country -> common.topic.notable_types -> Guatemala) enumerates instances
     and guesses; it matches SPARQL because the parse has the type constraint.

Here inverse names are merged into classes (pairs seen between the same two
entities in both directions, >= 5 times and for >= 50% of each relation's
entity pairs, over all WebQSP + CWQ test subgraphs), and hits through flaw 2
are not counted. Hit here is exact answer match per candidate.

  .venv/bin/python -I experiments/s_metric_audit.py   (from gcr-lab/, ~3 min)
"""
import collections
import glob
import gzip
import json
from math import comb

import pyarrow.parquet as pq

R = 'experiments/cuda_results/'
TYPE_RELS = {'common.topic.notable_types', 'people.person.gender', 'type.object.type', 'common.topic.notable_for',
             'people.marriage.type_of_union', 'government.government_position_held.basic_title'}
TEST = {'cwq': sorted(glob.glob('data/hf/cwq_eval/test-*.parquet')), 'webqsp': ['data/hf/test.parquet']}


def load():
    gold = {r['id']: [set(p) for p in r['parses']]
            for r in map(json.loads, gzip.open('eval/gold_relations.jsonl.gz', 'rt'))}
    graphs, pair, rel_n = {}, collections.Counter(), collections.Counter()
    for files in TEST.values():
        for f in files:
            for row in pq.read_table(f, columns=['id', 'graph']).to_pylist():
                g = {tuple(t) for t in row['graph']}
                graphs[row['id']] = g
                between = collections.defaultdict(set)
                for h, r, t in g:
                    between[(h, t)].add(r)
                for (h, t), rels in between.items():
                    for r1 in rels:
                        rel_n[r1] += 1
                        for r2 in between.get((t, h), ()):
                            if r2 != r1:
                                pair[(r1, r2)] += 1
    parent = {}

    def find(r):
        while parent.get(r, r) != r:
            r = parent[r]
        return r
    for (r1, r2), n in sorted(pair.items()):
        if n >= 5 and n >= 0.5 * rel_n[r1] and n >= 0.5 * rel_n[r2]:
            a, b = sorted((find(r1), find(r2)))
            parent[b] = a
    return gold, graphs, find


def steps(path):
    s = path.split(' -> ')
    return [(s[i], s[i + 1], s[i + 2]) for i in range(0, len(s) - 2, 2)]


def score(run, gold, graphs, canon):
    out = {}
    for row in map(json.loads, open(run + '/predictions.jsonl', encoding='utf-8')):
        parses = gold.get(row['id'])
        if not parses:
            continue
        g, merged = graphs[row['id']], [{canon(r) for r in p} for p in parses]
        q = dict(hit=False, old=False, merged=False, strict=False, shortcut=False)
        for text, audit in zip(row['prediction'], row['path_audit']):
            answer = text.split('# Answer:', 1)[1].strip() if '# Answer:' in text else ''
            hit = answer in row['ground_truth']
            q['hit'] |= hit
            path = steps(audit.get('path', ''))
            if not path or not audit['valid'] or not hit:
                continue
            rels = {r for _, r, _ in path}
            u, r, v = path[0]
            shortcut = r in TYPE_RELS and (u, r, v) not in g and (v, r, u) in g
            ok = any({canon(x) for x in rels} <= p for p in merged)
            q['old'] |= any(rels <= p for p in parses)
            q['merged'] |= ok
            q['strict'] |= ok and not shortcut
            q['shortcut'] |= shortcut
        out[row['id']] = q
    return out


def mcnemar(base, other, key):
    gained = sum(other[q][key] and not base[q][key] for q in base)
    lost = sum(base[q][key] and not other[q][key] for q in base)
    n = gained + lost
    p = min(1, 2 * sum(comb(n, k) for k in range(min(gained, lost) + 1)) / 2 ** n) if n else 1
    return f'+{gained}/-{lost} p={p:.2g}'


def main():
    gold, graphs, canon = load()
    old = {'official': 'official', 'A_multi': 'A_multi', 'C': 'C'}
    tables = {
        'cwq_500': ['official', 'A_multi', 'C', 'C_wq', 'C_fwd', 'C2', 'C2_s43', 'C2_s44', 'D2', 'A_multi_s43', 'A_multi_s44'],
        'webqsp_500': ['official', 'A_multi', 'C', 'C_wq', 'C_fwd', 'C2', 'C2_s43', 'C2_s44', 'D2', 'A_multi_s43', 'A_multi_s44'],
        'webqsp_1628': ['A_multi', 'C2'],
    }
    for ds, names in tables.items():
        def src(n):
            if ds == 'webqsp_500' and n == 'official':
                return f'{R}ae_full/{ds}/official_failed'  # complete; only flagged by the WebQTest-521 empty trie
            return f'{R}ae_full/{ds}/{old[n]}' if ds != 'webqsp_1628' and n in old else f'{R}v2/{ds}/{n}'
        scores = {n: score(src(n), gold, graphs, canon) for n in names}
        print(f'\n{ds}  hit  f.hit(old)  f.hit(inverse merged)  f.hit(strict)  hit via type shortcut  '
              f'strict vs A_multi  strict vs official')
        for n, s in scores.items():
            m = {k: sum(q[k] for q in s.values()) / len(s) for k in ('hit', 'old', 'merged', 'strict', 'shortcut')}
            line = (f'  {n:12s} {m["hit"]:.3f}  {m["old"]:.3f}  {m["merged"]:.3f}  {m["strict"]:.3f}  {m["shortcut"]:.3f}')
            if n != 'A_multi':
                line += '  ' + mcnemar(scores['A_multi'], s, 'strict')
            if 'official' in scores and n != 'official':
                line += '  ' + mcnemar(scores['official'], s, 'strict')
            print(line)


if __name__ == '__main__':
    main()
