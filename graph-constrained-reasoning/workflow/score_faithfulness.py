"""Score cuda_baseline runs for path faithfulness against gold SPARQL relations.

A decoded candidate is
  grounded  when path_audit found every step in the question subgraph,
  hit       when its answer section matches a gold answer,
  faithful  when it is grounded and all its relations appear in one annotated
            SPARQL parse (gcr-lab/experiments/build_gold_relations.py),
  faithful_strict  the same with inverse relation names merged, and not through
            a first step that walks a type edge backwards (gcr-lab/experiments/
            build_faithfulness_criterion.py). `faithful` overstates the gap
            between runs (gcr-lab FINDINGS S); report this one.

Per question: hit / f1 exactly as cuda_baseline reports them, plus
  faithful_hit    some candidate is a faithful hit,
  faithful_strict_hit  some candidate is a faithful_strict hit,
  unfaithful_hit  the question is hit, but only through unfaithful candidates,
  shortcut_hit    some candidate hits through a type shortcut.

Usage:
  python workflow/score_faithfulness.py RUN_DIR [RUN_DIR ...] [--json out.json] [--baseline RUN_DIR] [--criterion FILE]
"""
import argparse
import gzip
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.qa_utils import eval_f1, eval_hit, match

DEFAULT_GOLD = Path(__file__).resolve().parents[2] / 'gcr-lab' / 'eval' / 'gold_relations.jsonl.gz'
DEFAULT_CRITERION = Path(__file__).resolve().parents[2] / 'gcr-lab' / 'eval' / 'faithfulness_criterion.json'


def load_gold(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return {row['id']: [set(p) for p in row['parses']] for row in map(json.loads, f)}


def load_criterion(path):
    """Inverse relation classes and type-shortcut steps (gcr-lab FINDINGS S).

    Without the file the scorer falls back to raw relation names, which is the
    old criterion: it counts a forward path as unfaithful when the subgraph
    carries the inverse name, and it accepts type enumeration as faithful.
    """
    if not path:
        return {}, {}
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f'{path}: the corrected criterion is missing; build it with '
                                'gcr-lab/experiments/build_faithfulness_criterion.py, '
                                'or pass --criterion "" to score with raw relation names')
    row = json.loads(path.read_text(encoding='utf-8'))
    return row['inverse_classes'], {q: [tuple(s) for s in v] for q, v in row['shortcut'].items()}


def relations(path):
    return path.split(' -> ')[1::2]


def path_steps(path):
    s = path.split(' -> ')
    return [(s[i], s[i + 1], s[i + 2]) for i in range(0, len(s) - 2, 2)]


def score_candidate(text, audit, answers, parses, canon, shortcut):
    answer = text.split('# Answer:', 1)[1].strip() if '# Answer:' in text else ''
    hit = bool(answer) and any(match(answer, a) for a in answers)
    rels = set(relations(audit.get('path', '')))
    faithful = audit['valid'] and bool(rels) and any(rels <= p for p in parses)
    path = path_steps(audit.get('path', ''))
    # a first step that walks a type edge against its direction enumerates
    # instances of a class rather than following the fact
    shortcut_hit = bool(path) and path[0] in shortcut
    strict = (audit['valid'] and bool(rels)
              and any({canon.get(r, r) for r in rels} <= {canon.get(r, r) for r in parse}
                      for parse in parses)
              and not shortcut_hit)
    return {'grounded': audit['valid'], 'hit': hit, 'faithful': faithful,
            'faithful_strict': strict, 'shortcut': shortcut_hit}


def score_questions(path, gold, canon, shortcut):
    """Per-question and per-candidate labels for one run."""
    path = Path(path)
    if path.is_dir():
        path = path / 'predictions.jsonl'
    questions, candidates, missing = [], [], 0
    for row in map(json.loads, path.open(encoding='utf-8')):
        if row['id'] not in gold:
            missing += 1
            continue
        steps = shortcut.get(row['id'], ())
        cands = [score_candidate(t, a, row['ground_truth'], gold[row['id']], canon, steps)
                 for t, a in zip(row['prediction'], row['path_audit'])]
        candidates.extend(cands)
        answers = list(dict.fromkeys(t.split('# Answer:', 1)[1].strip()
                                     for t in row['prediction'] if '# Answer:' in t))
        hit = eval_hit(' '.join(answers), row['ground_truth'])
        faithful_hit = any(c['hit'] and c['faithful'] for c in cands)
        faithful_strict_hit = any(c['hit'] and c['faithful_strict'] for c in cands)
        questions.append({'id': row['id'], 'hit': hit,
                          'f1': eval_f1(answers, row['ground_truth'])[0],
                          'any_faithful': any(c['faithful'] for c in cands),
                          'faithful_hit': faithful_hit,
                          'faithful_strict_hit': faithful_strict_hit,
                          'unfaithful_hit': bool(hit) and not faithful_hit,
                          'shortcut_hit': any(c['hit'] and c['shortcut'] for c in cands)})
    if not questions:
        raise ValueError(f'{path}: no question has gold relations')
    return path, questions, candidates, missing


