# CUDA 实验进度

本阶段接续《GCR论文阅读与复现报告》的 MPS / 20 题结果：先在 RTX 4060 上建立真实模型基线，再扩大样本，为结构先验排序的 R1 实验保存同批 beam 输出。

## 环境

在仓库根目录执行（Windows PowerShell，Python 3.11）：

```powershell
uv venv .venv --python 3.11
uv pip install --python .venv/Scripts/python.exe torch==2.5.1 --index-url https://download.pytorch.org/whl/cu121
uv pip install --python .venv/Scripts/python.exe -r graph-constrained-reasoning/requirements-cuda-lock.txt
.venv/Scripts/python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name())"
```

安装命令采用 PyTorch 官方提供的 CUDA 12.1 wheel：<https://pytorch.org/get-started/previous-versions/>。独立推理环境不需要训练用的 DeepSpeed、FlashAttention 或外部模型 API。

`requirements-cuda-lock.txt` 保存本次验证过的完整环境，包含测试依赖；`requirements-cuda.txt` 列出主要依赖及必要兼容限制。特别固定 PyArrow 17 与 NumPy 1.26，避免旧版 datasets 被新版传递依赖破坏。

## 运行

```powershell
# 与报告相同规模：前 20 题、beam=2、2 跳、fp16、SDPA。
.venv/Scripts/python.exe graph-constrained-reasoning/workflow/cuda_baseline.py --limit 20 --output gcr-lab/experiments/cuda_results/webqsp_20

# 扩展基线，包含前面的 20 题，不应当作独立随机样本。
.venv/Scripts/python.exe graph-constrained-reasoning/workflow/cuda_baseline.py --limit 100 --output gcr-lab/experiments/cuda_results/webqsp_100

# 在已生成的候选中，测量 top-1 与包含 gold 终点的 oracle 上界差距。
.venv/Scripts/python.exe graph-constrained-reasoning/workflow/analyze_beams.py gcr-lab/experiments/cuda_results/webqsp_100

# 全量测试；另选新输出目录，--limit 0 表示整个 split。
.venv/Scripts/python.exe graph-constrained-reasoning/workflow/cuda_baseline.py --limit 0 --output graph-constrained-reasoning/results/cuda_webqsp_full

# 多重图 + 反向边建 trie（训练侧修复 B–E 组用）；默认 --graph directed 与上面完全一致。
.venv/Scripts/python.exe graph-constrained-reasoning/workflow/cuda_baseline.py --limit 100 --graph multi --output gcr-lab/experiments/cuda_results/webqsp_100_multi
```

`--graph multi` 保留同一对实体间的所有关系并允许反向走边（`src/multi_relation_graph.py`），trie 约大 4 倍；`path_audit` 随之接受反向边。说明见 `gcr-lab/experiments/FINDINGS.md` 第 O 节。

输出目录必须为空，以免混用不同设置。每次保存模型/数据 commit、参数、运行库版本、GPU 名称、推理耗时、峰值显存、逐题预测及官方评测文件。数据直接取指定版本的原始 parquet，不执行远程数据集脚本。推理错误会保留为空预测，计入分母，并以非零状态退出。运行时间包括逐题 trie 构建和生成，不包括下载、模型加载和最终评测。

`path_audit` 独立检查输出格式、起点、跳数以及每条原始有向边。它与答案命中是两种指标；合法路径仍可能与问题无关。官方 `Hit` 使用整个输出的字符串匹配，可能在路径中命中答案；复现时保留该口径，不把它宣称为严格的答案精确匹配。`answer_section_metrics` 则只取 `# Answer:` 后的文本，去重后用相同的归一化字符串匹配规则计算，仍不是严格精确匹配。

## 实验边界与后续

