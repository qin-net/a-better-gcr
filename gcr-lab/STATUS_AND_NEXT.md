# 进度与下一步（2026-11-04）

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

## 3. 今晚执行清单（GPU 电脑）

所有命令都在仓库根目录用 PowerShell 执行。**不要改代码，不要用 `--keep-test-seeds`。**

### 0. 准备

```powershell
git pull
.venv/Scripts/python.exe -m pytest -q graph-constrained-reasoning/tests
```

应该 17 个测试全部通过。不通过就停下，把输出记下来。

### 阶段 1：ae_full，两个数据集各取前 100 题（16 次运行，预计 1–2 小时）

```powershell
.venv/Scripts/python.exe -u graph-constrained-reasoning/workflow/run_variant_eval.py `
    --pilot graph-constrained-reasoning/training_runs/ae_full --limit 100
```

- 依次跑 official、A、A_multi、B、C、D、E、E_hops3，先跑 WebQSP，再跑 CWQ。
- 结果写在 `gcr-lab/experiments/cuda_results/ae_full/{webqsp_100,cwq_100}/`，每个数据集最后打印一张表并写 `faithfulness.json`。
- E_hops3 的 trie 会大很多，最慢，可能内存不够。

跑完立刻提交一次，见“提交”一节。

### 阶段 2：主要几组扩到前 500 题（12 次运行，预计 3–5 小时）

100 题的标准误约 ±5 个百分点，不足以区分各组，所以扩到 500 题：

```powershell
.venv/Scripts/python.exe -u graph-constrained-reasoning/workflow/run_variant_eval.py `
    --pilot graph-constrained-reasoning/training_runs/ae_full --limit 500 `
    --runs official A A_multi B C D
```

结果写在 `cuda_results/ae_full/{webqsp_500,cwq_500}/`。如果天亮前没跑完也没关系，提交已完成的部分。

### 阶段 3（时间还够才跑）：128 步先导，前 100 题

```powershell
.venv/Scripts/python.exe -u graph-constrained-reasoning/workflow/run_variant_eval.py `
    --pilot graph-constrained-reasoning/training_runs/ae_pilot_128_mb1 --limit 100 `
    --runs A B C D
```

它用来看训练步数对忠实度的影响，优先级最低。

### 出错时

- 驱动遇到失败会停下，报错里会写日志路径（`<输出目录>/<run>.log`）。把日志最后 30 行记下来。
- 然后把失败的那个目录改名，比如 `E_hops3` 改成 `E_hops3_failed`，再用同一条命令重跑。已完成的组会自动跳过，最后的打分会包含所有已完成的组。
- 只有 E_hops3 失败（比如内存不够）时，就加 `--runs official A A_multi B C D E` 跳过它，并记录原因。
- 不要删除任何结果目录，也不要修改 `predictions.jsonl`。

### 提交

每个阶段结束后都提交一次：

```powershell
git add gcr-lab/experiments/cuda_results/ae_full gcr-lab/experiments/cuda_results/ae_pilot_128_mb1
git commit -m "A–E 解码评测：<阶段与完成情况>"
git push
```

commit message 里写明完成了哪些运行、哪些失败以及原因，再附上每个阶段终端最后打印的表格。

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
