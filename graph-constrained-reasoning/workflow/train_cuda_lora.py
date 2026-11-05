"""Single-GPU continuation training; one deterministic path per question (see order_paths)."""
import argparse
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import torch
from datasets import Dataset, load_dataset
from huggingface_hub import HfApi, hf_hub_download
from peft import LoraConfig, get_peft_model, PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments, set_seed
from src.utils.graph_utils import build_graph, get_truth_paths
from src.utils.utils import path_to_string
from src.qa_prompt_builder import PathGenerationWithAnswerPromptBuilder

MODEL = 'rmanluo/GCR-Qwen2-0.5B-Instruct'
MODEL_REV = 'ec16a9e8c15e5792629e9405a42cea1562076b4e'
DATA = 'rmanluo/RoG-webqsp'
DATA_REV = 'c0632533135a06f8c5d536b420deec5fcb5c58f3'


def encode_pair(tokenizer, prompt, response, max_length):
    chat = [{'role': 'user', 'content': prompt}]
    prefix = tokenizer.apply_chat_template(chat, tokenize=True, add_generation_prompt=True)
    tokens = tokenizer.apply_chat_template(chat + [{'role': 'assistant', 'content': response}],
                                           tokenize=True, add_generation_prompt=False)
    if tokens[:len(prefix)] != prefix:
        raise ValueError('Chat template does not preserve the assistant prefix')
    if len(tokens) > max_length:
        return None  # Never train on a truncated path/answer.
    return dict(input_ids=tokens, attention_mask=[1] * len(tokens),
                labels=[-100] * len(prefix) + tokens[len(prefix):])


def read_packed(path, exclude_seeds=()):
    """Rows of a packed training set (gcr-lab/train_variants/data/<V>.jsonl.gz).

    CWQ ids are `<WebQSP seed id>_<hash>`, and about half of the WebQSP test
    questions seed a CWQ training question. A row whose seed is in
    `exclude_seeds` (validation, and test unless asked otherwise) is dropped.
    Returns (rows, number dropped).
    """
    rows, dropped = [], 0
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        for line in f:
            row = json.loads(line)
            if row['id'].split('_', 1)[0] in exclude_seeds:
                dropped += 1
                continue
            row['paths'] = [[tuple(step) for step in p] for p in row.pop('ground_truth_paths')]
            rows.append(row)
    return rows, dropped


