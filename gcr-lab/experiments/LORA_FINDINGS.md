# WebQSP LoRA 继续训练 v1

后续已完成两轮继续训练并定位特殊 token 入口问题，见 [LoRA v2 实验记录](LORA_V2_FINDINGS.md)。

2026-11-01，在 RTX 4060 Laptop GPU 上完成继续训练及保存权重后的重新加载评测。属于原始有向图数据上的训练基线，不包含图池补全、反向边或结构排序器。

## 设置与数据

基座为官方已微调的 GCR-Qwen2-0.5B，模型/数据版本与 [CUDA 首轮实验](CUDA_FINDINGS.md) 相同；不是从 Qwen 原始基座复现论文训练。

- 遍历完整 WebQSP train 2,826 题，保留 2,708 题，每题按长度及路径文本确定性选择一条最短非空路径；118 题无非空路径，0 条超长。
- 独立 validation split 前 100 题中 93 题有非空路径，7 题跳过；其 loss 只衡量可训练路径样本，不代表全部验证题。
- LoRA r=8、alpha=16、dropout=0.05，仅 q_proj/v_proj，540,672 个可训练参数；bf16，batch=2，梯度累积=8，学习率 2e-5，cosine schedule，warmup=0.03，seed=42，最大长度 512。
- 用户提示及 padding 不参与 loss；过长序列整条拒绝，不截断路径。训练不读 test split。
- 请求 1 epoch，Trainer 实际记录 0.998523 epoch、169 次 optimizer 更新；旧版 Trainer 在梯度累积末尾不足一组时未完成最后一组更新，因此不是严格的完整一轮更新。

## 训练结果

| 指标 | 数值 |
|---|---:|
| 训练前 validation loss | 0.340887 |
| 训练后 validation loss | 0.332987 |
| 平均 train loss | 0.312032 |
| 训练段耗时 | 133.89 秒 |
| PyTorch 峰值 allocated | 2.17 GiB |

保存的 96 个 adapter 张量均为有限值，LoRA B 权重已从零初始化发生实际更新。adapter 权重约 2.18 MB；最终权重与配置保存在 [adapter](../../graph-constrained-reasoning/training_runs/webqsp_lora_v1/adapter/)，完整样本 ID、配置、训练/验证日志见 [training_manifest.json](../../graph-constrained-reasoning/training_runs/webqsp_lora_v1/training_manifest.json)。

## 同一批测试集前 100 题

重新加载并合并保存的 adapter，以 fp16 / SDPA / beam=2 / 2 跳执行图约束生成，测试样本 ID 与原基线逐题对齐；测试未用于选择 epoch、调学习率或选权重。

| 指标 | 原基线 | LoRA v1 |
|---|---:|---:|
| 官方 Hit | 63% | 66% |
| 官方 F1 | 37.71% | 40.87% |
| 首位候选答案 Hit | 60% | 59% |
| 首位候选 gold 终点 | 58% | 56% |
| 任一候选 gold 终点 | 61% | 65% |
| 路径逐边核对通过 | 200/200 | 199/200 |
| 运行失败 / 漏题 | 0 / 0 | 0 / 0 |

Hit 新增命中：WebQTest-56、78、80、114、122；丢失命中：WebQTest-42、116。净增加 3 题。测试集固定前缀仅 100 题，单个 seed，没有统计显著性或全量收益结论。官方 Hit 是整段输出子串匹配，不能当作严格精确匹配。

**这版权重不替换原基线。** beam 覆盖有所增加，但 top-1 退化，并产生一个无法在原图核对的候选：WebQTest-73 的 `Maasai people -> people.ethnicity.languages_spoken -> English Language`。保留失败原文，不剔除候选来美化成绩。当前沿用官方特殊 token 触发与空前缀回退机制，尚未定位该候选逃离约束的具体原因；不能宣称微调后的流程仍有无条件的零幻觉保证。

评测原始文件见 [manifest](cuda_results/webqsp_100_lora_v1/manifest.json)、[逐题预测与核对](cuda_results/webqsp_100_lora_v1/predictions.jsonl)、[官方评测](cuda_results/webqsp_100_lora_v1/eval_result.txt)、[候选分析](cuda_results/webqsp_100_lora_v1/candidate_analysis.json)。

## 后续

优先诊断约束逃逸并加入生成 token 级审计，再在验证集比较多轮训练或更广的 LoRA target modules。结构排序器仍未训练；可沿原设计先做训练图特征统计、验证集拟合，再评估 R1。当前结果仅是第一轮 LoRA 实验，不是补全训练方案的收益验证。

运行命令见 [CUDA_RUNBOOK.md](../../graph-constrained-reasoning/CUDA_RUNBOOK.md)。7 项自动测试通过，包括助手 token mask、超长拒绝、路径核对及候选统计。