- 0.5B 权重：<https://huggingface.co/rmanluo/GCR-Qwen2-0.5B-Instruct>。
- 当前是第一阶段图约束生成，没有调用 ChatGPT / GPT-4o-mini 做第二阶段归纳，不能直接与论文的完整系统成绩比较。
- 当前显式使用普通 beam search；汇报生成脚本 `make_report_ppt.py` 也记录了 `--generation_mode beam`。旧运行未保存完整 generation 配置、模型版本及可用的原始预测，因此不能保证与 MPS 结果逐 token 一致。
- 8B 原始 fp16 权重超过 8GB 显存；后续可单独做 4bit 对照，需明确标记量化，不能混入 0.5B 基线。
- 排序路线先做训练图统计与验证集权重拟合，再在这里保存的同一批候选上做 R1。不能用测试答案拟合权重；R2 剪枝及补全训练继续排在其后。

`candidate_analysis.json` 的 gold 终点指标采用归一化后的完全相等，且只统计通过路径核对的候选。它只用于估计已有 beam 中可供排序挽回的空间，不是排序器的实际结果。即使某条路径终点正确，也不保证中间关系符合问题语义；保留所有 beam 的系统也不会仅因重排就提高候选覆盖。

实测结果与完成状态见 `gcr-lab/experiments/CUDA_FINDINGS.md`。

## 单卡 LoRA 继续训练

```powershell
.venv/Scripts/python.exe graph-constrained-reasoning/workflow/train_cuda_lora.py --output graph-constrained-reasoning/training_runs/webqsp_lora_v1
.venv/Scripts/python.exe graph-constrained-reasoning/workflow/cuda_baseline.py --adapter graph-constrained-reasoning/training_runs/webqsp_lora_v1/adapter --limit 100 --output gcr-lab/experiments/cuda_results/webqsp_100_lora_v1
```

这是在官方已微调的 0.5B 权重上继续训练，并非从 Qwen 基座复现官方完整训练。默认完整 WebQSP train、每题一条确定性最短非空路径、1 epoch、LoRA r=8/alpha=16、q/v 投影、batch=2、梯度累积=8、学习率 2e-5、bf16、最大 512 tokens。保留原始有向子图，不补边。过长序列整条跳过，用户提示与 padding 的 labels 为 -100。验证集取独立 validation split 前 100 题，在训练前后分别计算 loss；测试集不参与训练、调参或选择权重。配置参考 [PEFT 0.12 LoRA 文档](https://huggingface.co/docs/peft/v0.12.0/en/package_reference/lora)。

训练目录保存实际样本 ID、过滤计数、训练配置、loss 日志、资源统计以及可加载的 adapter。默认只保存最终 adapter，不保存完整基座或中途 optimizer checkpoint；中断后需使用新目录重新运行。

从 v1 继续训练并按完整验证集 loss 选择 epoch checkpoint：

```powershell
.venv/Scripts/python.exe -u graph-constrained-reasoning/workflow/train_cuda_lora.py --adapter graph-constrained-reasoning/training_runs/webqsp_lora_v1/adapter --epochs 2 --learning-rate 1e-5 --gradient-accumulation 2 --validation-limit 246 --select-best --output graph-constrained-reasoning/training_runs/webqsp_lora_v2
```

继续加载的是 adapter 权重，优化器与学习率调度重新初始化。`--select-best` 在每个 epoch 评估并保存 checkpoint，最终重新加载验证 loss 最低的权重，再导出到 `adapter/`。中间 trainer checkpoint 留在本机并由 Git 忽略，最终 adapter 和运行记录提交。梯度累积设为 2，让 2,708 条训练序列对应的 1,354 个 microbatch 可以整除。

评测时可加 `--record-token-trace`，在逐题输出中保留包含特殊 token 的原始字符串及整次 beam 搜索的空前缀回退计数。计数不是单条输出的回退次数；该诊断不改变原始解码行为。

`--prefill-path` 则显式改变生成条件：在 assistant 输入后预填 `# Reasoning Path:\n<PATH>`，从第一个生成的路径 token 开始进入 trie；返回文本会补回路径标题。只适用于具有专用 PATH token 的模型，默认关闭。它防止开头缺失/写错 PATH 标记，不移除原有空前缀回退，因此仍应检查 `path_audit`，其指标也应单独报告。
