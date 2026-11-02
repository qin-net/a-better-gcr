import gzip
import importlib.util
import json
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location('train_cuda_lora', Path(__file__).resolve().parents[1] / 'workflow/train_cuda_lora.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write(rows):
    path = Path(tempfile.mkdtemp()) / 'V.jsonl.gz'
    with gzip.open(path, 'wt', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row) + '\n')
    return path


def test_validation_seed_questions_are_dropped():
    path = write([
        dict(id='WebQTrn-1', question='q', q_entity=['a'], a_entity=['b'],
             ground_truth_paths=[[['a', 'r', 'b']]]),
        dict(id='WebQTrn-2_0f3a', question='q', q_entity=['a'], a_entity=['c'],
             ground_truth_paths=[[['a', 'r', 'x'], ['x', 's', 'c']]]),
        dict(id='WebQTrn-3_9b1c', question='q', q_entity=['a'], a_entity=['d'],
             ground_truth_paths=[[['a', 'r', 'd']]]),
    ])
    rows, dropped = module.read_packed(path, {'WebQTrn-2'})
    assert dropped == 1
    assert [row['id'] for row in rows] == ['WebQTrn-1', 'WebQTrn-3_9b1c']


def test_paths_become_triple_tuples():
    path = write([dict(id='WebQTrn-1', question='q', q_entity=['a'], a_entity=['c'],
                       ground_truth_paths=[[['a', 'r', 'x'], ['x', 's', 'c']]])])
    rows, _ = module.read_packed(path)
    assert rows[0]['paths'] == [[('a', 'r', 'x'), ('x', 's', 'c')]]
    assert module.path_to_string(rows[0]['paths'][0]) == 'a -> r -> x -> s -> c'
