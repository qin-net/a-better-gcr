# 进度与下一步（2026-11-08 更新）

**2026-11-08：全量三版本评测完成，下一步核验自动指标是否对应真实推理改善。**

最新 GPU 结果在 `experiments/cuda_results/FULL_SEEDS_REPORT.md`（提交 `b063995`）。两组各三个训练版本，
按原题家族重采样：WebQSP 全量修正忠实命中 +2.4 个百分点（95% 区间 +0.8～+4.1，p=0.0024）；
CWQ 全量 +1.8 个百分点（+0.2～+3.5，p=0.032）。Mac 精确匹配复核方向一致，p 分别约 0.0024、0.035。
总答对率分别变动 −0.1、−1.0 个百分点；未检出显著下降不等于证明没有代价。三个训练版本平均后再按题重采样，
也不等于充分估计任意训练随机性的影响。以下“未确认”“缺全量数据”均为历史记录。

**当前进度：80 题、320 条候选的 AI 初审完成**，通俗结论见
[`AI审阅报告_2026-11-08.md`](../AI审阅报告_2026-11-08.md)，完整记录在
[`eval/ai_review_2026-11-08/AI逐题详解.md`](eval/ai_review_2026-11-08/AI逐题详解.md)。
自动指标判为改善的各 10 题中，WebQSP 有 6 题、CWQ 有 2 题被 AI 判为单条完整路径改善。
既有真实改善、也有真实退步；自动指标仍会放过缺少第二条件、数值条件等不完整路径。
另外已在所用 RoG-CWQ 数据文件中确认三处题面与标注异常，尚未追溯最初发布版。

标签在揭晓甲乙身份前固定，但审阅者此前参与生成题册，**不是独立双盲，也没有人工审阅结论**。
原人工空表保持空白。这是有意分组的诊断样本，不能把样本比例换算为全题库净收益。

**下一步：先完善评价，重算现有预测，暂不重训。** 分开报告答案命中、关系一致性、完整条件满足；
无法可靠核验的条件单列，不强行判错。现有全量增益仅支持关系一致性代理指标，不等于完整推理能力提升。
当前尚未修改正式评分器或数据答案，无需重跑已完成的全量 GPU 评测。

---

**2026-11-06 结论（Mac 端，详见 `experiments/FINDINGS.md` X）**：v2 过夜全部跑完、0 失败。按种子题重算后：

| C2 对 A_multi | Hit | 修正忠实命中 | 状态 |
|---|---|---|---|
| CWQ 前 500，3 seed | +0.1 点 | +2.7 点，p=0.14 | 未确认 |
| WebQSP 前 500，3 seed | −2.8 点，p=0.035 | −0.7 点，p=0.62 | Hit 可能有代价 |
| WebQSP 全量，仅 seed 42 | −0.2 点 | +2.3 点，p=0.007 | 只有一个 seed |

稳健的只有“再训一轮”（A_multi 对 official）。训练路径修复的效果还没有确认，缺全量多 seed 的数据。

修正判据已固定：`score_faithfulness.py` 新增 `faithful_strict_hit`，读 `eval/faithfulness_criterion.json`，文件
缺失时报错；评测脚本的报告也输出这一列。**论文表格用这一列**，`faithful_hit` 只为复现旧结果。

下一步见文末 §7。

以下保留 11-04/11-05 的原文作记录。

**2026-11-05 结论（过夜评测，详见 `experiments/FINDINGS.md` Q）**：主假设在 CWQ 上成立。
SPARQL 约束训练（C/D）让忠实命中从 7.4% 升到 20%（p<1e-12），Hit 不变；代价是 WebQSP 的 Hit
降约 3 个百分点。换图本身无影响；B 有害；128 步先导看不到效果。下一步见文末 §6。

**2026-11-05 晚**：WebQSP 的 Hit 下降查明是训练路径构造的 bug（FINDINGS R），已出修正版训练集
C2/D2 和两组消融。**今晚 GPU 只跑一条命令，全部说明在 [`train_variants/V2_NIGHT.md`](train_variants/V2_NIGHT.md)**：

```powershell
git pull
.venv/Scripts/python.exe -u graph-constrained-reasoning/workflow/run_v2_night.py --push --hours 10
```

以下 §1–§5 是 11-04 的原文，保留作记录。

本文件给 GPU 电脑上的 agent 照着执行，也是给人看的阶段小结。§3 是今晚要跑的全部内容。

## 1. 做到哪里了

论文主线：**GCR 的训练数据有系统性缺口，修补训练路径能否让模型推理链更忠实。**

已有证据（CPU 分析，细节见 `experiments/FINDINGS.md` 各节）：

