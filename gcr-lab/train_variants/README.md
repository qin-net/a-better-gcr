# 训练侧修复：A–E 训练集

## 五组设置

| 组 | 训练路径 | 推理（`cuda_baseline.py`） | 题数 | 路径数（每题 ≤10） |
|---|---|---|---|---|
| A | 官方：有向图最短路 | `--graph directed --hops 2` | 24,650 | 89,137 |
| B | 多重图 + 反向边最短路 | `--graph multi --hops 2` | 24,651 | 162,599 |
| C | B，CWQ 只沿 SPARQL 关系 | `--graph multi --hops 2` | 24,651 | 84,116 |
| D | C + 图池修复 ≤2 跳（+832 题） | `--graph multi --hops 2` | 25,483 | 86,070 |
| E | C + 图池修复 ≤3 跳（+2,809 题） | `--graph multi --hops 3` | 27,460 | 92,247 |

题数为 CWQ + WebQSP 训练集中有路径的题。WebQSP 没有 SPARQL，B–E 的 WebQSP 部分相同。
多重图见 `graph-constrained-reasoning/src/multi_relation_graph.py` 与 `experiments/FINDINGS.md`
第 O 节：官方建图每对实体只留一个关系，关系约束的路径会有 36.7% 的题解码不出来，所以
B–E 训练和推理都换成多重图。

每组的对照意义：

- A → B：只换图。多重图不增加可达答案（FINDINGS O），预期无提升，用来排除“提升来自换图”。
- B → C：SPARQL 过滤假路径的贡献。
- C → D：图池修复的贡献，不改推理深度。
- D → E：加深到 3 跳是否值得（trie 会显著变大，见 FINDINGS K）。

每题路径数截到 10 条（按题目 id 固定随机种子抽样）。多重图把每种关系组合都展开成单独的
路径，不截断时 B 组路径数是 A 组的 3.5 倍；官方 `n_path_per_sample` 参数默认 10 但从未生效。
截断后 B 组仍比其他组多约 80% 路径，比较时要固定训练步数，或同时报告按 epoch 与按步数的结果。

## 在 GPU 电脑上跑（RTX 4060 8GB）

数据已打包在 `data/<V>.jsonl.gz`（共约 20MB，已入库），不需要在 GPU 电脑上重新生成。

```powershell
# 1. 训练依赖：在 CUDA_RUNBOOK 的推理环境上补装（trl 需与 transformers 4.44 匹配）
uv pip install --python .venv/Scripts/python.exe "trl==0.10.1"

# 2. 转成官方 load_from_disk 格式
.venv/Scripts/python.exe gcr-lab/train_variants/to_hf.py A B C D E

# 3. 训练一组（以 C 为例）。0.5B + LoRA，单卡；先用 --max_steps 200 试跑看显存与耗时
cd graph-constrained-reasoning
..\.venv\Scripts\python.exe workflow/finetune_kg_specialized_llm.py `
    --data_path_list ../gcr-lab/train_variants/hf/C `
    --model_name_or_path Qwen/Qwen2-0.5B-Instruct `
    --output_dir ../gcr-lab/train_variants/runs/C `
    --use_peft True --lora_r 8 --save_merged True `
    --bf16 True --num_train_epochs 1 `
    --per_device_train_batch_size 4 --gradient_accumulation_steps 4 `
    --learning_rate 2e-4 --lr_scheduler_type cosine --warmup_ratio 0.03 `
    --gradient_checkpointing True --save_strategy no --eval_strategy no `
    --logging_steps 10 --report_to none --attn_implementation sdpa `
    --response_template "<|im_start|>assistant" --max_seq_length 1024 `
    --dataloader_num_workers 0 --seed 42

# 4. 用合并后的模型评测（E 组改 --hops 3，A 组改 --graph directed）
cd ..
.venv/Scripts/python.exe graph-constrained-reasoning/workflow/cuda_baseline.py `
    --model_path gcr-lab/train_variants/runs/C/merged --graph multi --hops 2 `
    --limit 100 --output gcr-lab/experiments/cuda_results/train_C_webqsp_100
```

注意：

- 这五组都从**原始 Qwen2-0.5B-Instruct** 开始训练，不是在官方 GCR 权重上继续训。官方
  GCR-0.5B 的数字只作参考，不能和 A–E 直接比较；A 组才是可比基线。
- 官方训练会给分词器加 `<PATH>`、`</PATH>` 两个特殊 token 并扩展词表。官方 LoRA 只训练
  `q_proj, v_proj`，新 token 的嵌入会停留在随机初始化，所以我给 LoRA 加了
  `modules_to_save=["embed_tokens", "lm_head"]`（官方脚本默认是全参训练，不走这段）。
  Qwen2-0.5B 的嵌入与输出层共享权重，PEFT 可能对此给出警告，需要在 GPU 上确认。
- `--save_merged True` 会额外保存 `runs/<V>/merged/`：合并 LoRA、带扩展词表和分词器的完整
  模型，评测直接用它，不需要 `--adapter`。`cuda_baseline.py` 遇到本地目录时跳过 HF 版本解析，
  在 manifest 里记录本地路径。
- 先在 `--limit 100` 上把五组跑通，看出趋势后再跑全量测试集与 CWQ 测试集。
- 第 3、4 步都还没在 GPU 上跑过。

## 重新生成（CPU，约 11 分钟）

```bash
.venv/bin/python -I train_variants/build_variants.py --cwq data/hf/cwq_full/train-*.parquet \
    --webqsp data/hf/train.parquet --sparql data/hf/cwq_sparql_train.parquet \
    --repaired out/constrained_paths.jsonl
.venv/bin/python -I train_variants/pack.py
```

`build_variants.py` 写出未截断的 `out/train_variants/<V>/{cwq,webqsp}.jsonl`（约 300MB，不入库），
`pack.py` 截断并压缩到 `data/`。
