# GCR Lab — 图约束解码，一步一看

这是一个不依赖 GPU、不下载模型的小实验室，用纯 Python 复刻 GCR
（*Graph-constrained Reasoning*, ICML 2025）解码阶段的核心机制：
**推理路径上的每个 token 必须是 KG-Trie 中的合法前缀**。

## 为什么做这个

仓库里原先只有论文、报告和官方代码。官方流程需要 PyTorch + CUDA +
Llama-3.1-8B，本机跑不起来，而且即使是 0.5B 的小模型，也只能看到最终输出，
看不到"约束到底在每一步做了什么"。

这里把整件事缩小到可以一眼看清的尺度：一张 21 条三元组的小图谱、
一个手写的打分表代替语言模型、一个 50 词的词表。机制一个不少，规模小到可以
逐步打印。

## 跑起来

```bash
cd gcr-lab
python3 -m gcr_lab.demo        # 控制台跑 4 道题，两种模式，写入 out/traces.json
python3 -m gcr_lab.make_html   # 生成 out/lab.html
open out/lab.html
```

只需要 Python 3.9+，无第三方依赖。

真实 GPU 模型实验另见 [`../graph-constrained-reasoning/CUDA_RUNBOOK.md`](../graph-constrained-reasoning/CUDA_RUNBOOK.md)。该入口复用官方约束解码流程，记录模型与数据版本、逐题输出、耗时、显存和路径核对结果。

页面支持 URL 参数定位：`?q=0&mode=constrained&step=6&theme=light`。

## 结果

| 模式 | 路径可在图中核对 | 被 trie 强行改写的解码步 |
|---|---|---|
| 图约束解码 (GCR) | 4 / 4 | 6 / 37 |
| 自由解码 | 0 / 4 | — |

自由解码的 4 条路径都包含图中不存在的边（Philadelphia、Harvard University、
Spanish language、North America）。注意一个细节：**打分表里这些错误的答案分数
更高**。约束并没有让模型变"聪明"，它只是让错误的 token 无法被采样到——
这正是论文所谓"零推理幻觉"的确切含义，也是它的边界。

## 文件

| 文件 | 作用 |
|---|---|
| `gcr_lab/kb.py` | 手写知识图谱 + 题目，路径枚举（简单路径，最多 K 跳） |
| `gcr_lab/trie.py` | KG-Trie：`get(prefix)` 返回合法下一 token，与官方 `src/trie.py` 同契约 |
| `gcr_lab/toy_lm.py` | 透明的"语言模型"：按 槽位/关系/答案 打分，含不在图中的答案 |
| `gcr_lab/decoder.py` | 约束解码循环 + trace + 把输出还原成三元组并核对 |
| `gcr_lab/demo.py` | 跑全部题目，导出 trace |
| `gcr_lab/make_html.py` | 生成单文件可视化页面 |

## 和官方实现的对应关系

官方 `GraphConstrainedDecoding.allowed_tokens_fn` 在 `<PATH>` 内调用
`self.trie.get(sent[L_input:])` 取合法 token，其余 token 的 logits 置
`-inf`；`</PATH>` 之后回到无约束。这里的 `Decoder.decode` 是同一逻辑的
可读版本，唯一区别是多了"候选为空时回退到全词表"的记录（官方代码也有这个
回退，见 `graph_constrained_decoding.py:44`）。