| 节 | 结论 |
|---|---|
| E | 官方流程静默丢掉 20.1% 的 CWQ 训练题（答案不在子图里） |
| H | 把训练子图拼成图池，3 跳内能救回 77%，4 跳内 94% |
| M | 但图池最短路只有 2.4% 和 SPARQL 一致，直接加进训练是噪声 |
| N | 只沿 SPARQL 关系、允许反向走边，仍能救回 60–75% |
| O | 官方建图每对实体只留一个关系，丢掉 7–30% 的边，改为多重图 + 反向边 |
| P | 纯结构先验选不出正确路径（MRR 0.033），问题–关系匹配 + 训练先验可以用来剪枝（top-100 留住 94%） |

已做的 GPU 工作：

- 官方 GCR-0.5B 基线，WebQSP 前 100 题 Hit 0.63；LoRA v1/v2 在 WebQSP 上继续训练，分别为 0.66 和 0.70。
- 五组训练集 A–E（`train_variants/README.md`），已排除测试题泄漏。
- 128 步先导 `training_runs/ae_pilot_128_mb1`，以及完整 1 epoch 的 `training_runs/ae_full`。

ae_full 的验证 loss：A 从 0.3153 降到 0.3075，B–E 升到 0.334–0.346。验证集用的是官方有向图路径，这和 A 的训练分布相同，所以这个结果**不能说明 B–E 更差**，只能说明它们学到的路径分布不同。有一点信息：C/D/E（约 0.334）低于 B（0.346），说明按 SPARQL 选的路径更接近官方路径，不受约束的多重图最短路里有不少是绕路。

**缺的是真正的证据：解码评测。** A–E 还没在测试集上解码过。需要的是 Hit/F1，以及路径是否忠实于 SPARQL（`workflow/score_faithfulness.py`）。论文的核心表格就是这张。

已有的忠实度参照（WebQSP 前 100 题，未用 prefill，所以不能和今晚的结果直接比）：

| 运行 | hit | faithful_hit | unfaithful_hit | 路径忠实率 |
|---|---|---|---|---|
| 官方 | 0.63 | 0.53 | 0.10 | 52.0% |
| LoRA v2 | 0.70 | 0.60 | 0.10 | 55.0% |

## 2. 今晚要回答的问题

1. **C/D 是否比 A 更忠实**：重点看 CWQ 上的 `faithful_hit` 和路径忠实率，这是主假设。
2. **换图本身有没有影响**：比较 A 和 A_multi，同一个 adapter 只换推理图。
3. **代价**：B–E 在 WebQSP 上的 Hit 掉了多少。
4. **E 加深到 3 跳有没有用**：E 对比 E_hops3。预期没用，因为 trie 仍只在题目子图上（FINDINGS K）。

预先知道的上限：CWQ 测试集 3,531 题中有 **19.3%（683 题）答案不在题目子图里**，WebQSP 是 4.4%。这些题任何一组都答不对，训练侧修复也救不了，这是推理侧的问题（见 §5）。

## 3. 今晚执行（GPU 电脑，一条命令）

在仓库根目录用 PowerShell 执行：

```powershell
git pull
.venv/Scripts/python.exe -u graph-constrained-reasoning/workflow/run_overnight.py --push
```

然后就可以不管了。脚本会自己完成这些事：

1. **启动前检查**：CUDA 可用；单元测试通过（装了 pytest 才跑）；10 个 adapter 文件齐全。任何一项不满足就直接退出，不开始跑。
2. **按优先级依次跑三个阶段**：

   | 阶段 | 内容 | 运行次数 | 预计 |
   |---|---|---|---|
   | 1 | ae_full 全部 8 组，WebQSP、CWQ 各前 100 题 | 16 | 1–2 小时 |
   | 2 | official A A_multi B C D，各前 500 题 | 12 | 3–5 小时 |
   | 3 | 128 步先导 A B C D，各前 100 题 | 8 | 约 30 分钟 |

   阶段 2 扩到 500 题，是因为 100 题的标准误约 ±5 个百分点，不足以区分各组。阶段 3 用来看训练步数的影响。
3. **出错时**：某一组失败或超时（默认每题 20 秒的预算，正常约 2 秒），就把它改名为 `<run>_failed` 并保留日志，然后继续下一组。打分出错也不会中断，预测文件都保留着，可以事后重新打分。
4. **每个阶段结束**：自动 `git commit` 和 `git push` 结果，并更新 `gcr-lab/experiments/cuda_results/OVERNIGHT_REPORT.md`。这个报告里有逐组的开始/完成时间、失败原因和每个数据集的结果表。

可选参数：

- `--hours 8`：超过 8 小时后不再开始新的阶段，正在跑的阶段会跑完。
- `--stages 1 2`：只跑指定的阶段。

**中断了**（关机、断电、Ctrl+C）：重跑同一条命令即可。已完成的组会自动跳过，跑到一半的那组会自动改名为 `_failed` 后重跑。

**push 失败**（网络问题）：结果已经在本地 commit 了，第二天手动 `git push` 就行。

