"""Verify completed pilot provenance and write a compact, comparable summary."""
import argparse
import hashlib
import json
from pathlib import Path


def summarize(root):
    plan = json.loads((root / 'pilot_manifest.json').read_text(encoding='utf-8'))
    if plan['status'] != 'complete':
        raise ValueError('Pilot has not completed all variants')
    summaries, reference = {}, None
    for variant in 'ABCDE':
        path = root / variant / 'training_manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        if manifest['status'] != 'complete':
            raise ValueError(f'Incomplete variant {variant}')
        cfg = manifest['training_args']
        if manifest.get('continuation_adapter') is not None:
            raise ValueError('Variants must initialize independently from the same base')
        if max(log.get('step', 0) for log in manifest['log_history']) != plan['fixed_updates']:
            raise ValueError(f'Variant {variant} did not finish the update budget')
        fingerprint = dict(model=manifest['model_revision'], validation=manifest['sample_ids']['validation'],
                           seed=cfg['seed'], batch=cfg['per_device_train_batch_size'],
                           accumulation=cfg['gradient_accumulation_steps'], updates=cfg['max_steps'],
                           learning_rate=cfg['learning_rate'], checkpointing=cfg['gradient_checkpointing'],
                           validation_batch=cfg['per_device_eval_batch_size'], dtype=cfg['bf16'],
                           preprocessing_length=manifest['preprocessing']['max_length'],
                           paths_per_question=manifest['preprocessing']['paths_per_question'],
                           trainable_parameters=manifest['trainable_parameters'])
        if reference is None:
            reference = fingerprint
        if fingerprint != reference or cfg['max_steps'] != plan['fixed_updates']:
            raise ValueError(f'Comparison configuration drift in {variant}')
        if summaries and abs(manifest['before']['eval_loss'] - summaries['A']['before_loss']) > 1e-6:
            raise ValueError(f'Initial validation loss mismatch in {variant}')
        if manifest['data']['train']['kept_test_seeds']:
            raise ValueError('Test seed exclusion must remain enabled')
        source = Path(manifest['data']['train']['source'])
        if hashlib.sha256(source.read_bytes()).hexdigest() != manifest['data']['train']['sha256']:
            raise ValueError(f'Training input changed for {variant}')
        weights = root / variant / 'adapter' / 'adapter_model.safetensors'
        summaries[variant] = dict(train_sequences=manifest['data']['train']['training_sequences'],
            dropped_seed_overlap=manifest['data']['train']['dropped_seed_overlap'],
            epoch=manifest['train_metrics']['epoch'], updates=cfg['max_steps'],
            before_loss=manifest['before']['eval_loss'], after_loss=manifest['after']['eval_loss'],
            training_seconds=manifest['training_seconds'], peak_allocated_bytes=manifest['peak_allocated_bytes'],
            adapter_sha256=hashlib.sha256(weights.read_bytes()).hexdigest())
    return dict(comparison_config=reference, variants=summaries,
                caveat='Shared WebQSP directed-path validation loss only; not CWQ faithful-path accuracy or full training.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    summary = summarize(args.directory)
    output = json.dumps(summary, indent=2)
    (args.directory / 'verified_summary.json').write_text(output, encoding='utf-8')
    print(json.dumps(summary['variants'], indent=2))
