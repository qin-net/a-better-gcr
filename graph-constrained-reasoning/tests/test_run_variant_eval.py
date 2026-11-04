import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / 'workflow'
sys.path.insert(0, str(WORKFLOW))
spec = importlib.util.spec_from_file_location('run_variant_eval', WORKFLOW / 'run_variant_eval.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

ROW = dict(id='WebQTest-0', question='q', ground_truth=['Jamaican English'],
           prediction=['# Reasoning Path:\nJamaica -> location.country.languages_spoken -> Jamaican English\n'
                       '# Answer:\nJamaican English'],
           path_audit=[dict(valid=True, reason='grounded', missing_edges=[], endpoint='Jamaican English',
                            path='Jamaica -> location.country.languages_spoken -> Jamaican English')])


def fake_pilot():
    pilot = Path(tempfile.mkdtemp()) / 'pilot'
    for variant in 'ABCDE':
        (pilot / variant / 'adapter').mkdir(parents=True)
        (pilot / variant / 'adapter' / 'adapter_model.safetensors').write_bytes(b'')
    return pilot


def fake_run(fail):
    def run(command, **kwargs):
        output = Path(command[command.index('--output') + 1])
        if output.name in fail:
            (output / 'manifest.json').write_text('{"status": "running"}')
            return subprocess.CompletedProcess(command, 1)
        (output / 'predictions.jsonl').write_text(json.dumps(ROW) + '\n')
        (output / 'manifest.json').write_text('{"status": "complete"}')
        return subprocess.CompletedProcess(command, 0)
    return run


def test_keep_going_archives_failure_and_scores_the_rest(monkeypatch):
    pilot = fake_pilot()
    output = pilot.parent / 'results'
    monkeypatch.setattr(module.subprocess, 'run', fake_run({'B'}))
    scores, failures = module.evaluate(pilot, output, ['webqsp'], 1, ['official', 'A', 'B'],
                                       keep_going=True, on_event=lambda m: None)
    assert [f['run'] for f in failures] == ['B']
    assert (output / 'webqsp_1' / 'B_failed').is_dir() and (output / 'webqsp_1' / 'B_failed.log').exists()
    assert [Path(r['run']).name for r in scores['webqsp']] == ['official', 'A']
    assert scores['webqsp'][0]['question']['faithful_hit'] == 1

    # Rerunning retries only the failed run and scores everything.
    monkeypatch.setattr(module.subprocess, 'run', fake_run(set()))
    events = []
    scores, failures = module.evaluate(pilot, output, ['webqsp'], 1, ['official', 'A', 'B'],
                                       keep_going=True, on_event=events.append)
    assert not failures and sum(e.startswith('Starting') for e in events) == 1
    assert [Path(r['run']).name for r in scores['webqsp']] == ['official', 'A', 'B']
