# 全量多 seed：C2 对 A_multi 能否复现

背景见 `experiments/FINDINGS.md` X 节。前 500 题上，CWQ 的修正忠实命中 3 对 3 +2.7 点（p=0.14，未确认）；
WebQSP 全量 +2.3 点（p=0.007）只有 seed 42 一组，而前 500 题 3 个 seed 合并 Hit 掉了 2.8 点。
这次不训练，用 v2 过夜已训好的 adapter，在全量测试集上把两边都补到 3 个 seed。

## 一条命令（GPU 电脑，仓库根目录）

```powershell
git pull
.venv/Scripts/python.exe -u graph-constrained-reasoning/workflow/run_full_seeds.py --push
```

- 先自检：CUDA、全部测试、6 个 adapter 是否在。任一不过就不开跑。
- **合计约 15.5 小时**，一晚跑不完。可以加 `--hours 10`：超过 10 小时不再开新的一组，第二晚原命令重跑接着跑。
- 每跑完一组就 commit + push（预测、分数、`FULL_SEEDS_REPORT.md`），Mac 上 `git pull` 随时能看。
- 中断后原命令重跑：已完成的组跳过；跑了一半的那组改名 `*_failed` 后从头重跑（CWQ 一组约 2 小时）。
- 只想跑一部分：`--stages 1`（只跑 WebQSP）或 `--stages 2`（只跑 CWQ）。

## 两个阶段

| 阶段 | 数据 | 组（按顺序，C2 与同 seed 的 A_multi 成对） | 预计 |
|---|---|---|---|
| 1 | WebQSP 全量 1,628 题 | C2_s43、A_multi_s43、C2_s44、A_multi_s44（seed 42 已在 v2 阶段 4 跑过） | ~3.4 h |
| 2 | CWQ 全量 3,531 题 | C2、A_multi、C2_s43、A_multi_s43、C2_s44、A_multi_s44 | ~12 h |

解码设置与 v2 相同（多重图 2 跳，prefill）。产物在 `gcr-lab/experiments/cuda_results/v2/webqsp_1628/`
和 `v2/cwq_3531/`，记录在 `gcr-lab/experiments/cuda_results/FULL_SEEDS_REPORT.md`。

## 怎么看报告

每跑完一组，报告追加两张表：

- 分数表：列同 v2，看 `hit` 和 `f.strict`（修正后的忠实命中，论文用这一列）。
- C2 − A_multi：每个已配齐的 seed 一行，再加 3 个 seed 合并一行。数值是百分点，CI 和 p 都按种子题重采样
  （CWQ 同一种子题改写出的题彼此相关，逐题检验偏乐观）。**只看合并那一行**。

判读（STATUS_AND_NEXT §7）：

- 两个数据集的 `faithful_strict_hit` 合并后都显著为正，且 WebQSP 的 `hit` 不显著下降：训练路径修复进论文主表。
- 不复现：论文主线改为训练缺口的存在性证据（E/H/N）、指标缺陷（S）加推理侧补全（T–V）。
- CWQ 全量也只有 344 个种子题，CI 半宽估计约 ±2.7 点，与增益同量级，结果可能仍在边缘，事先接受这一点。
