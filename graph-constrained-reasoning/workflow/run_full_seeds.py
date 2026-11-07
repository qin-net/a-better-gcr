"""Full test sets, three seeds per arm: does C2's faithfulness gain over A_multi replicate?

gcr-lab/STATUS_AND_NEXT.md section 7. On the first 500 questions the CWQ gain is
+2.7 points (3 seeds v 3 seeds, p=0.14 resampling seed questions), and the WebQSP
full-set gain (+2.3 points, p=0.007) rests on seed 42 alone. No training: every
adapter is from the v2 night.
  1  WebQSP, all 1,628: C2 and A_multi, seeds 43 and 44 (seed 42 is v2 stage 4)  ~3.4 h
  2  CWQ, all 3,531: C2 and A_multi, seeds 42, 43, 44                           ~12 h

Runs go in matched pairs (C2, then A_multi of the same seed), so a night cut
short still leaves usable comparisons. After every run the score table and the
seed-question test of C2 against A_multi (per seed and seeds pooled) go into
cuda_results/FULL_SEEDS_REPORT.md, which is committed, and pushed with --push.
A failed run is renamed <name>_failed and the rest continue. Rerunning the same
command resumes and appends to the report.

  .venv/Scripts/python.exe -u graph-constrained-reasoning/workflow/run_full_seeds.py --push
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_v2_night  # noqa: E402
import run_variant_eval  # noqa: E402
import score_faithfulness  # noqa: E402
from run_overnight import git, now  # noqa: E402
from run_v2_night import OUT, RESULTS, RUNS, V2  # noqa: E402

REPORT = RESULTS / 'FULL_SEEDS_REPORT.md'
# seed -> (C2 run, A_multi run); run name -> adapter directory
PAIRS = {42: ('C2', 'A_multi'), 43: ('C2_s43', 'A_multi_s43'), 44: ('C2_s44', 'A_multi_s44')}
ADAPTERS = {'C2': V2 / 'C2', 'A_multi': RUNS / 'ae_full' / 'A',
            'C2_s43': V2 / 'C2_s43', 'A_multi_s43': V2 / 'A_s43',
            'C2_s44': V2 / 'C2_s44', 'A_multi_s44': V2 / 'A_s44'}
STAGES = [dict(stage=1, dataset='webqsp', limit=1628, seeds=[43, 44]),
          dict(stage=2, dataset='cwq', limit=3531, seeds=[42, 43, 44])]


def seed_comparison(dataset, limit):
    """C2 minus A_multi per seed and pooled, resampling seed questions."""
    root = OUT / f'{dataset}_{limit}'
    pairs = {s: p for s, p in PAIRS.items() if all(run_variant_eval.complete(root / n) for n in p)}
    if not pairs:
        return ''
    gold = score_faithfulness.load_gold(score_faithfulness.DEFAULT_GOLD)
    canon, shortcut = score_faithfulness.load_criterion(score_faithfulness.DEFAULT_CRITERION)
    scored = {n: {q['id']: q for q in score_faithfulness.score_questions(root / n, gold, canon, shortcut)[1]}
              for p in pairs.values() for n in p}
    ids = [q for q in next(iter(scored.values())) if all(q in s for s in scored.values())]
    groups = [(f'seed {s}', [p]) for s, p in pairs.items()]
    if len(pairs) > 1:
        groups.append((f'{len(pairs)}v{len(pairs)} pooled', list(pairs.values())))
    lines = [f'C2 - A_multi, {dataset}_{limit}, {len(ids)} questions; '
             'points, 95% CI and sign-flip p over seed questions']
    for label, use in groups:
        for key in ('hit', 'faithful_strict_hit'):
            d = {q: sum(bool(scored[c][q][key]) - bool(scored[a][q][key]) for c, a in use) / len(use)
                 for q in ids}
            m, lo, hi, p = score_faithfulness.seed_test(d)
            lines.append(f'{label:12s} {key:20s} {100 * m:+5.1f} [{100 * lo:+5.1f}, {100 * hi:+5.1f}]  '
                         + (f'p={p:.2g}' if p >= 1e-4 else 'p<1e-4'))
    return '\n'.join(lines)


def preflight():
    gpu = run_v2_night.preflight()
    for name, path in ADAPTERS.items():
        if not (path / 'adapter' / 'adapter_model.safetensors').exists():
            sys.exit(f'Missing adapter for {name}: {path}; git pull first')
    return gpu


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--stages', type=int, nargs='+', default=[1, 2], choices=[1, 2])
    parser.add_argument('--push', action='store_true', help='git push after each run')
    parser.add_argument('--seconds-per-question', type=float, default=20,
                        help='Per-run time budget (+10 min); typical runs need about 2 s per question')
    parser.add_argument('--hours', type=float, help='Start no new run after this many hours')
    args = parser.parse_args()
    gpu = preflight()
    log = REPORT.read_text(encoding='utf-8').rstrip('\n').split('\n') + [''] if REPORT.exists() \
        else ['# 全量多 seed：C2 对 A_multi', '']
    log += [f'## {now()} 开始，GPU：{gpu}，commit：{git("rev-parse", "--short", "HEAD").stdout.strip()}',
            f'- 命令：`{" ".join(sys.argv)}`', '']

    def event(message):
        line = f'[{now()}] {message}'
        print(line, flush=True)
        if '\n' in message:  # score table
            log.extend(['```', message, '```', ''])
        else:
            log.append(f'- {line}')

    def save(message):
        REPORT.write_text('\n'.join(log) + '\n', encoding='utf-8')
        git('add', str(REPORT), *(str(p) for p in OUT.glob('*_1628')), *(str(p) for p in OUT.glob('*_3531')))
        commit = git('commit', '-m', message, check=False)
        if commit.returncode == 0 and args.push:
            push = git('push', check=False)
            if push.returncode:
                event(f'Push failed: {push.stderr.strip()[-300:]}')
                REPORT.write_text('\n'.join(log) + '\n', encoding='utf-8')

    plan = [(s['dataset'], s['limit'], n) for s in STAGES if s['stage'] in args.stages
            for seed in s['seeds'] for n in PAIRS[seed]]
    failures, started = [], time.time()
    for dataset, limit, name in plan:
        if run_variant_eval.complete(OUT / f'{dataset}_{limit}' / name):
            event(f'Skipping completed {dataset}_{limit}/{name}')
            continue
        if args.hours and time.time() - started > args.hours * 3600:
            event(f'Stopping before {dataset}_{limit}/{name}: {args.hours} h budget used')
            break
        references = [OUT / '{dataset}_{limit}' / n for n in ADAPTERS if n != name]
        _, failed = run_variant_eval.evaluate(
            None, OUT, [dataset], limit, keep_going=True, seconds_per_question=args.seconds_per_question,
            on_event=event, plan=[(name, ADAPTERS[name] / 'adapter', 'multi', 2)], references=references)
        failures += failed
        try:
            text = seed_comparison(dataset, limit)
        except Exception as e:  # predictions are kept; can be redone offline
            text = f'seed comparison failed: {e!r}'
        if text:
            event(text)
        save(f'全量多 seed：{dataset}_{limit} {name}' + ('，失败' if failed else ''))
    event(f'All done, {len(failures)} failures' + (f': {json.dumps(failures, ensure_ascii=False)}' if failures else ''))
    save('全量多 seed 结束')


if __name__ == '__main__':
    main()
