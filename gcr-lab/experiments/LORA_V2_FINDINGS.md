# LoRA v2：继续训练与约束入口诊断

2026-11-02。在 v1 adapter 上继续训练两轮，使用新优化器，按完整 validation split 的 loss 选择 checkpoint；测试集未参与选权重或调整训练参数。

## 训练

- 仍使用固定版本的官方 GCR-Qwen2-0.5B 与 WebQSP 数据，q/v LoRA r=8，540,672 个可训练参数。
- 训练集 2,708 条确定性最短非空路径；完整验证集 246 题中 234 条可用路径，12 题没有非空路径。只监督助手输出。
- 学习率降为 1e-5，batch=2，梯度累积=2，bf16，seed=42，最大长度 512。初始化为 v1 权重，不恢复 v1 的 optimizer/scheduler。
- 实际完成 2.0 epoch、1,354 次更新，避免 v1 梯度累积尾组不足的问题；耗时 301.96 秒。
- 完整验证集 loss：训练前 0.335255，epoch 1 为 0.333682，epoch 2 为 0.333251。按验证 loss 选中 epoch 2（checkpoint-1354），重新加载后验证 loss 一致。
- 最终 adapter 数值均为有限值，且相较 v1 确有变化。最终权重、SHA256、初始化 adapter SHA256、样本 ID 和日志见 [training_manifest.json](../../graph-constrained-reasoning/training_runs/webqsp_lora_v2/training_manifest.json) 与 [adapter](../../graph-constrained-reasoning/training_runs/webqsp_lora_v2/adapter/)。本机中间 checkpoint 不提交。

## 固定前 100 道测试题，原解码设置

保存后重新加载 adapter，fp16 / SDPA / beam=2 / 2 跳，没有启用新增的路径预填选项。

| 指标 | 原模型 | v1 | v2 |
|---|---:|---:|---:|
| 官方 Hit | 63% | 66% | 70% |
| 官方 F1 | 37.71% | 40.87% | 43.83% |
| 首位答案 Hit | 60% | 59% | 61% |
| 首位 gold 终点 | 58% | 56% | 58% |
| 任一候选 gold 终点 | 61% | 65% | 68% |
| 路径核对通过 | 200/200 | 199/200 | 199/200 |

v2 推理计时约 152.96 秒，100 题全部完成，没有静默漏题；保留了全部原始输出，未剔除非法路径美化指标。官方 Hit 使用字符串子串匹配；仅答案段 Hit 也是 70%，答案去重后的 F1 为 43.82%。

原始文件：[manifest](cuda_results/webqsp_100_lora_v2/manifest.json)、[预测与 token 追踪](cuda_results/webqsp_100_lora_v2/predictions.jsonl)、[评测](cuda_results/webqsp_100_lora_v2/eval_result.txt)、[候选分析](cuda_results/webqsp_100_lora_v2/candidate_analysis.json)。单个 seed、固定 100 题不能证明全量收益或统计显著性。v2 继续作为实验权重，不宣称恢复无条件零幻觉保证。

## 已复现并定位的约束失败

v1 的 WebQTest-73，第二条候选原始输出实际是：

```text
# Reasoning Path:
</PATH>Maasai people -> people.ethnicity.languages_spoken -> English Language</PATH>
```

开头生成的是结束标记 `</PATH>`，没有生成 `<PATH>`。现有 callback 只在遇到开始标记后启用约束，因此整条候选没有进入 trie。该题整次 beam 搜索空前缀回退计数为 0，所以本例不是空前缀回退导致的逃逸。v2 同题仍产生这条非法边，100 题的全部搜索也都没有空前缀回退。

证据：[v1 单题原始 token 追踪](cuda_results/webqsp_73_v1_trace/predictions.jsonl)。`--record-token-trace` 只增加记录，不改变生成规则。

新增默认关闭的 `--prefill-path`：在 assistant 提示中显式预填路径标题和 `<PATH>`，从第一个路径 token 进入 trie。对同一 v1 失败题单独验证后，2/2 候选路径都可核对，回退计数仍为 0；第二条改为经 Maasai Language 到 Kenya 的合法两跳路径，但答案依然可能与问题不符。这证明本例入口修复有效，不等于证明所有题都安全或答案正确。

证据：[预填对照](cuda_results/webqsp_73_v1_prefill/predictions.jsonl)。预填改变了生成条件，其单题结果不混入上表。该选项没有移除原有空前缀回退机制，后续仍需完整验证集审计。

## 接续

优先在验证集全面核对路径预填，再扩大 beam=10。当前 v2 同批候选的 gold 终点 oracle 与首位候选间有 10 题差距，适合接原设计的 R1 排序；五个结构特征的轻量排序权重不一定需要显卡，候选生成及后续神经模型训练仍需要显卡。不能只靠增加 epoch 解决约束入口错误。

运行命令见 [CUDA_RUNBOOK.md](../../graph-constrained-reasoning/CUDA_RUNBOOK.md)，9 项自动测试通过。
