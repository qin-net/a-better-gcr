"""Reproducible, single-GPU evaluation using the original GCR pipeline."""
import argparse
import json
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch
import transformers
from datasets import load_dataset
from huggingface_hub import HfApi, hf_hub_download
from transformers import set_seed

from src.llms.graph_constrained_decoding_model import GraphConstrainedDecodingModel
from src.qa_prompt_builder import PathGenerationWithAnswerPromptBuilder
from src.utils.qa_utils import eval_path_result_w_ans, eval_f1, eval_hit
from src.path_audit import audit_prediction
from workflow.predict_paths_and_answers import prediction


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    GraphConstrainedDecodingModel.add_args(parser)
    parser.set_defaults(model_path="rmanluo/GCR-Qwen2-0.5B-Instruct", dtype="fp16",
                        attn_implementation="sdpa", generation_mode="beam", k=2,
                        max_new_tokens=1024)
    parser.add_argument("--dataset", default="rmanluo/RoG-webqsp")
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--record-token-trace", action="store_true")
    parser.add_argument("--prefill-path", action="store_true", help="Prefill the path header and opening marker")
    parser.add_argument("--model-revision", default="ec16a9e8c15e5792629e9405a42cea1562076b4e")
    parser.add_argument("--dataset-revision", default="c0632533135a06f8c5d536b420deec5fcb5c58f3")
    parser.add_argument("--split", default="test", choices=["test", "validation"])
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=20, help="0 evaluates the entire split")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--hops", type=int, default=2)
    parser.add_argument("--graph", default="directed", choices=["directed", "undirected", "multi"],
                        help="directed/undirected: official build_graph (one relation per pair); "
                             "multi: keep every relation, traversable in reverse")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.start < 0 or args.limit < 0 or args.k < 1 or args.hops < 1:
        parser.error("start/limit must be nonnegative; k/hops must be positive")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required; install the CUDA PyTorch wheel first")
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        raise FileExistsError(f"Use a fresh output directory: {args.output}")
    set_seed(args.seed)
    api = HfApi()
    # A local directory is a model trained here (e.g. gcr-lab/train_variants/runs/C).
    local_model = Path(args.model_path).is_dir()
    model_revision = (f"local:{Path(args.model_path).resolve()}" if local_model
                      else api.model_info(args.model_path, revision=args.model_revision).sha)
    data_revision = api.dataset_info(args.dataset, revision=args.dataset_revision).sha
    # Resolve raw parquet files, avoiding remote dataset scripts and truncated mirrors.
    files = sorted(f for f in api.list_repo_files(args.dataset, repo_type="dataset",
                                                  revision=data_revision)
                   if f.startswith(f"data/{args.split}-") and f.endswith(".parquet"))
    if not files:
        raise RuntimeError("No raw parquet files found for the requested split")
    local_files = [hf_hub_download(args.dataset, f, repo_type="dataset", revision=data_revision)
                   for f in files]
    dataset = load_dataset("parquet", data_files={args.split: local_files}, split=args.split)
    end = min(len(dataset), args.start + args.limit) if args.limit else len(dataset)
    dataset = dataset.select(range(args.start, end))
    if not len(dataset):
        raise ValueError("Selected dataset is empty")
    manifest = {
        "args": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
        "model_revision": model_revision, "dataset_revision": data_revision,
        "dataset_files": files, "torch": torch.__version__,
        "transformers": transformers.__version__, "cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(), "python": platform.python_version(),
        "requested_count": len(dataset), "stage": "graph_constrained_decoding_only",
        "status": "running",
    }
    def save_manifest():
        (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    save_manifest()
    # Load exactly the resolved revision, including the tokenizer and generation config.
    if not local_model:
        from huggingface_hub import snapshot_download
        args.model_path = snapshot_download(args.model_path, revision=model_revision,
                                           ignore_patterns=["training_args.bin", "*.md"])
    model = GraphConstrainedDecodingModel(args)
    model.prepare_for_inference()
    if args.adapter:
        from peft import PeftModel
        model.model = PeftModel.from_pretrained(model.model, str(args.adapter)).merge_and_unload()
        model.model.eval()
    if model.model.device.type != "cuda":
        raise RuntimeError("Model did not load on CUDA")
    if args.graph == "multi":
        from src import multi_relation_graph
        multi_relation_graph.install(reverse=True)
    builder = PathGenerationWithAnswerPromptBuilder(model.tokenizer, "zero-shot",
                                                    undirected=args.graph == "undirected",
                                                    index_path_length=args.hops)
    manifest["generation_config"] = model.generation_cfg.to_dict()
    save_manifest()
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    started = time.perf_counter()
    failures = []
    audits = []
    answer_metrics = []
    with (args.output / "predictions.jsonl").open("w", encoding="utf-8") as out:
        for i, sample in enumerate(dataset):
            result = prediction(sample, [], builder, model)
            if result is not None and args.record_token_trace:
                result['generation_details'] = model.last_generation_details
            if result is None:
                # Keep failures in the metric denominator instead of silently dropping them.
                failures.append(sample["id"])
                result = {"id": sample["id"], "question": sample["question"],
                          "prediction": [""], "ground_truth": sample["answer"],
                          "ground_truth_paths": [], "error": "no_prediction"}
            elif isinstance(result["prediction"], str):
                result["prediction"] = [result["prediction"]]
            result["path_audit"] = [audit_prediction(text, sample["graph"],
                                                     sample["q_entity"], args.hops,
                                                     reverse=args.graph != "directed")
                                    for text in result["prediction"]]
            audits.extend(result["path_audit"])
            answers = list(dict.fromkeys(text.split("# Answer:", 1)[1].strip()
                                        for text in result["prediction"] if "# Answer:" in text))
            f1, precision, recall = eval_f1(answers, sample["answer"])
            answer_metrics.append({"hit": eval_hit(" ".join(answers), sample["answer"]),
                                   "f1": f1, "precision": precision, "recall": recall})
            out.write(json.dumps(result) + "\n")
            out.flush()
            print(f"{i + 1}/{len(dataset)} {sample['id']}", flush=True)
    torch.cuda.synchronize()
    manifest.update(status="failed" if failures else "complete",
                    elapsed_seconds=time.perf_counter() - started,
                    peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                    peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                    failures=failures, completed_count=len(dataset))
    manifest["path_audit"] = {"generated_candidates": len(audits),
                              "valid_candidates": sum(a["valid"] for a in audits)}
    manifest["answer_section_metrics"] = {
        key: sum(row[key] for row in answer_metrics) / len(answer_metrics)
        for key in ("hit", "f1", "precision", "recall")}
    eval_path_result_w_ans(str(args.output / "predictions.jsonl"))
    save_manifest()
    if failures:
        raise RuntimeError(f"{len(failures)} samples failed; see manifest.json")


if __name__ == "__main__":
    main()
