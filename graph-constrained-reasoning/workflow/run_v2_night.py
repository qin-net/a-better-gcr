"""Unattended night: train the v2 path-selection fixes, evaluate them, commit as it goes.

Stages, in priority order (gcr-lab/train_variants/V2_NIGHT.md):
  1  train C2 D2                       -> eval WebQSP + CWQ, first 500
  2  train C_wq C_fwd (ablations)      -> eval WebQSP + CWQ, first 500
  3  train C2 and A with seeds 43, 44  -> eval WebQSP + CWQ, first 500
  4  no training                       -> A_multi and C2 on the full WebQSP test set (1,628)

Each stage trains what it needs (skipping adapters that are already complete),
evaluates, scores against the 11-04 ae_full runs with paired McNemar tests,
then commits and (with --push) pushes adapters, predictions and
V2_NIGHT_REPORT.md. A failed training or evaluation is renamed <name>_failed
and the night continues; runs that need a missing adapter are skipped.
Rerunning the same command resumes.

  .venv/Scripts/python.exe -u graph-constrained-reasoning/workflow/run_v2_night.py --push --hours 10
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_variant_eval  # noqa: E402
import score_faithfulness  # noqa: E402
from run_overnight import git, now  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = Path(__file__).resolve().parent
DATA = REPO / 'gcr-lab' / 'train_variants' / 'data'
RUNS = REPO / 'graph-constrained-reasoning' / 'training_runs'
V2 = RUNS / 'v2'
RESULTS = REPO / 'gcr-lab' / 'experiments' / 'cuda_results'
OUT = RESULTS / 'v2'
REFERENCE = RESULTS / 'ae_full'
REPORT = RESULTS / 'V2_NIGHT_REPORT.md'

# adapter name -> (packed training set, seed)
TRAIN = {'C2': ('C2', 42), 'D2': ('D2', 42), 'C_wq': ('C_wq', 42), 'C_fwd': ('C_fwd', 42),
         'C2_s43': ('C2', 43), 'C2_s44': ('C2', 44), 'A_s43': ('A', 43), 'A_s44': ('A', 44)}
STAGES = [
    dict(stage=1, train=['C2', 'D2'], limit=500, datasets=['webqsp', 'cwq'],
         runs=[('C2', 'C2'), ('D2', 'D2')]),
    dict(stage=2, train=['C_wq', 'C_fwd'], limit=500, datasets=['webqsp', 'cwq'],
         runs=[('C_wq', 'C_wq'), ('C_fwd', 'C_fwd')]),
    dict(stage=3, train=['C2_s43', 'C2_s44', 'A_s43', 'A_s44'], limit=500, datasets=['webqsp', 'cwq'],
         runs=[('C2_s43', 'C2_s43'), ('C2_s44', 'C2_s44'), ('A_multi_s43', 'A_s43'), ('A_multi_s44', 'A_s44')]),
    dict(stage=4, train=[], limit=1628, datasets=['webqsp'],
         runs=[('A_multi', RUNS / 'ae_full' / 'A'), ('C2', 'C2')]),
]
# 11-04 runs scored alongside (same first-N questions, same decoding settings).
REFERENCE_RUNS = ['A_multi', 'C', 'D']


def adapter_dir(name_or_path):
    return Path(name_or_path) if isinstance(name_or_path, Path) else V2 / name_or_path


def trained(output):
    manifest = output / 'training_manifest.json'
    return manifest.exists() and json.loads(manifest.read_text(encoding='utf-8'))['status'] == 'complete'


def train(name, event):
    """Train one adapter unless already complete. Returns True when it is usable."""
    data, seed = TRAIN[name]
    output = V2 / name
    if trained(output):
        event(f'Skipping trained {name}')
        return True
    if output.exists():
        event(f'Archived incomplete training {name} -> {run_variant_eval.archive(output).name}')
    command = [sys.executable, '-u', str(WORKFLOW / 'train_cuda_lora.py'),
               '--train-data', str(DATA / f'{data}.jsonl.gz'), '--seed', str(seed), '--output', str(output)]
    event(f'Training {name} ({data}.jsonl.gz, seed {seed})')
    V2.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with (V2 / f'{name}.log').open('w', encoding='utf-8') as log:
        code = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT).returncode
    if code or not trained(output):
        moved = run_variant_eval.archive(output) if output.exists() else output
        event(f'FAILED training {name}: exit code {code}; kept as {moved.name} (log {moved.name}.log)')
        return False
    m = json.loads((output / 'training_manifest.json').read_text(encoding='utf-8'))
    event(f'Trained {name} in {(time.time() - started) / 60:.0f} min, '
          f'{m["data"]["train"]["training_sequences"]} sequences, '
          f'validation loss {m["before"]["eval_loss"]:.4f} -> {m["after"]["eval_loss"]:.4f}')
    return True


def paired(dataset, limit, names):
    """McNemar of every completed v2 run against the 11-04 A_multi and C (or this night's A_multi)."""
    gold = score_faithfulness.load_gold(score_faithfulness.DEFAULT_GOLD)
    bases = [('11-04 A_multi', REFERENCE / f'{dataset}_{limit}' / 'A_multi'),
             ('11-04 C', REFERENCE / f'{dataset}_{limit}' / 'C'),
             ('A_multi', OUT / f'{dataset}_{limit}' / 'A_multi')]
    lines = []
    for label, base_dir in bases:
        if not run_variant_eval.complete(base_dir):
            continue
        base = score_faithfulness.score_questions(base_dir, gold)[1]
        lines.append(f'paired vs {label} (gained/lost, exact McNemar p)')
        for name in names:
            run = OUT / f'{dataset}_{limit}' / name
            if run == base_dir or not run_variant_eval.complete(run):
                continue
            other = score_faithfulness.score_questions(run, gold)[1]
            lines.append(f'{name:12s}' + ''.join(
                '  {}: +{}/-{} p={:.2g}'.format(key, *score_faithfulness.mcnemar(base, other, key))
                for key in ('hit', 'faithful_hit')))
    return '\n'.join(lines)


def preflight():
    import torch
    if not torch.cuda.is_available():
        sys.exit('CUDA is not available')
    try:
        import pytest  # noqa: F401
    except ImportError:
        print('pytest not installed, skipping tests', flush=True)
    else:
        tests = subprocess.run([sys.executable, '-m', 'pytest', '-q', 'graph-constrained-reasoning/tests'],
                               cwd=REPO, capture_output=True, text=True)
        if tests.returncode:
            sys.exit('Tests failed, not starting:\n' + tests.stdout[-3000:])
    for data, _ in TRAIN.values():
        if not (DATA / f'{data}.jsonl.gz').exists():
            sys.exit(f'Missing training set {DATA / data}.jsonl.gz; git pull first')
    if not (RUNS / 'ae_full' / 'A' / 'adapter' / 'adapter_model.safetensors').exists():
        sys.exit('Missing ae_full/A adapter')
    return torch.cuda.get_device_name()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--stages', type=int, nargs='+', default=[1, 2, 3, 4], choices=[1, 2, 3, 4])
    parser.add_argument('--push', action='store_true', help='git push after each stage commit')
    parser.add_argument('--seconds-per-question', type=float, default=20,
                        help='Per-run time budget (+10 min); typical runs need about 2 s per question')
    parser.add_argument('--hours', type=float, help='Start no new stage after this many hours')
    args = parser.parse_args()
    gpu = preflight()
    log = ['# v2 训练与评测记录', '', f'- 开始：{now()}，GPU：{gpu}，commit：{git("rev-parse", "--short", "HEAD").stdout.strip()}',
           f'- 命令：`{" ".join(sys.argv)}`', '']

    def event(message):
        line = f'[{now()}] {message}'
        print(line, flush=True)
        if '\n' in message:  # score table
            log.extend(['```', message, '```', ''])
        else:
            log.append(f'- {line}')

    def write_report():
        REPORT.write_text('\n'.join(log) + '\n', encoding='utf-8')

    all_failures, night_started = [], time.time()
    all_names = [name for s in STAGES for name, _ in s['runs']]
    for stage in (s for s in STAGES if s['stage'] in args.stages):
        if args.hours and time.time() - night_started > args.hours * 3600:
            event(f'Stage {stage["stage"]} not started: {args.hours} h budget used')
            break
        started = time.time()
        event(f'Stage {stage["stage"]}: train {stage["train"] or "nothing"}, '
              f'eval {[n for n, _ in stage["runs"]]} on {stage["datasets"]}, first {stage["limit"]}')
        log.append('')
        failures = [dict(stage=stage['stage'], run=f'train {name}') for name in stage['train']
                    if not train(name, event)]
        plan = []
        for name, adapter in stage['runs']:
            path = adapter_dir(adapter)
            if (path / 'adapter' / 'adapter_model.safetensors').exists():
                plan.append((name, path / 'adapter', 'multi', 2))
            else:
                event(f'Skipping eval {name}: adapter {path.name} not trained')
        if plan:
            references = [REFERENCE / '{dataset}_{limit}' / r for r in REFERENCE_RUNS]
            references += [OUT / '{dataset}_{limit}' / n for n in dict.fromkeys(all_names)
                           if n not in {p[0] for p in plan}]
            _, eval_failures = run_variant_eval.evaluate(
                None, OUT, stage['datasets'], stage['limit'], keep_going=True,
                seconds_per_question=args.seconds_per_question, on_event=event,
                plan=plan, references=references)
            failures += eval_failures
            for dataset in stage['datasets']:
                try:
                    text = paired(dataset, stage['limit'], list(dict.fromkeys(all_names)))
                except Exception as e:  # predictions are kept; can be redone offline
                    text = f'paired tests failed: {e!r}'
                if text:
                    event(f'{dataset}_{stage["limit"]}\n{text}')
        all_failures += failures
        event(f'Stage {stage["stage"]} done in {(time.time() - started) / 60:.0f} min, '
              f'{len(failures)} failed' + (f': {json.dumps(failures, ensure_ascii=False)}' if failures else ''))
        write_report()
        paths = [str(REPORT)] + [str(p) for p in (V2, OUT) if p.exists()]
        git('add', *paths)
        message = (f'v2 过夜阶段 {stage["stage"]}' + (f'，{len(failures)} 项失败' if failures else '，全部完成'))
        commit = git('commit', '-m', message, check=False)
        event('Committed' if commit.returncode == 0 else f'Commit skipped: {commit.stdout.strip()[-200:]}')
        if args.push:
            push = git('push', check=False)
            event('Pushed' if push.returncode == 0 else f'Push failed: {push.stderr.strip()[-300:]}')
        write_report()
    event(f'All done, {len(all_failures)} failures')
    write_report()
    git('add', str(REPORT))
    if git('commit', '-m', 'v2 过夜结束', check=False).returncode == 0 and args.push:
        git('push', check=False)


if __name__ == '__main__':
    main()
