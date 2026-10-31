"""Load RoG subgraph datasets from the parquet mirror.

Each row: question, answer, q_entity, a_entity, graph (list of [h, r, t]).
Usage:  python -I experiments/rog_io.py data/hf/train.parquet --stats
"""

import argparse
import json
import sys

import pyarrow.parquet as pq


def iter_rows(path):
    pf = pq.ParquetFile(path)
    for batch in pf.iter_batches(batch_size=512):
        cols = batch.to_pydict()
        n = len(cols["question"])
        for i in range(n):
            yield {
                "id": cols["id"][i] if "id" in cols else None,
                "question": cols["question"][i],
                "answer": cols["answer"][i] or [],
                "q_entity": cols["q_entity"][i] or [],
                "a_entity": cols["a_entity"][i] or [],
                "graph": cols["graph"][i] or [],
            }


def triples(path):
    """Yield every (h, r, t) tuple in every subgraph."""
    for row in iter_rows(path):
        for h, r, t in row["graph"]:
            yield (h, r, t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    rows = 0
    edges = 0
    questions = []
    for row in iter_rows(args.path):
        rows += 1
        edges += len(row["graph"])
        if args.limit and rows >= args.limit:
            break
        if args.stats and rows <= 2:
            questions.append(row)
    print(json.dumps({
        "rows": rows,
        "edges": edges,
        "sample_question": questions[0]["question"] if questions else None,
        "sample_graph_size": len(questions[0]["graph"]) if questions else None,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
