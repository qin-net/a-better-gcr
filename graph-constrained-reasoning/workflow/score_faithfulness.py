"""Score cuda_baseline runs for path faithfulness against gold SPARQL relations.

A decoded candidate is
  grounded  when path_audit found every step in the question subgraph,
  hit       when its answer section matches a gold answer,
  faithful  when it is grounded and all its relations appear in one annotated
            SPARQL parse (gcr-lab/experiments/build_gold_relations.py).

Per question: hit / f1 exactly as cuda_baseline reports them, plus
  faithful_hit    some candidate is a faithful hit,
  unfaithful_hit  the question is hit, but only through unfaithful candidates.

Usage:
  python workflow/score_faithfulness.py RUN_DIR [RUN_DIR ...] [--json out.json] [--baseline RUN_DIR]
"""
import argparse
import gzip
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.qa_utils import eval_f1, eval_hit, match

DEFAULT_GOLD = Path(__file__).resolve().parents[2] / 'gcr-lab' / 'eval' / 'gold_relations.jsonl.gz'


def load_gold(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return {row['id']: [set(p) for p in row['parses']] for row in map(json.loads, f)}


def relations(path):
    return path.split(' -> ')[1::2]


def score_candidate(text, audit, answers, parses):
    answer = text.split('# Answer:', 1)[1].strip() if '# Answer:' in text else ''
    hit = bool(answer) and any(match(answer, a) for a in answers)
    rels = set(relations(audit.get('path', '')))
    faithful = audit['valid'] and bool(rels) and any(rels <= p for p in parses)
    return {'grounded': audit['valid'], 'hit': hit, 'faithful': faithful}


def score_questions(path, gold):
    """Per-question and per-candidate labels for one run."""
    path = Path(path)
    if path.is_dir():
        path = path / 'predictions.jsonl'
    questions, candidates, missing = [], [], 0
    for row in map(json.loads, path.open(encoding='utf-8')):
        if row['id'] not in gold:
            missing += 1
            continue
        cands = [score_candidate(t, a, row['ground_truth'], gold[row['id']])
                 for t, a in zip(row['prediction'], row['path_audit'])]
        candidates.extend(cands)
        answers = list(dict.fromkeys(t.split('# Answer:', 1)[1].strip()
                                     for t in row['prediction'] if '# Answer:' in t))
        hit = eval_hit(' '.join(answers), row['ground_truth'])
        faithful_hit = any(c['hit'] and c['faithful'] for c in cands)
        questions.append({'id': row['id'], 'hit': hit,
                          'f1': eval_f1(answers, row['ground_truth'])[0],
                          'any_faithful': any(c['faithful'] for c in cands),
                          'faithful_hit': faithful_hit,
                          'unfaithful_hit': bool(hit) and not faithful_hit})
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


def score_run(path, gold):
    path, questions, candidates, missing = score_questions(path, gold)

    def rate(rows, key, cond=None):
        rows = [r for r in rows if cond is None or r[cond]]
        return sum(r[key] for r in rows) / len(rows) if rows else float('nan')

    return {'run': str(path.parent), 'questions': len(questions), 'missing_gold': missing,
            'candidates': len(candidates),
            'question': {k: rate(questions, k) for k in
                         ('hit', 'f1', 'any_faithful', 'faithful_hit', 'unfaithful_hit')},
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
    args = parser.parse_args()
    gold = load_gold(args.gold)
    results = [score_run(r, gold) for r in args.runs]
    print(f"{'run':40s} {'n':>5s} {'hit':>6s} {'f1':>6s} {'f.hit':>6s} {'unf.hit':>7s} "
          f"{'grnd':>6s} {'faith':>6s} {'f|hit':>6s}")
    for r in results:
        q, c = r['question'], r['candidate']
        print(f"{Path(r['run']).name[:40]:40s} {r['questions']:5d} {q['hit']:6.3f} {q['f1']:6.3f} "
              f"{q['faithful_hit']:6.3f} {q['unfaithful_hit']:7.3f} {c['grounded']:6.3f} "
              f"{c['faithful']:6.3f} {c['faithful_given_hit']:6.3f}"
              + (f"  ({r['missing_gold']} without gold)" if r['missing_gold'] else ''))
    if args.baseline:
        base = score_questions(args.baseline, gold)[1]
        print(f"\npaired vs {Path(args.baseline).name} (questions gained/lost, exact McNemar p)")
        for run in args.runs:
            if Path(run) == Path(args.baseline):
                continue
            other = score_questions(run, gold)[1]
            print(f"{Path(run).name[:40]:40s}" + ''.join(
                '  {}: +{}/-{} p={:.2g}'.format(key, *mcnemar(base, other, key))
                for key in ('hit', 'faithful_hit')))
    if args.json:
        args.json.write_text(json.dumps(results, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
