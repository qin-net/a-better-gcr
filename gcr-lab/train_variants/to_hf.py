"""Convert a packed variant into the `load_from_disk` dataset the official trainer reads.

Usage (on the GPU machine, repo root):
  python gcr-lab/train_variants/to_hf.py C   # -> gcr-lab/train_variants/hf/C
"""
import gzip
import json
import os
import sys

from datasets import Dataset

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    for v in sys.argv[1:] or "ABCDE":
        rows = [json.loads(line) for line in
                gzip.open(os.path.join(HERE, "data", f"{v}.jsonl.gz"), "rt", encoding="utf-8")]
        dest = os.path.join(HERE, "hf", v)
        Dataset.from_list(rows).save_to_disk(dest)
        print(f"{v}: {len(rows)} questions -> {dest}")


if __name__ == "__main__":
    main()
