# A–E 固定更新预算 GPU 先导对照

本轮使用已打包的 A–E 数据，分别从同一固定版本的官方 GCR-0.5B 初始化新的 LoRA，不从 v2 adapter 继续，也不在组间串接权重。目的为验证打包数据可以实际训练，并比较共同验证任务上的短程变化；不是五组完整 epoch 实验。

在仓库根目录运行：

```powershell
.venv/Scripts/python.exe -u graph-constrained-reasoning/workflow/run_variant_pilot.py --steps 128 --output graph-constrained-reasoning/training_runs/ae_pilot_128_mb1
```

输出目录必须为空。脚本按 A、B、C、D、E 串行执行；任一组返回失败时停止，不把失败组当成完成组。每组的命令、状态和汇总保存到 `pilot_manifest.json`，详细 stdout/stderr 保存为各组日志。

重启调度可加 `--resume` 跳过已完成且更新预算匹配的组；未完成组的目录需要先另行归档，脚本不会自动覆盖。结束后运行 `workflow/summarize_variant_pilot.py <pilot_directory>` 核对全部组的状态、实际更新数、共同验证样本、初始化 loss、训练配置与数据哈希，生成 `verified_summary.json`。

## 固定设置

- 每组 128 次 optimizer update，microbatch=1、梯度累积=16，每次更新 16 条序列，共 2,048 次序列呈现；各组分别 shuffle，样本内容并非逐条配对。
- 每题只取一条确定性最短非空路径，最大长度 512；超长序列丢弃，绝不截断路径后训练。
- LoRA q/v、r=8、alpha=16、dropout=0.05；bf16、SDPA、梯度检查点（non-reentrant）、学习率 2e-5、cosine、warmup 0.03、seed=42。
- 默认排除所有 WebQSP validation/test seed 对应的 CWQ 训练行；不使用 `--keep-test-seeds`。读取测试 split 仅为取 ID 排除同源行，不用测试答案训练或调参。
- 共同验证集为完整 WebQSP validation，取官方有向图的每题一条非空最短路径，eval batch=1。记录训练前后相同验证任务的 loss。
- 固定步数覆盖不足一个 epoch；不同组样本数、序列长度、训练耗时和有效 token 数并不相同，不能把固定更新预算表述为严格相同 FLOPs 或 token 预算。

## 解释边界

共同 WebQSP 验证 loss 只是运行与短程拟合对照，不足以评判 CWQ 的 SPARQL 忠实性、修复题收益或完整系统 Hit/F1；不能单凭它宣布某组“优于”其他组。旧版实验 eval batch=2，其聚合 loss 不与本轮直接比较。

C 在 SPARQL 约束找不到路时回退 B，因此不是完全纯净的 SPARQL 路径集。D/E 包含图池修复；E 的长路径还需要相应三跳推理和规模控制。推理应分别对齐 README 中各组图与跳数配置。

特别是 E 的修复路径来自训练图池：`cuda_baseline.py --graph multi --hops 3` 仍只在题目自带子图上建 trie，没有自动检索图池。加深跳数不等于把图池中的缺边引入题目子图；完整 E 端到端实验还需要训练图池检索和剪枝接入，不能只凭本轮训练或这一条命令宣称修复已在推理中生效。

官方起始权重已接受过原始混合数据训练；排除本轮训练行并不能清除基座已有的信息，也不会重新构建打包数据所依赖的图池。此处不宣称严格从零或完全无泄漏。

## 本机资源配置

最初 microbatch=2 的尝试显存接近 8GB，后启用梯度检查点仍有高峰，因此中断并保留在本机。正式对照统一重启为 microbatch=1 / 累积=16。中断运行不纳入汇总，不与后续组混合。Git 忽略这些中断目录及 trainer checkpoint；提交完成组最终 adapter、日志与运行记录。
