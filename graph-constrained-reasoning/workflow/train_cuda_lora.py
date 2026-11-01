"""Single-GPU continuation training; one deterministic shortest path per question."""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import torch
from datasets import Dataset, load_dataset
from huggingface_hub import HfApi, hf_hub_download
from peft import LoraConfig, get_peft_model
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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--epochs', type=float, default=1)
    p.add_argument('--max-length', type=int, default=512)
    p.add_argument('--validation-limit', type=int, default=100)
    args = p.parse_args()
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError('A CUDA GPU with bf16 support is required')
    if args.epochs <= 0 or args.validation_limit < 1:
        p.error('epochs and validation-limit must be positive')
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        raise FileExistsError('Use a fresh output directory')
    set_seed(42)
    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=MODEL_REV)
    files = HfApi().list_repo_files(DATA, repo_type='dataset', revision=DATA_REV)
    stats, ids = {}, {}
    def prepare(split, limit=None):
        paths = [hf_hub_download(DATA, f, repo_type='dataset', revision=DATA_REV)
                 for f in sorted(files) if f.startswith('data/' + split + '-') and f.endswith('.parquet')]
        raw = load_dataset('parquet', data_files={split: paths}, split=split)
        if limit:
            raw = raw.select(range(min(limit, len(raw))))
        rows, selected = [], []
        skipped = dict(no_path=0, too_long=0)
        for sample in raw:
            paths = get_truth_paths(sample['q_entity'], sample['a_entity'], build_graph(sample['graph']))
            paths = sorted((path for path in paths if path), key=lambda path: (len(path), path_to_string(path)))
            if not paths:
                skipped['no_path'] += 1
                continue
            path = paths[0]
            question = sample['question'].rstrip('?') + '?'
            prompt = PathGenerationWithAnswerPromptBuilder.ZERO_SHOT_PROMPT.format(
                question=question, entities=','.join(sample['q_entity']))
            response = '# Reasoning Path:\n<PATH>' + path_to_string(path) + '</PATH>\n# Answer:\n' + path[-1][-1].strip()
            row = encode_pair(tokenizer, prompt, response, args.max_length)
            if row is None:
                skipped['too_long'] += 1
                continue
            rows.append(row)
            selected.append(sample['id'])
        stats[split] = dict(input_questions=len(raw), training_sequences=len(rows), skipped=skipped)
        ids[split] = selected
        if not rows:
            raise ValueError('No usable samples for ' + split)
        return Dataset.from_list(rows)
    train = prepare('train')
    validation = prepare('validation', args.validation_limit)
    assert not set(ids['train']) & set(ids['validation'])
    model = AutoModelForCausalLM.from_pretrained(MODEL, revision=MODEL_REV,
                torch_dtype=torch.bfloat16, attn_implementation='sdpa').cuda()
    model = get_peft_model(model, LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05,
                target_modules=['q_proj', 'v_proj'], bias='none', task_type='CAUSAL_LM'))
    model.config.use_cache = False
    def collate(rows):
        width = max(len(row['input_ids']) for row in rows)
        return {key: torch.tensor([row[key] + [pad] * (width - len(row[key])) for row in rows])
                for key, pad in [('input_ids', tokenizer.pad_token_id), ('attention_mask', 0), ('labels', -100)]}
    cfg = TrainingArguments(output_dir=str(args.output / 'trainer'), num_train_epochs=args.epochs,
                per_device_train_batch_size=2, per_device_eval_batch_size=2,
                gradient_accumulation_steps=8, learning_rate=2e-5, warmup_ratio=0.03,
                lr_scheduler_type='cosine', bf16=True, report_to='none', save_strategy='no',
                logging_steps=10, dataloader_num_workers=0, seed=42, disable_tqdm=True)
    trainer = Trainer(model=model, args=cfg, train_dataset=train, eval_dataset=validation, data_collator=collate)
    manifest = dict(status='running', model=MODEL, model_revision=MODEL_REV, dataset_revision=DATA_REV,
                    preprocessing=dict(max_length=args.max_length, validation_limit=args.validation_limit,
                                       path_policy='one_shortest_nonempty_path_per_question'),
                    data=stats, sample_ids=ids, training_args=cfg.to_dict(),
                    trainable_parameters=sum(p.numel() for p in model.parameters() if p.requires_grad),
                    gpu=torch.cuda.get_device_name(), torch=torch.__version__)
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