**不要改代码，不要删除结果目录，不要修改 `predictions.jsonl`。**

单独跑某一组时，用底层命令，参数和以前一样：

```powershell
.venv/Scripts/python.exe -u graph-constrained-reasoning/workflow/run_variant_eval.py `
    --pilot graph-constrained-reasoning/training_runs/ae_full --limit 100 --runs official C --keep-going
```

## 4. 结果怎么读（拿到结果后由 Mac 端分析）

| 现象 | 含义 | 下一步 |
|---|---|---|
| CWQ 上 C/D 的 faithful_hit 明显高于 A，Hit 不降 | 主假设成立 | 跑全量测试集和多个 seed，写论文主表 |
| C/D 忠实度升高，但 Hit 下降 | 忠实与命中之间有取舍 | 报告取舍；用 R2 剪枝把 Hit 拉回来 |
| A 与 A_multi 差别大 | 换图本身就有影响 | B–E 要和 A_multi 比，不能和 A 比 |
| 各组差别都在噪声内 | 训练路径不是瓶颈 | 转向推理侧（§5） |

需要注意的口径：

- 今晚所有运行都用了 `--prefill-path`，组间可比；但和 §1 里未用 prefill 的旧结果不可比。
- `faithful` 要求路径的关系全部出现在**同一个**标注 SPARQL 中。SPARQL 里还包含约束用的关系（时间、类型等），所以这个判据偏宽松：它只能说明路径没走题外关系，不能保证顺序和方向都对。组间比较不受影响。
- 每组只训练了一个 seed（42），差异小于约 5 个百分点时不能下结论。

## 5. 之后的工作（Mac 端，等今晚结果出来再定）

1. **配对显著性检验**：在 `score_faithfulness.py` 里加入同题配对的 bootstrap / McNemar 检验。
2. **推理侧补全**：CWQ 测试集有 19.3% 的题答案不在子图里，训练修复对这些题无效。方案是推理时从训练图池检索缺失的边（FINDINGS H/K），再用 P 的剪枝把 trie 控制在可接受的规模。这一步能决定 D/E 的修复在推理时是否真正起作用，也是论文第二部分。
3. **R2 剪枝接入 `cuda_baseline.py`**：每题只保留结构先验 top-k 的候选路径再建 trie。
4. **全量测试集 + 多 seed**：方向确定后在 GPU 上跑最终版本。按每题约 1.6 秒估算，WebQSP 全量一组约 45 分钟，CWQ 约 1.5 小时。

## 6. 11-05 之后的下一步

已完成（Mac 端）：

- `score_faithfulness.py --baseline RUN` 输出同题配对的精确 McNemar 检验（§5.1）。
- `cuda_baseline.py`：2 跳内没有任何路径的题（空 trie）记为 `no_trie`，计入分母但不再让整组失败。
  11-04 WebQSP 500 题的 official 和 A 就是因为一道这样的题（WebQTest-521）被标成失败，结果有效。

下一轮 GPU（11-05 晚，已改为 v2，见 `train_variants/V2_NIGHT.md`）：

1. 训练 C2、D2、C_wq、C_fwd，C2 与 A 加 seed 43、44；全部在 WebQSP 与 CWQ 前 500 题评测。
2. A_multi 与 C2 在 WebQSP 全量 1,628 题上评测。

之后：

- 若 C2 在 WebQSP 不再掉点：C2 在两个数据集全量、3 seed 上出论文主表；E2（≤3 跳）与 3 跳解码。
- 若仍掉点：试 A+C2 混合训练集。
- 方向感知的忠实度指标（现在的 `faithful` 不检查方向和顺序）。

## 7. 11-06 之后的下一步

GPU 上跑全量多 seed，判断 C2 的效果。一条命令：`graph-constrained-reasoning/workflow/run_full_seeds.py --push`，
说明见 `train_variants/FULL_SEEDS.md`。adapter 都已训好，不用重新训练，耗时按 v2 实测估算：

1. **WebQSP 全量**：C2 和 A_multi 的 seed 43、44，4 组约 3.4 小时。回答 p=0.007 能否复现、Hit 是否真的掉。
2. **CWQ 全量 3,531 题**：C2 和 A_multi 的 3 个 seed，6 组约 12 小时。种子从 195 增到 344，按 √n 估算 CI
   半宽约 ±2.7 点，和 +2.7 点的增益同量级，结果可能仍在显著性边缘，要预先接受这一点。

分析一律按种子题，用 3 对 3 合并（`x_cluster_tests.py`）；`run_v2_night.py` 报告里的逐题 McNemar 在 CWQ 上偏乐观。

结果怎么读：

- 两边增益都复现、WebQSP Hit 不掉：训练路径修复进论文主表。
- 不复现：论文主线改为训练缺口的存在性证据（E/H/N）、指标缺陷（S）加推理侧补全（T–V）。
