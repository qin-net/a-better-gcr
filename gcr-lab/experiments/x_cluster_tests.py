"""Experiment X: redo the Q/S paired tests with seed-cluster resampling.

W showed that CWQ questions are rewrites of ~344 WebQSP seeds, so questions
sharing a seed are correlated and the per-question McNemar test used in Q and S
is too optimistic. S's headline (C2 vs A_multi: +2.5 points on CWQ) sits right
where that matters -- p = 0.09-0.13 per question, and CWQ only has 344
independent units.

Recomputes, for every run, the paired difference against a baseline on
  hit / f.hit(old) / f.hit(strict)   (s_metric_audit's corrected criterion)
with three tests side by side:
  McNemar   per question, exact -- what Q and S reported (too narrow)
  seed boot 2,000 resamples of whole seeds, percentile CI on the difference
  seed sign-flip  permutation over seeds of the per-seed net (gained - lost)

WebQSP ids carry no rewrite family (1,628 ids, 1,628 seeds), so its clusters
are singletons and the three tests agree there -- that is the control.

Also pools the three C2 seeds against the three A_multi seeds, and splits the
single-seed WebQSP full run into its first 500 and the other 1,128 questions.
Answers match exactly here, as in S; the paper tables use score_faithfulness.py's
substring match, which moves a run by at most 2 questions.

  PYTHONPATH=experiments .venv/bin/python experiments/x_cluster_tests.py   (from gcr-lab/)
"""
import collections
import random

from s_metric_audit import R, load, mcnemar, score

TABLES = {
    'cwq_500': ['official', 'A_multi', 'C', 'C_wq', 'C_fwd', 'C2', 'C2_s43', 'C2_s44', 'D2',
                'A_multi_s43', 'A_multi_s44'],
    'webqsp_500': ['official', 'A_multi', 'C', 'C_wq', 'C_fwd', 'C2', 'C2_s43', 'C2_s44', 'D2',
                   'A_multi_s43', 'A_multi_s44'],
    'webqsp_1628': ['A_multi', 'C2'],
}
KEYS = ('hit', 'old', 'strict')
BASE = {'cwq_500': 'A_multi', 'webqsp_500': 'A_multi', 'webqsp_1628': 'A_multi'}


def src(ds, name):
    if ds == 'webqsp_500' and name == 'official':
        return f'{R}ae_full/{ds}/official_failed'
    if ds == 'webqsp_1628' or name not in ('official', 'A_multi', 'C'):
        return f'{R}v2/{ds}/{name}'
    return f'{R}ae_full/{ds}/{name}'


def cluster(ids):
    """Map seed -> question ids."""
    g = collections.defaultdict(list)
    for q in ids:
        g[q.split('_')[0]].append(q)
    return g


def seed_boot(base, other, key, groups, n=2000, level=0.95):
    """Percentile CI on mean(other) - mean(base), resampling whole seeds."""
    seeds = sorted(groups)
    rng = random.Random(0)
    vals = []
    for _ in range(n):
        pick = [seeds[rng.randrange(len(seeds))] for _ in range(len(seeds))]
        qs = [q for s in pick for q in groups[s]]
        b = sum(base[q][key] for q in qs) / len(qs)
        o = sum(other[q][key] for q in qs) / len(qs)
        vals.append(o - b)
    vals.sort()
    lo = vals[int((1 - level) / 2 * n)]
    hi = vals[int((1 + level) / 2 * n) - 1]
    return lo, hi


def seed_perm(base, other, key, groups, n=10000):
    """Sign-flip permutation over seeds on the per-seed net gain.

    Under the null the seed's paired (other - base) contribution is symmetric
    about zero, so flipping each seed's sign at random gives the null
    distribution of the total. Two-sided p.
    """
    nets = []
    for s, qs in groups.items():
        g = sum(other[q][key] and not base[q][key] for q in qs)
        l = sum(base[q][key] and not other[q][key] for q in qs)
        nets.append(g - l)
    obs = abs(sum(nets))
    rng = random.Random(0)
    hits = 0
    for _ in range(n):
        if abs(sum(x if rng.random() < 0.5 else -x for x in nets)) >= obs:
            hits += 1
    return (hits + 1) / (n + 1)


