import importlib.util
import sys
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / 'workflow'
sys.path.insert(0, str(WORKFLOW))
spec = importlib.util.spec_from_file_location('run_v2_night', WORKFLOW / 'run_v2_night.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_every_stage_trains_what_it_evaluates():
    for stage in module.STAGES:
        assert set(stage['train']) <= set(module.TRAIN)
        for _, adapter in stage['runs']:
            assert isinstance(adapter, Path) or adapter in module.TRAIN
            if not isinstance(adapter, Path) and stage['stage'] != 4:
                assert adapter in stage['train']


def test_training_sets_exist():
    for data, _ in module.TRAIN.values():
        assert (module.DATA / f'{data}.jsonl.gz').exists(), data
