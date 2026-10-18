#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = Path("/Users/zhaoshuyang/Desktop/mine/paper/knowledge graph/GCR论文阅读与复现报告.docx")


def set_run(run, name="宋体", size=12, bold=False, color=None, west="Times New Roman"):
    run.bold = bold
    run.font.size = Pt(size)
    run.font.name = west
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    if color:
        run.font.color.rgb = color


def p(doc, text, name="宋体", size=12, bold=False, align="left", first_line=True, space_after=8, space_before=0, color=None):
    para = doc.add_paragraph()
    para.paragraph_format.space_after = Pt(space_after)
    para.paragraph_format.space_before = Pt(space_before)
    para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    if first_line:
        para.paragraph_format.first_line_indent = Cm(0.74)
    if align == "center":
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.first_line_indent = Cm(0)
    elif align == "right":
        para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        para.paragraph_format.first_line_indent = Cm(0)
    else:
        para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    run = para.add_run(text)
    set_run(run, name, size, bold, color)
    return para


def heading(doc, text, level=1):
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    para.paragraph_format.space_before = Pt(14 if level == 1 else 10)
    para.paragraph_format.space_after = Pt(8)
    para.paragraph_format.first_line_indent = Cm(0)
    para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    run = para.add_run(text)
    set_run(run, "黑体", 16 if level == 1 else 14, True, RGBColor(0x12, 0x2A, 0x4A))
    return para


def add_table(doc, headers, rows):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, h in enumerate(headers):
        cell = table.rows[0].cells[j]
        cell.text = ""
        para = cell.paragraphs[0]
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = para.add_run(h)
        set_run(run, "黑体", 10.5, True)
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            cell = table.rows[i + 1].cells[j]
            cell.text = ""
            para = cell.paragraphs[0]
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER if j == 0 else WD_ALIGN_PARAGRAPH.LEFT
            run = para.add_run(val)
            set_run(run, "宋体", 10.5, False)
    doc.add_paragraph().paragraph_format.space_after = Pt(6)


