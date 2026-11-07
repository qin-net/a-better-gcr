import importlib.util
import sys
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / 'workflow'
sys.path.insert(0, str(WORKFLOW))
spec = importlib.util.spec_from_file_location('run_full_seeds', WORKFLOW / 'run_full_seeds.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_every_run_has_a_trained_adapter():
    for seed, pair in module.PAIRS.items():
        for name in pair:
            assert (module.ADAPTERS[name] / 'adapter' / 'adapter_model.safetensors').exists(), name


def test_stages_cover_three_seeds_per_dataset():
    seeds = {s['dataset']: set(s['seeds']) for s in module.STAGES}
    # WebQSP seed 42 ran in v2 stage 4
    assert seeds == {'webqsp': {43, 44}, 'cwq': {42, 43, 44}}
    assert {s['dataset']: s['limit'] for s in module.STAGES} == {'webqsp': 1628, 'cwq': 3531}
