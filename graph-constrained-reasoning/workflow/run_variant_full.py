"""Sequential full-epoch A-E LoRA training on one CUDA GPU (v1 config: 1 epoch, batch=2, accum=8)."""
import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--resume', action='store_true', help='Skip completed variants from a matching run')
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()) and not args.resume:
        raise FileExistsError('Use a fresh output directory')
    args.output.mkdir(parents=True, exist_ok=True)
    plan = dict(status='running', variants={},
                interpretation='Full 1-epoch LoRA per variant from the same base, v1 config '
                               '(batch=2, accum=8, no gradient checkpointing, lr 2e-5). '
                               'Shared WebQSP validation loss recorded before/after.')
    if args.resume:
        plan = json.loads((args.output / 'manifest.json').read_text(encoding='utf-8'))
        plan['status'] = 'running'

    def save():
        (args.output / 'manifest.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
    save()

    for variant in 'ABCDE':
        output = args.output / variant
        if plan['variants'].get(variant, {}).get('status') == 'complete':
            print(f'Skipping completed variant {variant}', flush=True)
            continue
        command = [sys.executable, '-u', str(Path(__file__).with_name('train_cuda_lora.py')),
                   '--train-data', f'gcr-lab/train_variants/data/{variant}.jsonl.gz',
                   '--output', str(output)]
        print(f'Starting variant {variant} (1 epoch, batch=2 accum=8)', flush=True)
        plan['variants'][variant] = dict(command=command, status='running')
        save()
        with (args.output / f'{variant}.log').open('w', encoding='utf-8') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            plan['variants'][variant].update(status='failed', returncode=result.returncode)
            plan['status'] = 'failed'
            save()
            raise RuntimeError(f'Variant {variant} failed; see {variant}.log')
        manifest = json.loads((output / 'training_manifest.json').read_text(encoding='utf-8'))
        plan['variants'][variant].update(status='complete',
                                         before=manifest['before']['eval_loss'],
                                         after=manifest['after']['eval_loss'],
                                         data=manifest['data'],
                                         training_seconds=manifest['training_seconds'],
                                         peak_allocated_bytes=manifest.get('peak_allocated_bytes'))
        save()
        print(f"Completed {variant}: validation loss "
              f"{plan['variants'][variant]['before']:.6f} -> {plan['variants'][variant]['after']:.6f}", flush=True)
    plan['status'] = 'complete'
    save()


if __name__ == '__main__':
    main()
