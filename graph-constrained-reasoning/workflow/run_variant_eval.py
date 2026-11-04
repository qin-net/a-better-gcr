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
archived first. Results: <output>/<dataset>_<limit>/<run>/ and faithfulness.json;
<output> defaults to gcr-lab/experiments/cuda_results/<pilot directory name>.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

DATASETS = {'webqsp': ('rmanluo/RoG-webqsp', 'c0632533135a06f8c5d536b420deec5fcb5c58f3'),
            'cwq': ('rmanluo/RoG-cwq', 'b0f6275586286312c4e99ef4b0adc65463c91f8e')}


def runs(pilot):
    yield 'official', None, 'directed', 2
    yield 'A', pilot / 'A' / 'adapter', 'directed', 2
    yield 'A_multi', pilot / 'A' / 'adapter', 'multi', 2
    for variant in 'BCDE':
        yield variant, pilot / variant / 'adapter', 'multi', 2
    yield 'E_hops3', pilot / 'E' / 'adapter', 'multi', 3


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--pilot', type=Path, default=Path('graph-constrained-reasoning/training_runs/ae_pilot_128_mb1'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--datasets', nargs='+', default=['webqsp', 'cwq'], choices=sorted(DATASETS))
    parser.add_argument('--limit', type=int, default=100)
    args = parser.parse_args()
    args.output = args.output or Path('gcr-lab/experiments/cuda_results') / args.pilot.name
    workflow = Path(__file__).resolve().parent
    for dataset in args.datasets:
        name, revision = DATASETS[dataset]
        done = []
        for run, adapter, graph, hops in runs(args.pilot):
            output = args.output / f'{dataset}_{args.limit}' / run
            manifest = output / 'manifest.json'
            if manifest.exists() and json.loads(manifest.read_text(encoding='utf-8'))['status'] == 'complete':
                print(f'Skipping completed {dataset}/{run}', flush=True)
                done.append(output)
                continue
            if output.exists() and any(output.iterdir()):
                raise FileExistsError(f'Archive the incomplete run first: {output}')
            command = [sys.executable, '-u', str(workflow / 'cuda_baseline.py'),
                       '--dataset', name, '--dataset-revision', revision, '--split', 'test',
                       '--limit', str(args.limit), '--prefill-path', '--graph', graph, '--hops', str(hops),
                       '--output', str(output)]
            if adapter is not None:
                if not (adapter / 'adapter_model.safetensors').exists():
                    raise FileNotFoundError(f'Missing adapter: {adapter}')
                command += ['--adapter', str(adapter)]
            print(f'Starting {dataset}/{run}', flush=True)
            output.mkdir(parents=True, exist_ok=True)
            with (output.parent / f'{run}.log').open('w', encoding='utf-8') as log:
                result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
            if result.returncode:
                raise RuntimeError(f'{dataset}/{run} failed; see {output.parent / (run + ".log")}')
            done.append(output)
        subprocess.run([sys.executable, str(workflow / 'score_faithfulness.py'), *map(str, done),
                        '--json', str(args.output / f'{dataset}_{args.limit}' / 'faithfulness.json')],
                       check=True)


if __name__ == '__main__':
    main()
