"""Gold relation sets for scoring path faithfulness, small enough to commit.

For every question, the set of Freebase relations each annotated SPARQL uses. A decoded path is faithful when all of its
relations fall inside one of these sets; see
graph-constrained-reasoning/workflow/score_faithfulness.py.

  WebQSP: original release (WebQSP.{train,test}.json), one set per parse;
          train ids cover the RoG-webqsp validation split
  CWQ:    drt/complex_web_questions parquet, one SPARQL per question

Output: gcr-lab/eval/gold_relations.jsonl.gz, {"id", "dataset", "parses"}

Usage:
  python -I experiments/build_gold_relations.py \
      --webqsp data/webqsp_raw/WebQSP/data/WebQSP.{train,test}.json \
      --cwq data/hf/cwq_sparql_{validation,test}.parquet
"""

import argparse
import gzip
import json
import os
import re

import pyarrow.parquet as pq

# Unlike n_constrained_paths.PRED_RE, keep relations with more than three
# segments (base.aareas.schema.administrative_area.capital) whole.
PRED_RE = re.compile(r"ns:([a-z_0-9]+(?:\.[a-z_0-9]+){2,})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--webqsp", nargs="+", required=True)
    ap.add_argument("--cwq", nargs="+", required=True)
    args = ap.parse_args()

    rows = []
    for path in args.webqsp:
        for q in json.load(open(path))["Questions"]:
            parses = [sorted(set(PRED_RE.findall(p["Sparql"] or ""))) for p in q["Parses"]]
            rows.append({"id": q["QuestionId"], "dataset": "webqsp", "parses": parses})
    for path in args.cwq:
        t = pq.read_table(path, columns=["ID", "sparql"]).to_pydict()
        for i, s in zip(t["ID"], t["sparql"]):
            rows.append({"id": i, "dataset": "cwq", "parses": [sorted(set(PRED_RE.findall(s or "")))]})

    dest = os.path.join(os.path.dirname(__file__), "..", "eval", "gold_relations.jsonl.gz")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with gzip.open(dest, "wt", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    empty = sum(not any(p) for p in (r["parses"] for r in rows))
    print(f"{len(rows)} questions ({empty} without relations) -> {os.path.relpath(dest)}")


if __name__ == "__main__":
    main()
