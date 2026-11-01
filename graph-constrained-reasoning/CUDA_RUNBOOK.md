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
```

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
