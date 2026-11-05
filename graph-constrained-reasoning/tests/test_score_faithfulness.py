import importlib.util
import json
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location('score_faithfulness', Path(__file__).resolve().parents[1] / 'workflow/score_faithfulness.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def candidate(path, answer, valid=True):
    return (f'# Reasoning Path:\n{path}\n# Answer:\n{answer}',
            {'valid': valid, 'reason': 'grounded' if valid else 'missing_edge', 'path': path})


def test_candidate_labels():
    parses = [{'people.person.spouse_s', 'people.marriage.spouse'}, {'people.person.children'}]
    via_marriage = candidate('Nixon -> people.person.spouse_s -> m.1 -> people.marriage.spouse -> Pat Nixon', 'Pat Nixon')
    via_child = candidate('Nixon -> people.person.children -> Tricia -> people.person.parents -> Pat Nixon', 'Pat Nixon')
    ungrounded = candidate('Nixon -> people.person.children -> Pat Nixon', 'Pat Nixon', valid=False)
    assert module.score_candidate(*via_marriage, ['Pat Nixon'], parses) == {'grounded': True, 'hit': True, 'faithful': True}
    # relations must come from a single parse
    assert module.score_candidate(*via_child, ['Pat Nixon'], parses)['faithful'] is False
    assert module.score_candidate(*ungrounded, ['Pat Nixon'], parses)['faithful'] is False


def test_question_counts_unfaithful_hit():
    texts, audits = zip(candidate('A -> r.x.y -> B', 'B'), candidate('A -> s.x.y -> C', 'C'))
    row = dict(id='q1', question='q', prediction=list(texts), path_audit=list(audits), ground_truth=['B'])
    path = Path(tempfile.mkdtemp()) / 'predictions.jsonl'
    path.write_text(json.dumps(row) + '\n', encoding='utf-8')
    result = module.score_run(path, {'q1': [{'s.x.y'}]})
    assert result['question']['hit'] == 1 and result['question']['unfaithful_hit'] == 1
    assert result['candidate']['faithful'] == 0.5


def test_mcnemar_pairs_by_question_id():
    base = [{'id': f'q{i}', 'hit': i < 2} for i in range(10)]
    other = [{'id': f'q{i}', 'hit': i >= 1} for i in reversed(range(10))]
    gained, lost, p = module.mcnemar(base, other, 'hit')
    assert (gained, lost) == (8, 1)
    assert abs(p - 2 * 10 / 2 ** 9) < 1e-12
    assert module.mcnemar(base, base, 'hit') == (0, 0, 1.0)