def diff_test(diffs, groups, n=2000, flips=10000):
    """Seed CI and sign-flip p for per-question differences (need not be 0/1)."""
    totals = [(sum(diffs[q] for q in qs), len(qs)) for qs in groups.values()]
    rng = random.Random(0)
    vals = []
    for _ in range(n):
        pick = [totals[rng.randrange(len(totals))] for _ in totals]
        vals.append(sum(t for t, _ in pick) / sum(m for _, m in pick))
    vals.sort()
    obs = abs(sum(t for t, _ in totals))
    hits = sum(abs(sum(t if rng.random() < 0.5 else -t for t, _ in totals)) >= obs - 1e-9 for _ in range(flips))
    return sum(diffs.values()) / len(diffs), vals[int(0.025 * n)], vals[int(0.975 * n) - 1], (hits + 1) / (flips + 1)


def fmt(p):
    return f'{p:.2g}' if p >= 1e-4 else f'{p:.0e}'


def main():
    gold, graphs, canon = load()
    for ds, names in TABLES.items():
        scores = {n: score(src(ds, n), gold, graphs, canon) for n in names}
        ids = list(scores[names[0]])
        assert all(set(s) == set(ids) for s in scores.values()), f'{ds}: id mismatch'
        groups = cluster(ids)
        base = BASE[ds]
        print(f'\n=== {ds}  n={len(ids)}  seeds={len(groups)}  base={base}')
        for key in KEYS:
            print(f'  [{key}]  run          rate    McNemar(per q)        seed CI              seed perm p')
            for n in names:
                if n == base:
                    continue
                rate = sum(scores[n][q][key] for q in ids) / len(ids)
                lo, hi = seed_boot(scores[base], scores[n], key, groups)
                p = seed_perm(scores[base], scores[n], key, groups)
                print(f'          {n:12s} {rate:.3f}  {mcnemar(scores[base], scores[n], key):20s} '
                      f'[{lo:+.3f}, {hi:+.3f}]  {fmt(p)}')
        if 'official' in scores:
            print(f'  [strict vs official]')
            for n in names:
                if n == 'official':
                    continue
                lo, hi = seed_boot(scores['official'], scores[n], 'strict', groups)
                p = seed_perm(scores['official'], scores[n], 'strict', groups)
                print(f'          {n:12s} {sum(scores[n][q]["strict"] for q in ids) / len(ids):.3f}  '
                      f'{mcnemar(scores["official"], scores[n], "strict"):20s} '
                      f'[{lo:+.3f}, {hi:+.3f}]  {fmt(p)}')

        if {'C2_s43', 'A_multi_s43'} <= set(names):
            print('  [3 seeds pooled: C2 vs A_multi]     diff   seed CI              seed perm p')
            for key in KEYS:
                c = [scores[n] for n in ('C2', 'C2_s43', 'C2_s44')]
                a = [scores[n] for n in ('A_multi', 'A_multi_s43', 'A_multi_s44')]
                d = {q: (sum(x[q][key] for x in c) - sum(x[q][key] for x in a)) / 3 for q in ids}
                m, lo, hi, p = diff_test(d, groups)
                print(f'          {key:26s} {m:+.3f}  [{lo:+.3f}, {hi:+.3f}]  {fmt(p)}')
        if ds == 'webqsp_1628':
            first = list(score(src('webqsp_500', 'C2'), gold, graphs, canon))
            assert first == ids[:500], 'webqsp_500 is not the first 500 of webqsp_1628'
            print('  [seed 42 only, C2 vs A_multi]       diff   seed CI              seed perm p')
            for label, part in (('first 500', ids[:500]), ('other 1128', ids[500:])):
                for key in KEYS:
                    d = {q: scores['C2'][q][key] - scores['A_multi'][q][key] for q in part}
                    m, lo, hi, p = diff_test(d, cluster(part))
                    print(f'          {label + " " + key:26s} {m:+.3f}  [{lo:+.3f}, {hi:+.3f}]  {fmt(p)}')


if __name__ == '__main__':
    main()
