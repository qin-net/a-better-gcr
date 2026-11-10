"""Experiment Y: score the GPU run of inference-side completion (x_cuda_completion.py).

The C2 adapter decoded CWQ test (first 500) three ways: local subgraph only,
always adding the ~100 completion paths of U/V to the trie, and adding them
only when the gap detector fires. comparison.json has hit only; this adds
faithful_strict_hit, the seed-question test of each mode against local, how
many decoded candidates actually use an added edge, and the gate's recall on
questions whose answer is not in the subgraph.

  uv run -q --no-project --python 3.11 --with scikit-learn --with pyarrow \\
      --with networkx --with datasets --with transformers \\
      python experiments/y_completion_eval.py        (from gcr-lab/, ~1 min)
"""
import glob
import json
import sys

import pyarrow.parquet as pq

sys.path[:0] = ['../graph-constrained-reasoning/workflow']
import score_faithfulness as sf  # noqa: E402

RUN = 'experiments/cuda_results/cwq_completion_500/'
MODES = ('local', 'always', 'gated')


def subgraphs(ids):
    out = {}
    for f in sorted(glob.glob('data/hf/cwq_eval/test-*.parquet')):
        for r in pq.read_table(f, columns=['id', 'a_entity', 'graph']).to_pylist():
            if r['id'] in ids:
                g = r['graph'] or []
                edges = {(h, rel, t) for h, rel, t in g}
                nodes = {x for h, _, t in g for x in (h, t)}
                out[r['id']] = dict(gap=not set(r['a_entity'] or []) & nodes,
                                    edges=edges | {(t, rel, h) for h, rel, t in edges})
    return out


def main():
    gold = sf.load_gold('eval/gold_relations.jsonl.gz')
    canon, shortcut = sf.load_criterion('eval/faithfulness_criterion.json')
    rows = {m: {r['id']: r for r in map(json.loads, open(RUN + m + '/predictions.jsonl', encoding='utf-8'))}
            for m in MODES}
    scored = {m: {q['id']: q for q in sf.score_questions(RUN + m, gold, canon, shortcut)[1]} for m in MODES}
    info = subgraphs(set(rows['local']))
    gap = {q for q, v in info.items() if v['gap']}
    print(f'{len(info)} questions, {len(gap)} with the answer outside the subgraph')
    for m in MODES:
        s = scored[m]
        line = f'{m:7s} hit {sum(q["hit"] for q in s.values()) / len(s):.3f}  ' \
               f'strict {sum(q["faithful_strict_hit"] for q in s.values()) / len(s):.3f}'
        if m != 'local':
            added = {q for q, r in rows[m].items() if r.get('completion_paths', 0)}
            used = total = 0
            for q, r in rows[m].items():
                for a in r['path_audit']:
                    total += 1
                    used += any(step not in info[q]['edges'] for step in sf.path_steps(a.get('path', '')))
            line += f'  paths added to {len(added)} questions ({len(added & gap)} of the gap ones), ' \
                    f'candidates using an added edge {used}/{total}'
            for key in ('hit', 'faithful_strict_hit'):
                d = {q: bool(s[q][key]) - bool(scored['local'][q][key]) for q in s}
                m_, lo, hi, p = sf.seed_test(d)
                line += f'\n        {key:20s} +{sum(v > 0 for v in d.values())}/-{sum(v < 0 for v in d.values())}' \
                        f'  seed p={p:.2g}  gained in gap questions {sum(d[q] > 0 for q in gap)}'
        print(line)


if __name__ == '__main__':
    main()