def mcnemar(base, other, key):
    """Exact two-sided McNemar test on questions both runs answered.

    Returns (gained, lost, p): questions where only `other` / only `base` has `key`.
    """
    base = {q['id']: bool(q[key]) for q in base}
    pairs = [(base[q['id']], bool(q[key])) for q in other if q['id'] in base]
    gained = sum(not b and o for b, o in pairs)
    lost = sum(b and not o for b, o in pairs)
    n = gained + lost
    p = min(1.0, 2 * sum(math.comb(n, k) for k in range(min(gained, lost) + 1)) / 2 ** n) if n else 1.0
    return gained, lost, p


def seed_test(diffs, n=2000, flips=10000):
    """Paired test that resamples whole seed questions (gcr-lab FINDINGS W, X).

    diffs: question id -> per-question difference (other - base, may be a mean
    over seeds). CWQ ids are <WebQSP seed id>_<hash> and questions sharing a seed
    are correlated, so McNemar is too optimistic there; WebQSP seeds are single
    questions. Returns (mean difference, 95% seed-bootstrap CI low, high,
    seed sign-flip permutation p). Same procedure as gcr-lab/experiments/x_cluster_tests.py.
    """
    groups = {}
    for q, d in diffs.items():
        groups.setdefault(q.split('_')[0], []).append(d)
    totals = [(sum(ds), len(ds)) for ds in groups.values()]
    rng = random.Random(0)
    vals = []
    for _ in range(n):
        pick = [totals[rng.randrange(len(totals))] for _ in totals]
        vals.append(sum(t for t, _ in pick) / sum(m for _, m in pick))
    vals.sort()
    obs = abs(sum(t for t, _ in totals))
    hits = sum(abs(sum(t if rng.random() < 0.5 else -t for t, _ in totals)) >= obs - 1e-9 for _ in range(flips))
    return sum(diffs.values()) / len(diffs), vals[int(0.025 * n)], vals[int(0.975 * n) - 1], (hits + 1) / (flips + 1)


def score_run(path, gold, canon, shortcut):
    path, questions, candidates, missing = score_questions(path, gold, canon, shortcut)

    def rate(rows, key, cond=None):
        rows = [r for r in rows if cond is None or r[cond]]
        return sum(r[key] for r in rows) / len(rows) if rows else float('nan')

    return {'run': str(path.parent), 'questions': len(questions), 'missing_gold': missing,
            'candidates': len(candidates),
            'question': {k: rate(questions, k) for k in
                         ('hit', 'f1', 'any_faithful', 'faithful_hit', 'faithful_strict_hit',
                          'unfaithful_hit', 'shortcut_hit')},
            'candidate': {'grounded': rate(candidates, 'grounded'),
                          'faithful': rate(candidates, 'faithful'),
                          'faithful_given_grounded': rate(candidates, 'faithful', 'grounded'),
                          'faithful_given_hit': rate(candidates, 'faithful', 'hit')}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('runs', nargs='+', help='cuda_baseline output dirs or predictions.jsonl')
    parser.add_argument('--gold', type=Path, default=DEFAULT_GOLD)
    parser.add_argument('--json', type=Path)
    parser.add_argument('--baseline', help='run to compare every other run against (paired McNemar)')
    parser.add_argument('--criterion', default=str(DEFAULT_CRITERION),
                        help='inverse classes and type shortcuts; pass "" for raw relation names')
    args = parser.parse_args()
    gold = load_gold(args.gold)
    canon, shortcut = load_criterion(args.criterion)
    results = [score_run(r, gold, canon, shortcut) for r in args.runs]
    print(f"{'run':40s} {'n':>5s} {'hit':>6s} {'f1':>6s} {'f.hit':>6s} {'f.strict':>8s} {'unf.hit':>7s} "
          f"{'grnd':>6s} {'faith':>6s} {'f|hit':>6s}")
    for r in results:
        q, c = r['question'], r['candidate']
        print(f"{Path(r['run']).name[:40]:40s} {r['questions']:5d} {q['hit']:6.3f} {q['f1']:6.3f} "
              f"{q['faithful_hit']:6.3f} {q['faithful_strict_hit']:8.3f} {q['unfaithful_hit']:7.3f} "
              f"{c['grounded']:6.3f} "
              f"{c['faithful']:6.3f} {c['faithful_given_hit']:6.3f}"
              + (f"  ({r['missing_gold']} without gold)" if r['missing_gold'] else ''))
    if args.baseline:
        base = score_questions(args.baseline, gold, canon, shortcut)[1]
        print(f"\npaired vs {Path(args.baseline).name} (questions gained/lost, exact McNemar p)")
        for run in args.runs:
            if Path(run) == Path(args.baseline):
                continue
            other = score_questions(run, gold, canon, shortcut)[1]
            print(f"{Path(run).name[:40]:40s}" + ''.join(
                '  {}: +{}/-{} p={:.2g}'.format(key, *mcnemar(base, other, key))
                for key in ('hit', 'faithful_hit', 'faithful_strict_hit')))
    if args.json:
        args.json.write_text(json.dumps(results, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
