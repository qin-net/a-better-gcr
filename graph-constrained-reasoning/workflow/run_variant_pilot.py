"""Equal-update A-E pilot training, sequentially on one CUDA GPU."""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--steps', type=int, default=128)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--resume', action='store_true', help='Skip completed variants from a matching pilot')
    args = parser.parse_args()
    if args.steps < 1:
        parser.error('steps must be positive')
    if args.output.exists() and any(args.output.iterdir()) and not args.resume:
        raise FileExistsError('Use a fresh pilot directory')
    args.output.mkdir(parents=True, exist_ok=True)
    plan = dict(status='running', fixed_updates=args.steps, variants={},
                interpretation='Pilot with equal updates, not complete epochs; validation loss is the shared WebQSP directed-path yardstick.')
    if args.resume:
        plan = json.loads((args.output / 'pilot_manifest.json').read_text(encoding='utf-8'))
        if plan['fixed_updates'] != args.steps:
            raise ValueError('Cannot resume with a different update budget')
        plan['status'] = 'running'
    def save():
        (args.output / 'pilot_manifest.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    save()
    for variant in 'ABCDE':
        output = args.output / variant
        if plan['variants'].get(variant, {}).get('status') == 'complete':
            saved = json.loads((output / 'training_manifest.json').read_text(encoding='utf-8'))
            if saved['status'] != 'complete' or saved['training_args']['max_steps'] != args.steps:
                raise ValueError(f'Invalid completed state for {variant}')
            print(f'Skipping completed variant {variant}', flush=True)
            continue
        command = [sys.executable, '-u', str(Path(__file__).with_name('train_cuda_lora.py')),
                   '--train-data', f'gcr-lab/train_variants/data/{variant}.jsonl.gz',
                   '--max-steps', str(args.steps), '--batch-size', '1', '--gradient-accumulation', '16',
                   '--gradient-checkpointing',
                   '--validation-limit', '246', '--output', str(output)]
        print(f'Starting variant {variant}: {args.steps} optimizer updates', flush=True)
        entry = dict(command=command, status='running')
        plan['variants'][variant] = entry
        save()
        with (args.output / f'{variant}.log').open('w', encoding='utf-8') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            entry.update(status='failed', returncode=result.returncode)
            plan['status'] = 'failed'
            save()
            raise RuntimeError(f'Variant {variant} failed; see {variant}.log')
        manifest = json.loads((output / 'training_manifest.json').read_text(encoding='utf-8'))
        entry.update(status='complete', before=manifest['before']['eval_loss'],
                     after=manifest['after']['eval_loss'], data=manifest['data'],
                     training_seconds=manifest['training_seconds'])
        save()
        print(f"Completed {variant}: validation loss {entry['before']:.6f} -> {entry['after']:.6f}", flush=True)
    plan['status'] = 'complete'
    save()


if __name__ == '__main__':
    main()
