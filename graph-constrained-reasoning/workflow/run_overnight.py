"""Unattended overnight evaluation of the A-E adapters, committing results as it goes.

Stages, in priority order (STATUS_AND_NEXT.md section 3):
  1  ae_full, all runs, first 100 test questions of WebQSP and CWQ
  2  ae_full, official A A_multi B C D, first 500 questions
  3  ae_pilot_128_mb1, A B C D, first 100 questions

A failed run is renamed to <run>_failed and the night continues. After each
stage the results and OVERNIGHT_REPORT.md are committed (and pushed with
--push). Rerunning the same command resumes, skipping completed runs.

  .venv/Scripts/python.exe -u graph-constrained-reasoning/workflow/run_overnight.py --push
"""
import argparse
import datetime
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_variant_eval  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
RUNS = REPO / 'graph-constrained-reasoning' / 'training_runs'
RESULTS = REPO / 'gcr-lab' / 'experiments' / 'cuda_results'
STAGES = [
    dict(stage=1, pilot='ae_full', limit=100, runs=None),
    dict(stage=2, pilot='ae_full', limit=500, runs=['official', 'A', 'A_multi', 'B', 'C', 'D']),
    dict(stage=3, pilot='ae_pilot_128_mb1', limit=100, runs=['A', 'B', 'C', 'D']),
]
REPORT = RESULTS / 'OVERNIGHT_REPORT.md'


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def git(*args, check=True):
    return subprocess.run(['git', *args], cwd=REPO, check=check, capture_output=True, text=True)


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
    for stage in STAGES:
        for variant in 'ABCDE':
            adapter = RUNS / stage['pilot'] / variant / 'adapter' / 'adapter_model.safetensors'
            if not adapter.exists():
                sys.exit(f'Missing adapter {adapter}')
    return torch.cuda.get_device_name()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--stages', type=int, nargs='+', default=[1, 2, 3], choices=[1, 2, 3])
    parser.add_argument('--push', action='store_true', help='git push after each stage commit')
    parser.add_argument('--seconds-per-question', type=float, default=20,
                        help='Per-run time budget (+10 min); typical runs need about 2 s per question')
    parser.add_argument('--hours', type=float, help='Start no new stage after this many hours')
    args = parser.parse_args()
    gpu = preflight()
    log = [f'# 过夜评测记录', '', f'- 开始：{now()}，GPU：{gpu}，commit：{git("rev-parse", "--short", "HEAD").stdout.strip()}',
           f'- 命令：`{" ".join(sys.argv)}`', '']

    def event(message):
        line = f'[{now()}] {message}'
        print(line, flush=True)
        if '\n' in message:  # score table
            log.extend(['```', message, '```', ''])
        else:
            log.append(f'- {line}')

    all_failures, night_started = [], time.time()
    for stage in (s for s in STAGES if s['stage'] in args.stages):
        if args.hours and time.time() - night_started > args.hours * 3600:
            event(f'Stage {stage["stage"]} not started: {args.hours} h budget used')
            break
        started = time.time()
        event(f'Stage {stage["stage"]}: {stage["pilot"]}, first {stage["limit"]}, runs {stage["runs"] or "all"}')
        log.append('')
        _, failures = run_variant_eval.evaluate(
            RUNS / stage['pilot'], RESULTS / stage['pilot'], limit=stage['limit'], only=stage['runs'],
            keep_going=True, seconds_per_question=args.seconds_per_question, on_event=event)
        all_failures += failures
        event(f'Stage {stage["stage"]} done in {(time.time() - started) / 60:.0f} min, '
              f'{len(failures)} failed' + (f': {json.dumps(failures, ensure_ascii=False)}' if failures else ''))
        REPORT.write_text('\n'.join(log) + '\n', encoding='utf-8')
        git('add', str(RESULTS / stage['pilot']), str(REPORT))
        message = (f'过夜评测阶段 {stage["stage"]}：{stage["pilot"]} 前 {stage["limit"]} 题'
                   + (f'，{len(failures)} 组失败' if failures else '，全部完成'))
        commit = git('commit', '-m', message, check=False)
        event('Committed' if commit.returncode == 0 else f'Commit skipped: {commit.stdout.strip()[-200:]}')
        if args.push:
            push = git('push', check=False)
            event('Pushed' if push.returncode == 0 else f'Push failed: {push.stderr.strip()[-300:]}')
        REPORT.write_text('\n'.join(log) + '\n', encoding='utf-8')
    event(f'All done, {len(all_failures)} failed runs')
    REPORT.write_text('\n'.join(log) + '\n', encoding='utf-8')
    git('add', str(REPORT))
    if git('commit', '-m', '过夜评测结束', check=False).returncode == 0 and args.push:
        git('push', check=False)


if __name__ == '__main__':
    main()