def build():
    doc = Document()
    for sec in doc.sections:
        sec.top_margin = Cm(2.54)
        sec.bottom_margin = Cm(2.54)
        sec.left_margin = Cm(3.17)
        sec.right_margin = Cm(3.17)
        sec.page_width = Cm(21.0)
        sec.page_height = Cm(29.7)

    p(doc, "软件学院", "黑体", 16, False, "center", False, 4)
    p(doc, "论文阅读与复现报告", "黑体", 22, True, "center", False, 12)
    p(doc, "Graph-constrained Reasoning", "Times New Roman", 14, False, "center", False, 4)
    p(doc, "Faithful Reasoning on Knowledge Graphs with Large Language Models", "Times New Roman", 12, False, "center", False, 18)
    p(doc, "汇报人：赵舒阳", "宋体", 12, False, "center", False, 4)
    p(doc, "日期：2026年9月15日", "宋体", 12, False, "center", False, 18)
    p(doc, "（配套幻灯片：GCR论文阅读与复现汇报.pptx）", "宋体", 10.5, False, "center", False, 18, color=RGBColor(0x5C, 0x67, 0x78))

    heading(doc, "一、工作概述", 1)
    p(doc, "本次工作围绕 ICML 2025 论文 Graph-constrained Reasoning（以下简称 GCR，arXiv:2410.13080）展开，完成论文精读与小规模开源复现。论文针对大模型在知识图谱问答中的幻觉问题，提出将图谱结构写入解码过程，使生成的推理路径必须落在真实三元组上。")
    p(doc, "阅读方面，理清了检索式方法、智能体走图与 GCR 三类范式的差别，明确所谓“零幻觉”仅指路径可在图谱中核对，并不等于答案必然正确。复现方面，受本机 Apple M2 Pro（16 GB，无 NVIDIA）限制，未运行论文主实验所用的 Llama-3.1-8B 与 ChatGPT 归纳模块，改用官方公开的 Qwen2-0.5B 图谱专用权重，在 WebQSP 测试集前 20 条上完成图约束解码。结果为 Hit 13/20（65.0%），F1 约 45.7%。该数字不能与论文报告的 WebQSP Hit 92.6% 直接对比，其意义在于验证方法流程可运行，并观察错误类型。")

    heading(doc, "二、论文信息", 1)
    add_table(
        doc,
        ["项目", "内容"],
        [
            ["题目", "Graph-constrained Reasoning: Faithful Reasoning on Knowledge Graphs with Large Language Models"],
            ["会议", "ICML 2025（PMLR 267）"],
            ["作者", "Luo, Zhao, Haffari, Li, Gong, Pan"],
            ["单位", "莫纳什大学、南京理工大学、上海交通大学、格里菲斯大学"],
            ["任务", "知识图谱问答（KGQA）"],
            ["代码", "https://github.com/RManLuo/graph-constrained-reasoning"],
            ["主图谱 / 数据", "Freebase；WebQSP、CWQ（复现使用 RoG-webqsp）"],
        ],
    )

    heading(doc, "三、问题与方法", 1)
    heading(doc, "（一）问题", 2)
    p(doc, "大模型具备逐步推理能力（思维链，Chain-of-Thought），但不保证中间步骤为真。将知识图谱接入后，常见做法有两类：一是检索相关三元组写入提示词（检索式 / RAG）；二是让模型作为智能体在图上逐步查询。前者检索有偏且模型仍可无视检索结果；后者调用次数多、时延长，仍可能生成图中不存在的边。作者前作 RoG 仍报告约 33% 的推理错误。GCR 的目标是：推理路径必须能在图谱中找到。")

    heading(doc, "（二）方法", 2)
    p(doc, "方法分为三步。第一，从问题主题实体出发，枚举有限跳数（主实验为 2 跳）内的真实路径，按分词结果建成前缀树 KG-Trie。该步骤为图算法，不调用大模型。主实验中主题实体由数据集给出；若处理生问题，附录采用 SpaCy 做命名实体识别、ColBERT 做实体链接。")
    p(doc, "第二，用微调后的图谱专用小模型做图约束解码。生成 <PATH> 与 </PATH> 之间的内容时，每一步 token 必须是 Trie 中的合法前缀，非法词概率置零。路径结束后约束松开，模型按普通解码给出假设答案。一次 beam search 可得到 K 条路径及假设答案。公式 7 是该 0/1 开关，不是损失函数。公式 8 才是微调目标：对图上最短路与标准答案做下一个词预测。")
    p(doc, "第三，将 K 条路径交给未针对该任务微调的通用大模型做归纳，得到最终答案。通用模型不再搜图，也不再受 Trie 约束。")

    heading(doc, "（三）与 RAG 的差别", 2)
    p(doc, "检索式方法把图谱内容写成提示词，模型答题时仍可能编造。GCR 并不取消“先从图附近取路”这一步，差别在于取路结果的用法：不当作阅读材料，而作为解码时的合法选项。因此，GCR 杜绝的是写出图上不存在的边，而不是一切错误。路径真实但与问题无关、答案段自由生成、第二阶段归纳出错、图谱本身缺边，都仍可能失败。")

    heading(doc, "四、论文报告的主结果", 1)
    p(doc, "下列数字摘自论文表格，实验设置为微调 Llama-3.1-8B 作为图谱专用模型，并以 ChatGPT 或 GPT-4o-mini 作为归纳模型，不得理解为本次本地复现成绩。")
    add_table(
        doc,
        ["方法", "WebQSP Hit", "WebQSP F1", "CWQ Hit", "CWQ F1"],
        [
            ["RoG (Llama-2-7B)", "85.7", "70.8", "62.6", "56.2"],
            ["GNN-RAG+RA", "90.7", "73.5", "68.7", "60.4"],
            ["GCR + ChatGPT", "92.6", "73.2", "72.7", "60.9"],
            ["GCR + GPT-4o-mini", "92.2", "74.1", "75.8", "61.7"],
        ],
    )
    p(doc, "作者在 WebQSP 上统计：加上约束后，正确预测中的忠实路径比例为 100%；去掉约束后降至 62.4%（CWQ 为 48.1%）。效率方面，GCR 平均约 2 次模型调用、231 个输入 token，相对智能体方法 ToG（约 11.6 次调用、7069 token）更省。论文同时指出：换医学图谱时提升有限；失败案例包括无关真路径与图谱不完整。")

    heading(doc, "五、本地复现", 1)
    heading(doc, "（一）环境与设置", 2)
    add_table(
        doc,
        ["项目", "设置"],
        [
            ["硬件", "Apple M2 Pro，统一内存 16 GB，无 CUDA"],
            ["软件", "Python 3.12，PyTorch 2.14（MPS），transformers 4.44.2"],
            ["模型", "rmanluo/GCR-Qwen2-0.5B-Instruct（官方公开权重）"],
            ["数据", "HuggingFace rmanluo/RoG-webqsp，split=test[:20]"],
            ["解码", "beam=2，index hop L=2，attn=sdpa，dtype=fp16"],
            ["未运行", "Llama-3.1-8B；第二阶段 ChatGPT / GPT-4o-mini；全量测试集"],
        ],
    )
    p(doc, "官方脚本默认依赖 FlashAttention 与 CUDA，本机改为 SDPA。图谱专用模型按模型名中的 “gcr” 走约束解码接口。20 条样本推理耗时约 53 秒（不含首次下载权重与数据）。原始输出见仓库 results/GenPaths/RoG-webqsp/GCR-Qwen2-0.5B-Instruct/test[:20]/ 目录。")

    heading(doc, "（二）定量结果", 2)
    p(doc, "评测由官方脚本 eval_path_result_w_ans 给出。因仅使用小模型假设答案、beam 宽度为 2，且没有归纳模型合并多条路径，成绩低于论文主结果是预期之内的。")
    add_table(
        doc,
        ["指标", "数值"],
        [
            ["样本数", "20"],
            ["Hit", "13 / 20（65.0%）"],
            ["Accuracy", "47.78%"],
            ["F1", "45.69%"],
            ["Precision / Recall", "52.5% / 47.78%"],
            ["Path F1", "43.69%"],
        ],
    )

    heading(doc, "（三）案例", 2)
    p(doc, "正确样本中，路径均为图谱关系，例如：Jamaica → location.country.languages_spoken → Jamaican English；Martin Luther King, Jr. → people.deceased_person.place_of_death → Memphis；Edgar Allan Poe → place_of_death → Baltimore。未见明显伪造实体或伪造关系名。")
    p(doc, "错误更具说明意义，且与论文失败分析一致。问 “who plays ken barlow in coronation street”，起点为剧名，模型走到创作者 Tony Warren，答成 Screenwriter，标准答案为演员 William Roache——论文附录亦以此类题目说明图谱缺失。问 JaMarcus Russell 来自何处（论文 Table 5 同题），标准答案为出生地 Mobile；0.5B 在约束下未编造 Tampa，但选择了国籍边，答成美国或阿拉巴马。问 Anna Bligh 代表选区，模型走到 Queensland，标准答案为 Electoral district of South Brisbane。上述错误的共同特征是：边真实，关系选错或图中没有该问所需的边。")

    heading(doc, "六、结论", 1)
    p(doc, "GCR 的贡献可以概括为：在假定图谱可用的前提下，用前缀树约束解码，把“路径是否在图上”从软约束变成硬约束，再用通用模型归纳多条真路径。它比 RAG 更适合必须核对边是否存在的场景，但更依赖图谱的覆盖与正确性。图越大不等于越好，相关邻域要全、要准；跳数过长会使 Trie 膨胀并引入噪声。")
    p(doc, "因此，该方法更适合已有或值得维护领域图谱的垂直应用，例如企业内部知识、术语体系、法规与馆藏，而不适合开放域、图谱长期盖不全的问答。建图、实体链接与持续更新的成本不在本文实验范围内，落地时往往是主要工作量。")
    p(doc, "本次已完成精读与 0.5B 小样本复现。若需对齐论文主数字，应在具备 CUDA 与足够显存的机器上运行官方 8B 权重，并接入第二阶段通用大模型后评测全量 WebQSP / CWQ。Windows 端 i7 + RTX 4060 可考虑 4bit 量化尝试，但不保证复现论文原设置。")

    heading(doc, "参考文献", 1)
    refs = [
        "Luo L, Zhao Z, Haffari G, et al. Graph-constrained Reasoning: Faithful Reasoning on Knowledge Graphs with Large Language Models[C]//ICML. 2025. arXiv:2410.13080.",
        "Luo L, Li Y F, Haffari G, et al. Reasoning on Graphs: Faithful and Interpretable Large Language Model Reasoning[C]//ICLR. 2024. （RoG）",
        "Sun J, Xu C, Tang L, et al. Think-on-Graph: Deep and Responsible Reasoning of Large Language Model on Knowledge Graph[C]//ICLR. 2024. （ToG）",
        "Mavromatis C, Karypis G. GNN-RAG: Graph Neural Retrieval for Large Language Model Reasoning[J]. 2024.",
        "Wei J, Wang X, Schuurmans D, et al. Chain-of-Thought Prompting Elicits Reasoning in Large Language Models[C]//NeurIPS. 2022.",
    ]
    for i, r in enumerate(refs, 1):
        para = doc.add_paragraph()
        para.paragraph_format.left_indent = Cm(0.74)
        para.paragraph_format.first_line_indent = Cm(-0.74)
        para.paragraph_format.space_after = Pt(4)
        para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        run = para.add_run(f"[{i}] {r}")
        set_run(run, "宋体", 10.5, False)

    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
