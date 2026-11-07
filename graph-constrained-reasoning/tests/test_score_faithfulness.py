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
    labels = module.score_candidate(*via_marriage, ['Pat Nixon'], parses, {}, {})
    assert labels == {'grounded': True, 'hit': True, 'faithful': True,
                      'faithful_strict': True, 'shortcut': False}
    # relations must come from a single parse
    assert module.score_candidate(*via_child, ['Pat Nixon'], parses, {}, {})['faithful'] is False
    assert module.score_candidate(*ungrounded, ['Pat Nixon'], parses, {}, {})['faithful'] is False


def test_inverse_names_merge_and_type_shortcut_is_rejected():
    """FINDINGS S: the two flaws the corrected criterion fixes."""
    # SPARQL names film.film.directed_by, the subgraph edge carries the inverse
    parses = [{'film.film.directed_by'}]
    forward = candidate('Kubrick -> film.director.film -> 2001', '2001')
    canon = {'film.director.film': 'film.film.directed_by'}  # same inverse class
    assert module.score_candidate(*forward, ['2001'], parses, {}, {})['faithful'] is False
    assert module.score_candidate(*forward, ['2001'], parses, canon, {})['faithful_strict'] is True
    # walking a type relation backwards from a class node enumerates instances
    enum = candidate('Country -> common.topic.notable_types -> Guatemala', 'Guatemala')
    parses = [{'common.topic.notable_types'}]
    step = ('Country', 'common.topic.notable_types', 'Guatemala')
    assert module.score_candidate(*enum, ['Guatemala'], parses, {}, {})['faithful_strict'] is True
    assert module.score_candidate(*enum, ['Guatemala'], parses, {}, {step})['faithful_strict'] is False


def test_missing_criterion_file_is_an_error():
    """A silently missing criterion would fall back to the flawed labels."""
    import pytest
    with pytest.raises(FileNotFoundError):
        module.load_criterion(Path(tempfile.mkdtemp()) / 'absent.json')
    assert module.load_criterion('') == ({}, {})


def test_question_counts_unfaithful_hit():
    texts, audits = zip(candidate('A -> r.x.y -> B', 'B'), candidate('A -> s.x.y -> C', 'C'))
    row = dict(id='q1', question='q', prediction=list(texts), path_audit=list(audits), ground_truth=['B'])
    path = Path(tempfile.mkdtemp()) / 'predictions.jsonl'
    path.write_text(json.dumps(row) + '\n', encoding='utf-8')
    result = module.score_run(path, {'q1': [{'s.x.y'}]}, {}, {})
    assert result['question']['hit'] == 1 and result['question']['unfaithful_hit'] == 1
    assert result['candidate']['faithful'] == 0.5


def test_mcnemar_pairs_by_question_id():
    base = [{'id': f'q{i}', 'hit': i < 2} for i in range(10)]
    other = [{'id': f'q{i}', 'hit': i >= 1} for i in reversed(range(10))]
    gained, lost, p = module.mcnemar(base, other, 'hit')
    assert (gained, lost) == (8, 1)
    assert abs(p - 2 * 10 / 2 ** 9) < 1e-12
    assert module.mcnemar(base, base, 'hit') == (0, 0, 1.0)


def test_seed_test_resamples_whole_seeds():
    # 10 seeds of 5 questions each, all gained: one sign per seed, so p is 2 / 2 ** 10 up to sampling
    diffs = {f'WebQTest-{s}_{i}': 1 for s in range(10) for i in range(5)}
    m, lo, hi, p = module.seed_test(diffs)
    assert (m, lo, hi) == (1, 1, 1)
    assert p < 0.01
    # the same 50 gains spread over 50 singleton seeds give a much smaller p
    assert module.seed_test({f'WebQTest-{i}': 1 for i in range(50)})[3] < p
    m, lo, hi, p = module.seed_test({f'WebQTest-{s}_{i}': (1 if s % 2 else -1) for s in range(10) for i in range(5)})
    assert m == 0 and lo < 0 < hi and p == 1
