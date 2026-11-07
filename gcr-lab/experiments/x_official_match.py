"""The X table under the official scorer's matching.

x_cluster_tests.py uses s_metric_audit's exact answer match; the paper tables
come from score_faithfulness.py, which uses the official substring match. The
two disagree by at most 2 questions per run but move a borderline p value
(C2, CWQ single seed: 0.093 exact, 0.057 official), so the X table is printed
here with the scorer the paper uses.

Needs the scorer's dependencies, so run it through uv, not gcr-lab/.venv:

  uv run -q --no-project --python 3.11 --with scikit-learn --with pyarrow \\
      --with networkx --with datasets --with transformers \\
      python experiments/x_official_match.py        (from gcr-lab/, ~5 min)
"""
import sys

sys.path[:0] = ['experiments', '../graph-constrained-reasoning/workflow']

import score_faithfulness as sf
from x_cluster_tests import cluster, diff_test, fmt, src

GOLD = sf.load_gold('eval/gold_relations.jsonl.gz')
CANON, SHORTCUT = sf.load_criterion('eval/faithfulness_criterion.json')
C = ['C2', 'C2_s43', 'C2_s44']
A = ['A_multi', 'A_multi_s43', 'A_multi_s44']


def scores(dataset, name):
    path = src(dataset, name)
    return {q['id']: q for q in sf.score_questions(path, GOLD, CANON, SHORTCUT)[1]}


def pooled(dataset, other, base, keys=('hit', 'faithful_strict_hit')):
    """Mean per-question difference, seed CI and sign-flip p, seeds averaged within an arm."""
    o, b = [scores(dataset, n) for n in other], [scores(dataset, n) for n in base]
    ids = list(o[0])
    for key in keys:
        d = {q: (sum(bool(x[q][key]) for x in o) - sum(bool(x[q][key]) for x in b)) / len(other) for q in ids}
        m, lo, hi, p = diff_test(d, cluster(ids))
        print(f'{dataset:12s} {len(other)}v{len(base)} {key:20s} {m:+.3f}  [{lo:+.3f}, {hi:+.3f}]  p={fmt(p)}')


def main():
    pooled('cwq_500', C, A)
    pooled('cwq_500', ['C2'], ['A_multi'])
    pooled('webqsp_500', C, A)
    pooled('webqsp_1628', ['C2'], ['A_multi'])
    # is the full-run gain concentrated in questions the 500-subset does not cover?
    first = list(scores('webqsp_500', 'C2'))
    c2, a = scores('webqsp_1628', 'C2'), scores('webqsp_1628', 'A_multi')
    assert first == list(c2)[:500], 'webqsp_500 is not the first 500 of webqsp_1628'
    for label, part in (('first 500', first), ('other 1128', list(c2)[500:])):
        for key in ('hit', 'faithful_strict_hit'):
            d = {q: bool(c2[q][key]) - bool(a[q][key]) for q in part}
            m, lo, hi, p = diff_test(d, cluster(part))
            print(f'webqsp_1628s1 {label:10s} {key:20s} {m:+.3f}  [{lo:+.3f}, {hi:+.3f}]  p={fmt(p)}')


if __name__ == '__main__':
    main()
