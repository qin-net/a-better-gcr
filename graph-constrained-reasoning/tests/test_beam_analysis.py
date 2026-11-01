import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "analyze_beams", Path(__file__).resolve().parents[1] / "workflow" / "analyze_beams.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_oracle_only_counts_existing_valid_candidates():
    rows = [
        {"prediction": ["# Answer:\nWrong", "# Answer:\nGold"], "ground_truth": ["Gold"],
         "path_audit": [{"valid": True, "endpoint": "Wrong"}, {"valid": True, "endpoint": "Gold"}]},
        {"prediction": ["# Answer:\nGold"], "ground_truth": ["Gold"],
         "path_audit": [{"valid": False, "endpoint": "Gold"}]},
    ]
    counts = module.analyze(rows)["counts"]
    assert counts["top1_answer_hit"] == 1
    assert counts["any_beam_answer_hit"] == 2
    assert counts["top1_gold_endpoint"] == 0
    assert counts["any_beam_gold_endpoint"] == 1
    assert counts["gold_endpoint_recoverable_by_reranking"] == 1


def test_endpoint_requires_normalized_exact_match():
    row = {"prediction": "# Answer:\nNew York City", "ground_truth": ["New York"],
           "path_audit": [{"valid": True, "endpoint": "New York City"}]}
    counts = module.analyze([row])["counts"]
    assert counts["top1_answer_hit"] == 1  # Official substring matching.
    assert counts["top1_gold_endpoint"] == 0
