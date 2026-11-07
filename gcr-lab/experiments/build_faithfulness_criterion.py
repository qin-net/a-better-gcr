"""Build the fixed artifacts for the corrected faithfulness criterion (FINDINGS S).

score_faithfulness.py used to call a candidate faithful when its relation names
are a subset of one SPARQL parse. S found two flaws and this freezes the fix:

  1. Freebase stores each fact under two inverse names
     (film.director.film / film.film.directed_by). The subgraph edge carries
     one, SPARQL names the other. Merge inverse names into classes: r1 and r2
     are merged when they connect the same two entities in opposite directions,
     >= 5 times, and each for >= 50% of that relation's entity pairs, over all
     WebQSP + CWQ test subgraphs.
  2. Walking a type relation backwards from a class node
     (Country -> common.topic.notable_types -> Guatemala) enumerates instances
     and guesses; SPARQL lists the type as a constraint so it scores as
     faithful. Flag those first steps and do not count hits through them.

Output (gcr-lab/eval/faithfulness_criterion.json):
  inverse_classes  relation -> class id           (merged names)
  type_relations   relations subject to flaw 2
  shortcut         question id -> [[h, r, t], ...]  first steps to reject

Computed once from the test subgraphs, so scoring a run needs no parquet and
every table in the paper shares one definition.

  .venv/bin/python -I experiments/build_faithfulness_criterion.py   (from gcr-lab/, ~1 min)
"""
import collections
import glob
import gzip
import json
from pathlib import Path

import pyarrow.parquet as pq

# same list as s_metric_audit.py
TYPE_RELS = {'common.topic.notable_types', 'people.person.gender', 'type.object.type', 'common.topic.notable_for',
             'people.marriage.type_of_union', 'government.government_position_held.basic_title'}
TEST = {'cwq': sorted(glob.glob('data/hf/cwq_eval/test-*.parquet')), 'webqsp': ['data/hf/test.parquet']}
OUT = Path('eval/faithfulness_criterion.json')


def main():
    gold_ids = {r['id'] for r in map(json.loads, gzip.open('eval/gold_relations.jsonl.gz', 'rt'))}
    pair, rel_n = collections.Counter(), collections.Counter()
    shortcut = {}
    n_graph = 0
    for files in TEST.values():
        for f in files:
            for row in pq.read_table(f, columns=['id', 'graph', 'q_entity']).to_pylist():
                g = {tuple(t) for t in row['graph']}
                between = collections.defaultdict(set)
                for h, r, t in g:
                    between[(h, t)].add(r)
                for (h, t), rels in between.items():
                    for r1 in rels:
                        rel_n[r1] += 1
                        for r2 in between.get((t, h), ()):
                            if r2 != r1:
                                pair[(r1, r2)] += 1
                if row['id'] in gold_ids:
                    n_graph += 1
                    # the shortcut walks a type edge against its direction, so
                    # (t, r, h) is the step and it must not also be an edge.
                    # Paths start at a question entity, so only those can be first steps.
                    starts = set(row['q_entity'])
                    flagged = [[t, r, h] for h, r, t in sorted(g)
                               if r in TYPE_RELS and t in starts and (t, r, h) not in g]
                    if flagged:
                        shortcut[row['id']] = flagged

    parent = {}

    def find(r):
        while parent.get(r, r) != r:
            r = parent[r]
        return r

    for (r1, r2), n in sorted(pair.items()):
        if n >= 5 and n >= 0.5 * rel_n[r1] and n >= 0.5 * rel_n[r2]:
            a, b = sorted((find(r1), find(r2)))
            parent[b] = a
    classes = {r: find(r) for r in rel_n}
    merged = collections.Counter(classes.values())
    print(f'{len(classes)} relations -> {len(merged)} classes, largest {merged.most_common(3)}')
    print(f'type-shortcut first steps flagged in {len(shortcut)}/{n_graph} scored questions')

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({'inverse_classes': classes,
                               'type_relations': sorted(TYPE_RELS),
                               'shortcut': shortcut}, sort_keys=True), encoding='utf-8')
    print(f'wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)')


if __name__ == '__main__':
    main()