def order_paths(sample, paths):
    """Non-empty paths, the one to train on first.

    v2 packed sets (gcr-lab/train_variants/build_v2.py, path_order='ranked')
    store paths best first: SPARQL-faithful, then fewest reversed steps.
    Everything else falls back to shortest, then alphabetical — which on the
    multi-relation graph tends to pick reversed steps (FINDINGS.md section R).
    """
    paths = [path for path in paths if path]
    if sample.get('path_order') == 'ranked':
        return paths
    return sorted(paths, key=lambda path: (len(path), path_to_string(path)))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--epochs', type=float, default=1)
    p.add_argument('--max-steps', type=int, default=-1,
                   help='Positive value overrides epochs for equal-budget pilot comparisons')
    p.add_argument('--gradient-checkpointing', action='store_true')
    p.add_argument('--batch-size', type=int, default=2)
    p.add_argument('--max-length', type=int, default=512)
    p.add_argument('--validation-limit', type=int, default=100)
    p.add_argument('--adapter', type=Path, help='Continue saved adapter weights with a fresh optimizer')
    p.add_argument('--learning-rate', type=float, default=2e-5)
    p.add_argument('--gradient-accumulation', type=int, default=8)
    p.add_argument('--select-best', action='store_true', help='Select epoch checkpoint using validation loss only')
    p.add_argument('--train-data', type=Path,
                   help='Packed training set (gcr-lab/train_variants/data/<V>.jsonl.gz) instead of '
                        'shortest paths in the WebQSP train subgraphs')
    p.add_argument('--paths-per-question', type=int, default=1,
                   help='Training sequences per question, shortest paths first (default 1)')
    p.add_argument('--seed', type=int, default=42, help='LoRA init and data order seed')
    p.add_argument('--keep-test-seeds', action='store_true',
                   help='With --train-data, keep CWQ questions built from WebQSP test questions '
                        '(the official GCR mix); dropped by default')
    args = p.parse_args()
    if args.max_steps != -1 and args.max_steps < 1:
        p.error('max-steps must be -1 (epochs) or positive')
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError('A CUDA GPU with bf16 support is required')
    if (args.epochs <= 0 or args.validation_limit < 1 or args.max_length < 1
            or args.gradient_accumulation < 1 or args.batch_size < 1 or args.learning_rate <= 0 or args.paths_per_question < 1):
        p.error('epochs, lengths, learning-rate, gradient-accumulation and paths-per-question must be positive')
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        raise FileExistsError('Use a fresh output directory')
    set_seed(args.seed)
    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=MODEL_REV)
    files = HfApi().list_repo_files(DATA, repo_type='dataset', revision=DATA_REV)
    stats, ids = {}, {}
    def load(split, limit=None):
        paths = [hf_hub_download(DATA, f, repo_type='dataset', revision=DATA_REV)
                 for f in sorted(files) if f.startswith('data/' + split + '-') and f.endswith('.parquet')]
        raw = load_dataset('parquet', data_files={split: paths}, split=split)
        if limit:
            raw = raw.select(range(min(limit, len(raw))))
        return raw
    def prepare(split, samples, n_paths=1, extra=None):
        rows, selected = [], []
        skipped = dict(no_path=0, too_long=0)
        for sample in samples:
            if 'paths' in sample:
                paths = sample['paths']
            else:
                paths = get_truth_paths(sample['q_entity'], sample['a_entity'], build_graph(sample['graph']))
            paths = order_paths(sample, paths)
            if not paths:
                skipped['no_path'] += 1
                continue
            question = sample['question'].rstrip('?') + '?'
            prompt = PathGenerationWithAnswerPromptBuilder.ZERO_SHOT_PROMPT.format(
                question=question, entities=','.join(sample['q_entity']))
            kept = 0
            for path in paths[:n_paths]:
                response = '# Reasoning Path:\n<PATH>' + path_to_string(path) + '</PATH>\n# Answer:\n' + path[-1][-1].strip()
                row = encode_pair(tokenizer, prompt, response, args.max_length)
                if row is None:
                    skipped['too_long'] += 1
                    continue
                rows.append(row)
                kept += 1
            if kept:
                selected.append(sample['id'])
        stats[split] = dict(input_questions=len(samples), training_sequences=len(rows), skipped=skipped,
                            **(extra or {}))
        ids[split] = selected
        if not rows:
            raise ValueError('No usable samples for ' + split)
        return Dataset.from_list(rows)
    validation_raw = load('validation', args.validation_limit)
    if args.train_data:
        # Drop CWQ questions built from a validation (or test) seed question; keep
        # the WebQSP validation split as the shared yardstick across variants.
        seeds = set(load('validation')['id'])
        if not args.keep_test_seeds:
            seeds |= set(load('test')['id'])
        packed, dropped = read_packed(args.train_data, seeds)
        train = prepare('train', packed, args.paths_per_question,
                        dict(source=str(args.train_data), dropped_seed_overlap=dropped,
                             kept_test_seeds=args.keep_test_seeds,
                             sha256=hashlib.sha256(args.train_data.read_bytes()).hexdigest()))
    else:
        train = prepare('train', load('train'), args.paths_per_question)
    validation = prepare('validation', validation_raw)
    assert not set(ids['train']) & set(ids['validation'])
    model = AutoModelForCausalLM.from_pretrained(MODEL, revision=MODEL_REV,
                torch_dtype=torch.bfloat16, attn_implementation='sdpa').cuda()
    if args.adapter:
        model = PeftModel.from_pretrained(model, str(args.adapter), is_trainable=True)
    else:
        model = get_peft_model(model, LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05,
                    target_modules=['q_proj', 'v_proj'], bias='none', task_type='CAUSAL_LM'))
    model.config.use_cache = False
    def collate(rows):
        width = max(len(row['input_ids']) for row in rows)
        return {key: torch.tensor([row[key] + [pad] * (width - len(row[key])) for row in rows])
                for key, pad in [('input_ids', tokenizer.pad_token_id), ('attention_mask', 0), ('labels', -100)]}
    cfg = TrainingArguments(output_dir=str(args.output / 'trainer'), num_train_epochs=args.epochs,
                max_steps=args.max_steps,
                gradient_checkpointing=args.gradient_checkpointing,
                gradient_checkpointing_kwargs={'use_reentrant': False},
                per_device_train_batch_size=args.batch_size, per_device_eval_batch_size=1,
                gradient_accumulation_steps=args.gradient_accumulation, learning_rate=args.learning_rate, warmup_ratio=0.03,
                lr_scheduler_type='cosine', bf16=True, report_to='none', save_strategy='epoch' if args.select_best else 'no',
                logging_steps=50, dataloader_num_workers=0, seed=args.seed, disable_tqdm=True,
                eval_strategy='epoch' if args.select_best else 'no',
                load_best_model_at_end=args.select_best, metric_for_best_model='eval_loss',
                greater_is_better=False, save_total_limit=1)
    trainer = Trainer(model=model, args=cfg, train_dataset=train, eval_dataset=validation, data_collator=collate)
    manifest = dict(status='running', model=MODEL, model_revision=MODEL_REV, dataset_revision=DATA_REV,
                    preprocessing=dict(max_length=args.max_length, validation_limit=args.validation_limit,
                                       train_data=str(args.train_data) if args.train_data else None,
                                       path_policy='first_stored_path_if_ranked_else_shortest',
                                       paths_per_question=args.paths_per_question),
                    data=stats, sample_ids=ids, training_args=cfg.to_dict(),
                    trainable_parameters=sum(p.numel() for p in model.parameters() if p.requires_grad),
                    gpu=torch.cuda.get_device_name(), torch=torch.__version__)
    manifest['continuation_adapter'] = str(args.adapter) if args.adapter else None
    def save():
        (args.output / 'training_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    save()
    manifest['before'] = trainer.evaluate()
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    result = trainer.train()
    manifest['training_seconds'] = time.perf_counter() - started
    manifest['train_metrics'] = result.metrics
    manifest['after'] = trainer.evaluate()
    manifest['best_checkpoint'] = trainer.state.best_model_checkpoint
    manifest['best_validation_loss'] = trainer.state.best_metric
    manifest['peak_allocated_bytes'] = torch.cuda.max_memory_allocated()
    model.peft_config['default'].base_model_name_or_path = MODEL
    model.peft_config['default'].revision = MODEL_REV
    model.save_pretrained(args.output / 'adapter')
    manifest['log_history'] = trainer.state.log_history
    manifest['status'] = 'complete'
    save()
    print(json.dumps({k: manifest[k] for k in ['before', 'after', 'training_seconds']}, indent=2))


if __name__ == '__main__':
    main()
