# CUDA 首轮实验：真实模型基线与排序空间

日期：2026-11-01。接续阅读报告的 MPS 小规模复现与已有的 CPU 图结构实验，本轮完成 GPU 环境迁移和基线扩大；尚未训练补全模型或结构排序器。

## 完成内容

- RTX 4060 Laptop GPU（8GB）实际运行官方 `rmanluo/GCR-Qwen2-0.5B-Instruct`。
- 固定模型 commit `ec16a9e8c15e5792629e9405a42cea1562076b4e`、RoG-webqsp commit `c0632533135a06f8c5d536b420deec5fcb5c58f3`。
- Windows / Python 3.11.4 / PyTorch 2.5.1+cu121 / Transformers 4.44.2；普通 beam=2、2 跳、fp16、SDPA、seed=42、max_new_tokens=1024。
- 逐题保存预测、gold、完整输入、路径核对结果，保存完整 generation 配置与运行资源信息；失败样本计入分母。
- 增加已有 beam 的排序空间分析，为 R1 提供候选覆盖对照，尚不声称排序收益。

完整复跑命令与环境锁文件见 [CUDA_RUNBOOK.md](../../graph-constrained-reasoning/CUDA_RUNBOOK.md)。

## 实测结果

| 指标 | 测试集前 20 题 | 测试集前 100 题 |
|---|---:|---:|
| 完成 / 失败 | 20 / 0 | 100 / 0 |
| 官方 Hit | 65.00%（13/20） | 63.00%（63/100） |
| 官方 F1 | 44.03% | 37.71% |
| 仅答案段 Hit | 65.00% | 63.00% |
| 仅答案段 F1（答案去重） | 44.03% | 37.70% |
| 官方 Path F1 | 43.69% | 38.40% |
| 路径逐边核对通过 | 40/40 | 200/200 |
| 计时段耗时 | 35.20 秒 | 168.43 秒 |
| PyTorch 峰值 allocated | 1.29 GiB | 1.29 GiB |
| PyTorch 峰值 reserved | 1.55 GiB | 1.55 GiB |

计时包括逐题 trie 构建、推理、路径核对及写预测文件，不包括下载、模型加载、最终评测。显存为 PyTorch 自身的统计，不包括桌面程序、CUDA 驱动等占用。两组前 20 题的 ID 与预测文本完全相同。

旧报告记录 Hit=65%、F1=45.69%、Path F1=43.69%、耗时约 53 秒。本轮 Hit 与 Path F1 对齐，答案 F1 不完全一致；仓库没有旧运行可用的原始预测，尚未定位差异来源，不能宣称逐 token 复现或将耗时差作为严格的硬件加速比。

原始输出：

- [20 题 manifest](cuda_results/webqsp_20/manifest.json)、[预测](cuda_results/webqsp_20/predictions.jsonl)、[官方评测](cuda_results/webqsp_20/eval_result.txt)。
- [100 题 manifest](cuda_results/webqsp_100/manifest.json)、[预测](cuda_results/webqsp_100/predictions.jsonl)、[官方评测](cuda_results/webqsp_100/eval_result.txt)。

## R1 候选空间

使用保存的 beam 输出做事后分析，不利用测试答案拟合任何排序权重。gold 终点命中要求路径核对通过，且终点与某个 gold 答案在归一化后完全相等。

| 指标 | 前 20 题 | 前 100 题 |
|---|---:|---:|
| 首位候选的答案段 Hit（官方字符串匹配） | 60% | 60% |
| 任一候选的答案段 Hit | 65% | 63% |
| 首位候选有 gold 终点 | 60% | 58% |
| 任一候选有 gold 终点 | 65% | 61% |
| gold 终点仅在后位候选中的题数 | 1 | 3 |

详见 [20 题分析](cuda_results/webqsp_20/candidate_analysis.json) 与 [100 题分析](cuda_results/webqsp_100/candidate_analysis.json)。

这批 beam=2 候选中，按 gold 终点指标，理想排序可将 top-1 从 58/100 提至 61/100，上界仅有 3 个百分点。正确终点不保证关系语义正确；别名及官方子串匹配也会造成终点指标与答案 Hit 不同。该 oracle 不是实际排序器结果，保留所有候选时也不能通过重排增加覆盖。

## 接续进度

1. 已完成：CUDA 环境、20 题对照、100 题扩展、逐边核对、候选空间分析，相关自动测试 5 项通过。
2. 下一阶段：在验证集扩大 beam 到 10，测量候选覆盖及耗时；从训练图统计 F1–F4，补充 F5 问题—关系匹配，在验证集拟合并冻结权重。
3. 再执行：同批候选上的 R1、特征消融；报告 top-1 路径指标与保留候选覆盖，接入归纳模型后再报告完整系统 Hit/F1。
4. 后续：全量 WebQSP/CWQ、8B 4bit 对照、R2 剪枝及训练侧补全。当前没有进行这些实验，不把小样本、0.5B、单阶段成绩与论文 8B + ChatGPT 的完整系统直接比较。

100 题是固定前缀样本，并非独立随机抽样；包含前 20 题。路径核对全通过只说明本批输出存在于给定图中，不意味着答案全对或所有输入都能保证相同结果。
