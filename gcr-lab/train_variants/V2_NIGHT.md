# v2 过夜实验：修好训练路径选择后重训重评

背景见 `experiments/FINDINGS.md` R 节。一句话：C/D 的 WebQSP 训练路径没做 SPARQL 约束，且每题
那一条训练路径按字母序挑，大多挑到反向走边的路径；v2 修掉这两处。

## 今晚只需一条命令（GPU 电脑，仓库根目录）

```powershell
git pull
.venv/Scripts/python.exe -u graph-constrained-reasoning/workflow/run_v2_night.py --push --hours 10
```

- 先自检：CUDA、全部测试、训练集与 `ae_full/A` adapter 是否在。任一不过就不开跑。
- 每个阶段结束都 commit + push（adapter、预测、`V2_NIGHT_REPORT.md`），早上 Mac 上 `git pull` 就能看。
- 中断后原命令重跑即可：已训完的 adapter、已评完的组都会跳过；跑了一半的会改名 `*_failed` 后重来。
- 某组训练或评测失败只记录、不停；依赖它的评测会跳过。
- `--hours 10`：超过 10 小时不再开新阶段（已开的阶段会跑完）。只想跑一部分：`--stages 1 2`。

## 四个阶段（按优先级）

| 阶段 | 训练（各 1 epoch，约 18–20 分钟/个） | 评测（多重图 2 跳，prefill） | 预计 |
|---|---|---|---|
| 1 | C2、D2 | WebQSP + CWQ 前 500 题 | ~1.7 h |
| 2 | C_wq、C_fwd（消融） | WebQSP + CWQ 前 500 题 | ~1.7 h |
| 3 | C2、A 的 seed 43、44 | WebQSP + CWQ 前 500 题 | ~3.5 h |
| 4 | 不训练 | A_multi（11-04 的 A）与 C2 在 WebQSP 全量 1,628 题 | ~2 h |

合计约 9 小时。产物：

- adapter：`graph-constrained-reasoning/training_runs/v2/<名字>/`（训练日志 `v2/<名字>.log`）
- 预测与分数：`gcr-lab/experiments/cuda_results/v2/<数据集>_<题数>/`，每组一个目录，`faithfulness.json` 是该数据集的汇总
- 过程记录：`gcr-lab/experiments/cuda_results/V2_NIGHT_REPORT.md`

## 各组是什么

| 组 | 训练集 | WebQSP 路径 | CWQ 路径 | 选哪条训练 |
|---|---|---|---|---|
| A（11-04） | `A.jsonl.gz` | 官方有向图最短路 | 同左 | 最短 + 字母序 |
| C（11-04） | `C.jsonl.gz` | 多重图最短路，**无约束** | SPARQL 关系约束 | 最短 + 字母序 |
| C_wq | `C_wq.jsonl.gz` | SPARQL 约束 | SPARQL 约束 | 最短 + 字母序 |
| C_fwd | `C_fwd.jsonl.gz` | 同 C | 同 C | 正向优先 |
| **C2** | `C2.jsonl.gz` | SPARQL 约束 | SPARQL 约束 | 忠实优先 → 正向优先 |
| D2 | `D2.jsonl.gz` | 同 C2 | C2 + 图池修复 ≤2 跳（+832 题） | 同 C2 |

被选中训练的那条路径（`data/v2_stats.json`）：

| 组 | WebQSP 忠实 | WebQSP 含反向步 | CWQ 忠实 | CWQ 含反向步 |
|---|---|---|---|---|
| A | 73.6% | 0% | 19.8%* | — |
| C | 29.8% | 59.5% | 94.8%* | 79.2%* |
| C_wq | 98.3% | 7.5% | 97.0% | 63.7% |
| C_fwd | 70.2% | 1.5% | 95.5% | 32.4% |
| C2 | 98.3% | 1.1% | 97.0% | 32.8% |
| D2 | 98.3% | 1.1% | 97.1% | 35.0% |

\* 1,174 题抽样。C2 先按忠实、再按反向步数排序，所以 CWQ 剩下约三分之一含反向步的题，
都是在子图里找不到同样忠实的纯正向路径的题，不是选择出错。

## 早上怎么看

报告里每个数据集有一张分数表和配对检验：

- 分数表列：`hit`、`f1`、`f.hit`（faithful_hit：答对且路径关系全落在同一个 SPARQL 里）、
  `unf.hit`（答对但路径不忠实）、`faith`（所有候选路径的忠实率）。表里的 `A_multi`、`C`、`D`
  是 11-04 的结果（同题、同解码设置），其余是今晚的。
- 配对检验：每个 v2 组对 11-04 的 A_multi 和 C 做同题 McNemar，`+x/-y` 是比基线多答对/少答对的
  题数，p < 0.05 才算差异显著。

要回答的问题与判读：

1. **WebQSP 的 Hit 回来了没有**（最关键）：C2 对 A_multi 的 hit 不再显著下降（11-04 的 C 是
   +20/−37，p=0.03），且 f.hit ≥ A_multi。
2. **CWQ 的收益保住没有**：C2 的 CWQ f.hit 仍在 0.20 左右（A_multi 0.074），hit 不降。
3. **两处修复各占多少**：C_wq 只修约束、C_fwd 只修选择；和 C、C2 一起构成 2×2。
4. **图池修复有没有额外收益**：D2 对 C2。
5. **seed 方差**：C2 三个 seed（42/43/44）、A 三个 seed 的 hit 与 f.hit 波动；差异小于这个波动的结论不能写进论文。
6. 阶段 4 用全量 WebQSP 看结论是否只是前 500 题的偶然。

事后在 Mac 上重新打分或换基线：

```bash
uv run -q --python 3.11 --with scikit-learn --with networkx --with datasets --with transformers \
  python graph-constrained-reasoning/workflow/score_faithfulness.py \
  gcr-lab/experiments/cuda_results/v2/webqsp_500/* --baseline gcr-lab/experiments/cuda_results/ae_full/webqsp_500/A_multi
```

## 已知局限

- `faithful` 只看关系是否落在同一个 SPARQL 中，不检查方向和顺序；反向走边的路径也可能算忠实。
  更严格的方向感知指标留到之后。
- 只有前 500 题（阶段 4 补 WebQSP 全量）；CWQ 全量 3,531 题约需 2 小时/组，今晚不跑。
