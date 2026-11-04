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
训练沿用已验证的 `train_cuda_lora.py`（LoRA v1/v2 那套：官方 GCR-0.5B 上继续训，r=8 q/v，
每题一条确定性最短路径），只把训练数据换成 `--train-data`：

```powershell
# 训练一组（以 C 为例）。超参与 LoRA v1 相同；A–C 约 16.1k 条序列，
# 4060 上 mb1 + 梯度检查点约 14 分钟 128 步，完整一个 epoch 约 1 小时 50 分
.venv/Scripts/python.exe -u graph-constrained-reasoning/workflow/train_cuda_lora.py `
    --train-data gcr-lab/train_variants/data/C.jsonl.gz `
    --output graph-constrained-reasoning/training_runs/variant_C
```

固定 128 步的五组先导对照见 [GPU_PILOT_PROTOCOL.md](GPU_PILOT_PROTOCOL.md)。评测五组 adapter：

```powershell
# 完整 1-epoch 的五组（ae_full），结果写到 gcr-lab/experiments/cuda_results/ae_full/
.venv/Scripts/python.exe -u graph-constrained-reasoning/workflow/run_variant_eval.py `
    --pilot graph-constrained-reasoning/training_runs/ae_full --limit 100
```

`--pilot` 换成 `training_runs/ae_pilot_128_mb1` 即评测 128 步先导。

对 WebQSP 和 CWQ 测试集前 100 题各跑 7 次 `cuda_baseline.py --prefill-path`：官方权重、A（有向图）、
A_multi（多重图，把“换图”与“换数据”分开）、B–E（多重图 2 跳）、E_hops3。E_hops3 的 trie 仍只
建在题目自带子图上，不含图池，所以它只检验解码深度，不代表图池修复已在推理中生效（FINDINGS K）。
已完成的组重启时跳过。最后用 `score_faithfulness.py` 写出 `faithfulness.json`：

- `hit` / `f1`：与 `cuda_baseline` manifest 的 answer_section_metrics 相同。
- `faithful`：路径落在子图上，且所有关系出现在该题某一个标注 SPARQL 中。标准关系来自
  `gcr-lab/eval/gold_relations.jsonl.gz`（`experiments/build_gold_relations.py` 由原始 WebQSP 与 CWQ
  SPARQL 生成，已入库）。
- `faithful_hit`：有一条路径既答对又忠实；`unfaithful_hit`：答对了，但只靠不忠实的路径。

已有结果（WebQSP 前 100 题，未 prefill）：

| 运行 | hit | f1 | faithful_hit | unfaithful_hit | 路径忠实率 |
|---|---|---|---|---|---|
| 官方 | 0.63 | 0.377 | 0.53 | 0.10 | 52.0% |
| LoRA v1 | 0.66 | 0.409 | 0.58 | 0.08 | 55.5% |
| LoRA v2 | 0.70 | 0.438 | 0.60 | 0.10 | 55.0% |

注意：

- **测试泄漏**：CWQ 每题由一道 WebQSP 题改写而来，id 前缀就是那道题的 id。CWQ 训练集里有
  7,082 题（`A`–`C`）的种子是 WebQSP **测试**题，覆盖 1,628 道测试题中的 815 道（前 100 题中
  48 道）。官方 GCR 训练混合了两者，所以官方权重本身已见过这些改写。`--train-data` 默认丢掉
  这些题以及种子在 validation 中的题，A–C 剩约 16.1k 条序列（丢 8,548 行），D 16.7k（丢 8,827），E 18.0k（丢 9,444）；
  `--keep-test-seeds` 恢复官方混法。论文里 WebQSP 数字应当用默认（丢弃）设置报告。
- 起点是官方 GCR-0.5B，它已在官方路径（≈ A 组）上训过，所以 A 组相当于“同分布再训一次”，
  是 B–E 的可比基线；不能拿 A–E 和官方原始权重的数字直接比较。
- 默认每题一条最短路径（与 v1/v2 一致）。`--paths-per-question N` 每题取前 N 条，但这样各组序列
  数不同，需固定步数比较。
- 在本机（CPU）用官方分词器编码了 A/C/E 各约 1k 题抽样：没有超过 512 token 的序列，中位长度
  约 135。GPU 上已跑过 128 步先导（`training_runs/ae_pilot_128_mb1`），完整 epoch 还没跑。

`finetune_kg_specialized_llm.py`（官方脚本，从原始 Qwen2-0.5B 起训）也能读这些数据
（`to_hf.py` 转成 `load_from_disk` 格式，LoRA 已加 `modules_to_save` 训练 PATH token 嵌入，
`--save_merged True` 导出合并模型供 `cuda_baseline.py --model_path` 评测），但在 4060 上没跑过，
作为复现官方完整训练的备选，不是主线。

## 重新生成（CPU，约 11 分钟）

```bash
.venv/bin/python -I train_variants/build_variants.py --cwq data/hf/cwq_full/train-*.parquet \
    --webqsp data/hf/train.parquet --sparql data/hf/cwq_sparql_train.parquet \
    --repaired out/constrained_paths.jsonl
.venv/bin/python -I train_variants/pack.py
```

`build_variants.py` 写出未截断的 `out/train_variants/<V>/{cwq,webqsp}.jsonl`（约 300MB，不入库），
`pack.py` 截断并压缩到 `data/`。
