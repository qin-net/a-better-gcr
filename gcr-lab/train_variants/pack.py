"""Cap paths per question and pack A–E for the GPU machine.

The multi-relation graph expands every relation combination into its own path,
so B has 3.5x the paths of A. The official `n_path_per_sample` (default 10) is
declared but never applied, so this caps every variant to at most --cap paths
per question, sampled with a per-question seed, to keep training sizes
comparable. Output is gzip JSON lines with the official columns, small enough
to commit; `to_hf.py` turns it into a `load_from_disk` dataset.

Usage:
  python -I train_variants/pack.py            # -> train_variants/data/<V>.jsonl.gz
"""
import argparse
import gzip
import json
import os
import random

HERE = os.path.dirname(__file__)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(HERE, "..", "out", "train_variants"))
    ap.add_argument("--dst", default=os.path.join(HERE, "data"))
    ap.add_argument("--cap", type=int, default=10)
    args = ap.parse_args()

    os.makedirs(args.dst, exist_ok=True)
    for v in "ABCDE":
        questions = paths = 0
        with gzip.open(os.path.join(args.dst, f"{v}.jsonl.gz"), "wt", encoding="utf-8") as out:
            for ds in ("webqsp", "cwq"):
                for line in open(os.path.join(args.src, v, f"{ds}.jsonl")):
                    r = json.loads(line)
                    ps = r["ground_truth_paths"]
                    if not ps:
                        continue
                    if len(ps) > args.cap:
                        ps = random.Random(r["id"]).sample(ps, args.cap)
                    r["ground_truth_paths"] = ps
                    questions += 1
                    paths += len(ps)
                    out.write(json.dumps(r, ensure_ascii=False) + "\n")
        size = os.path.getsize(os.path.join(args.dst, f"{v}.jsonl.gz")) / 2**20
        print(f"{v}: {questions} questions, {paths} paths, {size:.1f} MB")


if __name__ == "__main__":
    main()
