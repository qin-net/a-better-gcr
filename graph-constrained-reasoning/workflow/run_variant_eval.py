"""Evaluate A-E adapters (pilot or full run) with cuda_baseline, then score path faithfulness.

Every run decodes with --prefill-path on the first N test questions of WebQSP
and CWQ. Runs:
  official    no adapter, directed graph (reference for the shared start point)
  A           directed graph, and A_multi on the multi-relation graph, which
              separates the graph change from the data change
  B-E         multi-relation graph, 2 hops
  E_hops3     E with a 3-hop trie. The trie is still built from the question
              subgraph only, not the training graph pool, so this checks the
              decoding depth, not the pool repair (FINDINGS K).

Completed runs are skipped on restart; an incomplete run directory must be
archived first (--keep-going does that itself, renaming it to <run>_failed).
Results: <output>/<dataset>_<limit>/<run>/ and faithfulness.json;
<output> defaults to gcr-lab/experiments/cuda_results/<pilot directory name>.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score_faithfulness  # noqa: E402

DATASETS = {'webqsp': ('rmanluo/RoG-webqsp', 'c0632533135a06f8c5d536b420deec5fcb5c58f3'),
            'cwq': ('rmanluo/RoG-cwq', 'b0f6275586286312c4e99ef4b0adc65463c91f8e')}


def runs(pilot):
    yield 'official', None, 'directed', 2
    yield 'A', pilot / 'A' / 'adapter', 'directed', 2
    yield 'A_multi', pilot / 'A' / 'adapter', 'multi', 2
    for variant in 'BCDE':
        yield variant, pilot / variant / 'adapter', 'multi', 2
    yield 'E_hops3', pilot / 'E' / 'adapter', 'multi', 3


def complete(output):
    manifest = output / 'manifest.json'
    return manifest.exists() and json.loads(manifest.read_text(encoding='utf-8'))['status'] == 'complete'


def archive(output):
    """Move a failed run aside so a restart retries it from scratch."""
    n, target = 1, output.with_name(output.name + '_failed')
    while target.exists() or target.with_suffix('.log').exists():
        n += 1
        target = output.with_name(f'{output.name}_failed{n}')
    if output.exists():
        output.rename(target)
    log = output.parent / f'{output.name}.log'
    if log.exists():
        log.rename(target.parent / f'{target.name}.log')
    return target


def evaluate(pilot, output, datasets=('webqsp', 'cwq'), limit=100, only=None,
             keep_going=False, seconds_per_question=None, on_event=print):
    """Run and score. Returns {dataset: score results} and a list of failures."""
    known = [r[0] for r in runs(pilot)]
    if only and set(only) - set(known):
        raise ValueError(f'unknown runs {sorted(set(only) - set(known))}; choose from {known}')
    workflow = Path(__file__).resolve().parent
    scores, failures = {}, []
    for dataset in datasets:
        name, revision = DATASETS[dataset]
        root = output / f'{dataset}_{limit}'
        for run, adapter, graph, hops in runs(pilot):
            if only and run not in only:
                continue
            target = root / run
            if complete(target):
                on_event(f'Skipping completed {dataset}/{run}')
                continue
            if target.exists() and any(target.iterdir()):
                if not keep_going:
                    raise FileExistsError(f'Archive the incomplete run first: {target}')
                on_event(f'Archived incomplete {dataset}/{run} -> {archive(target).name}')
            command = [sys.executable, '-u', str(workflow / 'cuda_baseline.py'),
                       '--dataset', name, '--dataset-revision', revision, '--split', 'test',
                       '--limit', str(limit), '--prefill-path', '--graph', graph, '--hops', str(hops),
                       '--output', str(target)]
            if adapter is not None:
                if not (adapter / 'adapter_model.safetensors').exists():
                    raise FileNotFoundError(f'Missing adapter: {adapter}')
                command += ['--adapter', str(adapter)]
            on_event(f'Starting {dataset}/{run}')
            target.mkdir(parents=True, exist_ok=True)
            timeout = seconds_per_question * limit + 600 if seconds_per_question else None
            with (root / f'{run}.log').open('w', encoding='utf-8') as log:
                try:
                    code = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                          timeout=timeout).returncode
                    reason = f'exit code {code}' if code else None
                except subprocess.TimeoutExpired:
                    reason = f'timed out after {timeout} s'
            if reason is None and not complete(target):
                reason = 'manifest not complete'
            if reason:
                if not keep_going:
                    raise RuntimeError(f'{dataset}/{run} failed ({reason}); see {root / (run + ".log")}')
                moved = archive(target)
                failures.append(dict(dataset=dataset, limit=limit, run=run, reason=reason,
                                     log=str(moved.parent / f'{moved.name}.log')))
                on_event(f'FAILED {dataset}/{run}: {reason}; kept as {moved.name}')
                continue
            on_event(f'Completed {dataset}/{run}')
        # Score every completed run of this dataset, including ones from earlier invocations.
        done = [root / r for r in known if complete(root / r)]
        if done:
            try:
                gold = score_faithfulness.load_gold(score_faithfulness.DEFAULT_GOLD)
                scores[dataset] = [score_faithfulness.score_run(d, gold) for d in done]
            except Exception as e:  # predictions are kept; scoring can be redone offline
                if not keep_going:
                    raise
                failures.append(dict(dataset=dataset, limit=limit, run='scoring', reason=repr(e)))
                on_event(f'FAILED scoring {dataset}_{limit}: {e!r}')
                continue
            (root / 'faithfulness.json').write_text(json.dumps(scores[dataset], indent=2), encoding='utf-8')
            on_event(table(scores[dataset]))
    return scores, failures


def table(results):
    lines = [f"{'run':10s} {'n':>4s} {'hit':>6s} {'f1':>6s} {'f.hit':>6s} {'unf.hit':>7s} {'faith':>6s}"]
    for r in results:
        q, c = r['question'], r['candidate']
        lines.append(f"{Path(r['run']).name:10s} {r['questions']:4d} {q['hit']:6.3f} {q['f1']:6.3f} "
                     f"{q['faithful_hit']:6.3f} {q['unfaithful_hit']:7.3f} {c['faithful']:6.3f}")
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--pilot', type=Path, default=Path('graph-constrained-reasoning/training_runs/ae_pilot_128_mb1'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--datasets', nargs='+', default=['webqsp', 'cwq'], choices=sorted(DATASETS))
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--runs', nargs='+', help='Subset of runs, e.g. official A C (default: all)')
    parser.add_argument('--keep-going', action='store_true', help='Archive a failed run and continue')
    parser.add_argument('--seconds-per-question', type=float, help='Kill a run after this budget (+10 min)')
    args = parser.parse_args()
    output = args.output or Path('gcr-lab/experiments/cuda_results') / args.pilot.name
    try:
        _, failures = evaluate(args.pilot, output, args.datasets, args.limit, args.runs,
                               args.keep_going, args.seconds_per_question,
                               on_event=lambda m: print(m, flush=True))
    except ValueError as e:
        parser.error(str(e))
    if failures:
        sys.exit(f'{len(failures)} runs failed: {failures}')


if __name__ == '__main__':
    main()
