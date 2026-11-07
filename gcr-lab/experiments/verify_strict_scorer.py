"""Check that score_faithfulness.py's faithful_strict_hit matches s_metric_audit.py.

The paper tables come from score_faithfulness.py, but the corrected criterion
was first measured in s_metric_audit.py. This compares both per question on the
24 runs of X, under exact and official substring answer matching: 0 differences
under exact match, at most 2 questions under substring match (S used exact).

  PYTHONPATH=experiments .venv/bin/python experiments/verify_strict_scorer.py   (from gcr-lab/)
"""
import sys
sys.path[:0] = ['experiments', '../graph-constrained-reasoning/workflow']
import score_faithfulness as sf
from s_metric_audit import load, score
from x_cluster_tests import TABLES, src

gold_a, graphs, canon_fn = load()
gold = sf.load_gold('eval/gold_relations.jsonl.gz')
canon, shortcut = sf.load_criterion('eval/faithfulness_criterion.json')
official_match = sf.match

for ds, names in TABLES.items():
    print(f'\n{ds}  run  audit  exact-match scorer  diffs | official-match scorer  diffs  shortcut hits')
    for n in names:
        a = score(src(ds, n), gold_a, graphs, canon_fn)
        sf.match = lambda answer, gt: answer == gt
        e = {q['id']: q for q in sf.score_questions(src(ds, n), gold, canon, shortcut)[1]}
        sf.match = official_match
        o = {q['id']: q for q in sf.score_questions(src(ds, n), gold, canon, shortcut)[1]}
        assert set(a) == set(e) == set(o)
        rate = lambda d, k: sum(bool(q[k]) for q in d.values()) / len(d)
        de = sum(a[i]['strict'] != e[i]['faithful_strict_hit'] for i in a)
        do = sum(a[i]['strict'] != o[i]['faithful_strict_hit'] for i in a)
        sc = sum(a[i]['shortcut'] != e[i]['shortcut_hit'] for i in a)
        print(f"  {n:12s} {rate(a, 'strict'):.3f}  {rate(e, 'faithful_strict_hit'):.3f}  {de:3d} | "
              f"{rate(o, 'faithful_strict_hit'):.3f}  {do:3d}  shortcut diffs {sc}")
