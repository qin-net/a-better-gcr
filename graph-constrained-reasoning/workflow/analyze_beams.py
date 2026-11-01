"""Measure R1 reranking headroom in saved beams; never fit on test labels."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.utils.qa_utils import normalize, eval_hit


def analyze(rows):
    counts = dict(samples=0, top1_answer_hit=0, any_beam_answer_hit=0,
                  top1_gold_endpoint=0, any_beam_gold_endpoint=0,
                  gold_endpoint_recoverable_by_reranking=0)
    for row in rows:
        counts["samples"] += 1
        predictions = row["prediction"]
        if isinstance(predictions, str):
            predictions = [predictions]
        answers = [text.split("# Answer:", 1)[1].strip() if "# Answer:" in text else ""
                   for text in predictions]
        gold = {normalize(answer) for answer in row["ground_truth"]}
        endpoints = [audit.get("valid", False) and normalize(audit.get("endpoint", "")) in gold
                     for audit in row["path_audit"]]
        first = bool(endpoints and endpoints[0])
        available = any(endpoints)
        counts["top1_answer_hit"] += bool(answers and eval_hit(answers[0], row["ground_truth"]))
        counts["any_beam_answer_hit"] += any(eval_hit(a, row["ground_truth"]) for a in answers)
        counts["top1_gold_endpoint"] += first
        counts["any_beam_gold_endpoint"] += available
        counts["gold_endpoint_recoverable_by_reranking"] += available and not first
    if not counts["samples"]:
        raise ValueError("No predictions to analyze")
    return {"counts": counts,
            "rates": {k: v / counts["samples"] for k, v in counts.items() if k != "samples"},
            "note": "Gold-endpoint oracle is an evaluation upper bound, not a learned ranker or semantic path-quality label."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_directory", type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in
            (args.result_directory / "predictions.jsonl").read_text(encoding="utf-8").splitlines()]
    result = analyze(rows)
    output = json.dumps(result, indent=2)
    (args.result_directory / "candidate_analysis.json").write_text(output, encoding="utf-8")
    print(output)
