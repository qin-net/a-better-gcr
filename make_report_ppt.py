#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GCR 论文阅读与复现汇报（学术风格）"""
from pathlib import Path
from lxml import etree
from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

ROOT = Path("/Users/zhaoshuyang/Desktop/mine/paper/knowledge graph")
RES = ROOT / "graph-constrained-reasoning" / "resources"
ASSETS = ROOT / "ppt_assets"
ASSETS.mkdir(exist_ok=True)
OUT = ROOT / "GCR论文阅读与复现汇报.pptx"

NSMAP = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}

NAVY = RGBColor(0x12, 0x2A, 0x4A)
NAVY2 = RGBColor(0x1B, 0x3A, 0x5F)
GOLD = RGBColor(0xB8, 0x96, 0x4E)
CREAM = RGBColor(0xF7, 0xF4, 0xEE)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
INK = RGBColor(0x1E, 0x24, 0x30)
MUTED = RGBColor(0x5C, 0x67, 0x78)
LINE = RGBColor(0xD5, 0xD0, 0xC6)
RED = RGBColor(0x8B, 0x2E, 0x2E)
GREEN = RGBColor(0x2E, 0x5C, 0x45)
CARD = RGBColor(0xF0, 0xEC, 0xE4)

W, H = Inches(13.333), Inches(7.5)
FONT = "PingFang SC"
FONT_EN = "Times New Roman"


def _set_ea(run, name):
    rPr = run._r.get_or_add_rPr()
    for tag in ("latin", "ea", "cs"):
        el = rPr.find(f"{{http://schemas.openxmlformats.org/drawingml/2006/main}}{tag}")
        if el is None:
            el = etree.SubElement(rPr, qn(f"a:{tag}"))
        el.set("typeface", name)


def set_run(run, text, size, color=INK, bold=False, font=FONT):
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = font
    _set_ea(run, font)


def add_text(slide, l, t, w, h, text, size=16, color=INK, bold=False, align=PP_ALIGN.LEFT, font=FONT, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(l, t, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    try:
        tf._txBody.bodyPr.set("anchor", {MSO_ANCHOR.TOP: "t", MSO_ANCHOR.MIDDLE: "ctr", MSO_ANCHOR.BOTTOM: "b"}.get(anchor, "t"))
    except Exception:
        pass
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    set_run(run, text, size, color, bold, font)
    return box


def add_para(tf, text, size=15, color=INK, bold=False, space=6, align=PP_ALIGN.LEFT):
    p = tf.add_paragraph() if tf.paragraphs[0].text or tf.paragraphs[0].runs else tf.paragraphs[0]
    if p.text or p.runs:
        p = tf.add_paragraph()
    p.alignment = align
    p.space_after = Pt(space)
    run = p.add_run()
    set_run(run, text, size, color, bold)
    return p


def rect(slide, l, t, w, h, fill, line=None):
    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, l, t, w, h)
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
        sh.line.width = Pt(0.75)
    sh.shadow.inherit = False
    return sh


def topbar(slide, title, page, total=11):
    rect(slide, 0, 0, W, Inches(0.92), NAVY)
    rect(slide, 0, Inches(0.92), W, Inches(0.06), GOLD)
    add_text(slide, Inches(0.5), Inches(0.22), Inches(11.2), Inches(0.52), title, 22, WHITE, True, anchor=MSO_ANCHOR.MIDDLE)
    add_text(slide, Inches(11.6), Inches(0.28), Inches(1.3), Inches(0.4), f"{page:02d} / {total:02d}", 11, GOLD, False, PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)
    rect(slide, 0, Inches(7.22), W, Inches(0.28), NAVY)
    add_text(slide, Inches(0.5), Inches(7.22), Inches(8), Inches(0.28), "软件学院  ·  论文阅读与复现汇报  ·  ICML 2025", 10, RGBColor(0xC9, 0xD4, 0xE3), False, anchor=MSO_ANCHOR.MIDDLE)
    add_text(slide, Inches(9.2), Inches(7.22), Inches(3.6), Inches(0.28), "GCR  ·  Graph-constrained Reasoning", 10, GOLD, False, PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)


def fit_pic(slide, path, l, t, box_w, box_h):
    im = Image.open(path)
    iw, ih = im.size
    scale = min(box_w / iw, box_h / ih)
    pw, ph = iw * scale, ih * scale
    left = l + (box_w - pw) / 2
    top = t + (box_h - ph) / 2
    slide.shapes.add_picture(str(path), int(left), int(top), int(pw), int(ph))


def caption(slide, l, t, w, text):
    add_text(slide, l, t, w, Inches(0.32), text, 11, MUTED, False, PP_ALIGN.CENTER)


def blank():
    prs = Presentation()
    prs.slide_width = W
    prs.slide_height = H
    return prs, prs.slide_layouts[6]


def make_terminal_shot():
    path = ASSETS / "local_run_terminal.png"
    img = Image.new("RGB", (1600, 720), (18, 32, 52))
    draw = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 28, index=0)
        font = ImageFont.truetype("/Library/Fonts/SF-Mono-Regular.otf", 22)
        font_sm = ImageFont.truetype("/Library/Fonts/SF-Mono-Regular.otf", 18)
    except Exception:
        try:
            font_title = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 26)
            font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Courier New.ttf", 20)
            font_sm = font
        except Exception:
            font_title = font = font_sm = ImageFont.load_default()

    draw.rectangle([0, 0, 1600, 56], fill=(12, 22, 38))
    draw.text((24, 14), "本地复现终端输出  ·  WebQSP test[:20]", fill=(212, 175, 90), font=font_title)

    lines = [
        ("$ python workflow/predict_paths_and_answers.py \\", (214, 220, 228)),
        ("    --d RoG-webqsp  --split 'test[:20]'  --k 2 \\", (168, 178, 190)),
        ("    --model_path rmanluo/GCR-Qwen2-0.5B-Instruct \\", (168, 178, 190)),
        ("    --generation_mode beam  --attn_implementation sdpa  --dtype fp16", (168, 178, 190)),
        ("", (214, 220, 228)),
        ("Save results to:  results/GenPaths/RoG-webqsp/GCR-Qwen2-0.5B-Instruct/test[:20]/...", (140, 160, 150)),
        ("Prepare pipline for inference...", (140, 160, 150)),
        ("100%|████████████████████| 20/20 [00:53<00:00,  2.68s/it]", (120, 190, 150)),
        ("", (214, 220, 228)),
        ("Accuracy: 47.78     Hit: 65.0     F1: 45.69", (232, 208, 140)),
        ("Precision: 52.5     Recall: 47.78", (232, 208, 140)),
        ("Path F1: 43.69      Path Precision: 57.5      Path Recall: 42.66", (200, 188, 150)),
    ]
    y = 88
    for text, color in lines:
        draw.text((36, y), text, fill=color, font=font)
        y += 42
    draw.rectangle([36, 640, 1564, 688], fill=(27, 58, 95))
    note_font = font_title
    try:
        note_font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 22, index=0)
    except Exception:
        pass
    draw.text((48, 652), "说明：0.5B 专用模型 + Trie 约束；未调用第二阶段 ChatGPT。Hit = 13/20。", fill=(247, 244, 238), font=note_font)
    img.save(path, "PNG")
    return path


def build():
    term = make_terminal_shot()
    prs, layout = blank()

    # ---------- 1 封面 ----------
    s = prs.slides.add_slide(layout)
    rect(s, 0, 0, W, H, NAVY)
    rect(s, 0, 0, Inches(0.18), H, GOLD)
    add_text(s, Inches(0.7), Inches(1.15), Inches(12), Inches(0.4), "ICML 2025  ·  arXiv:2410.13080", 16, GOLD, True)
    add_text(s, Inches(0.7), Inches(1.7), Inches(12), Inches(1.4), "知识图谱约束推理\n论文阅读与复现汇报", 40, WHITE, True)
    add_text(s, Inches(0.7), Inches(3.35), Inches(12), Inches(0.7), "Graph-constrained Reasoning: Faithful Reasoning on\nKnowledge Graphs with Large Language Models", 18, RGBColor(0xC9, 0xD4, 0xE3), False, font=FONT_EN)
    rect(s, Inches(0.7), Inches(4.35), Inches(2.2), Inches(0.06), GOLD)
    add_text(s, Inches(0.7), Inches(4.7), Inches(10), Inches(1.4), "汇报人　　赵舒阳\n单　　位　　软件学院\n日　　期　　2026年9月14日", 16, WHITE)
    add_text(s, Inches(0.7), Inches(6.55), Inches(12), Inches(0.4), "本地复现环境：Apple M2 Pro（16 GB）· Qwen2-0.5B · WebQSP 20 条样本", 13, RGBColor(0x9A, 0xAB, 0xC0))

    # ---------- 2 提纲 ----------
    s = prs.slides.add_slide(layout)
    rect(s, 0, 0, W, H, CREAM)
    topbar(s, "汇报提纲", 2)
    items = [
        ("01", "论文定位", "GCR 将知识图谱结构写入大模型解码过程，约束生成路径必须落在真实边上。"),
        ("02", "方法要点", "对比检索式 RAG、智能体走图；KG-Trie + 图约束解码 + 归纳汇总。"),
        ("03", "论文主结果", "WebQSP Hit 92.6%，路径层忠实率 100%（作者 8B + 通用大模型设置）。"),
        ("04", "本地复现", "官方权重 Qwen2-0.5B，Mac 上完成 20 条 WebQSP 推理，Hit 13/20。"),
        ("05", "结论与边界", "路径不编假边，但强依赖图谱质量；更适合已有领域图的垂直场景。"),
    ]
    for i, (num, title, desc) in enumerate(items):
        y = Inches(1.25) + Inches(i * 1.08)
        rect(s, Inches(0.55), y, Inches(12.2), Inches(0.96), WHITE, LINE)
        rect(s, Inches(0.55), y, Inches(0.12), Inches(0.96), GOLD)
        add_text(s, Inches(0.9), y + Inches(0.12), Inches(1.1), Inches(0.7), num, 22, GOLD, True, anchor=MSO_ANCHOR.MIDDLE)
        add_text(s, Inches(2.1), y + Inches(0.12), Inches(10.2), Inches(0.36), title, 18, NAVY, True)
        add_text(s, Inches(2.1), y + Inches(0.48), Inches(10.2), Inches(0.38), desc, 14, MUTED)

    # ---------- 3 论文信息 ----------
    s = prs.slides.add_slide(layout)
    rect(s, 0, 0, W, H, CREAM)
    topbar(s, "一、论文信息与阅读任务", 3)
    meta = [
        ("题目", "Graph-constrained Reasoning: Faithful Reasoning on Knowledge Graphs with LLMs"),
        ("会议", "ICML 2025（PMLR 267）"),
        ("作者", "Luo, Zhao, Haffari, Li, Gong, Pan（莫纳什 / 南理工 / 交大 / 格里菲斯）"),
        ("任务", "知识图谱问答（KGQA）：用人话提问，沿图谱真实路径给出答案"),
        ("开源", "github.com/RManLuo/graph-constrained-reasoning"),
        ("本次工作", "精读方法与实验边界；在 Mac 上跑通官方 0.5B 推理脚本并核对案例"),
    ]
    for i, (k, v) in enumerate(meta):
        y = Inches(1.22) + Inches(i * 0.88)
        rect(s, Inches(0.55), y, Inches(12.2), Inches(0.78), WHITE, LINE)
        add_text(s, Inches(0.8), y + Inches(0.18), Inches(1.8), Inches(0.42), k, 15, GOLD, True, anchor=MSO_ANCHOR.MIDDLE)
        add_text(s, Inches(2.7), y + Inches(0.18), Inches(9.7), Inches(0.42), v, 15, INK, False, anchor=MSO_ANCHOR.MIDDLE)

    # ---------- 4 方法总览图 ----------
    s = prs.slides.add_slide(layout)
    rect(s, 0, 0, W, H, CREAM)
    topbar(s, "二、方法总览：三类范式对比", 4)
    fit_pic(s, RES / "GCR.png", Inches(0.4), Inches(1.12), Inches(12.5), Inches(5.7))
    caption(s, Inches(0.5), Inches(6.82), Inches(12.3), "图源：论文 Figure 2 / 官方仓库 resources/GCR.png")

    # ---------- 5 差异说明 ----------
    s = prs.slides.add_slide(layout)
    rect(s, 0, 0, W, H, CREAM)
    topbar(s, "二、与检索式方法的本质差别", 5)
    headers = ["", "（a）检索式 / RAG", "（c）GCR"]
    rows = [
        ["图如何进入模型", "三元组写入 Prompt，作阅读材料", "先枚举真路径，建成 Trie，卡住下一个 token"],
        ["能否写出假边", "可以。模型答题时仍可能无视检索结果", "路径段不能。非法前缀概率置 0"],
        ["谁挑选相关路径", "检索器（向量 / GNN 等）", "微调后的图谱专用小模型"],
        ["第二次模型调用", "通常一次给出答案", "通用大模型对多条真路径做归纳"],
        ["幻觉的含义", "事实与过程都可能编造", "论文所称零幻觉 = 路径能在图上找到"],
    ]
    col_w = [Inches(2.4), Inches(4.85), Inches(4.85)]
    x0 = Inches(0.55)
    y0 = Inches(1.2)
    rh = Inches(0.82)
    for j, h in enumerate(headers):
        x = x0
        for k in range(j):
            x = x + col_w[k]
        rect(s, x, y0, col_w[j], Inches(0.5), NAVY)
        add_text(s, x + Inches(0.08), y0, col_w[j] - Inches(0.1), Inches(0.5), h, 13, WHITE, True, PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    for i, row in enumerate(rows):
        y = y0 + Inches(0.5) + rh * i
        bg = WHITE if i % 2 == 0 else CARD
        for j, cell in enumerate(row):
            x = x0
            for k in range(j):
                x = x + col_w[k]
            rect(s, x, y, col_w[j], rh, bg, LINE)
            color = NAVY if j == 0 else INK
            add_text(s, x + Inches(0.1), y + Inches(0.08), col_w[j] - Inches(0.18), rh - Inches(0.12), cell, 13, color, j == 0, anchor=MSO_ANCHOR.MIDDLE)
    add_text(s, Inches(0.55), Inches(6.55), Inches(12.2), Inches(0.5), "一句话：（a）把图当参考书；（c）把图当成答题卡上的合法选项。假选项被划掉，选错科目仍可能发生。", 14, MUTED)

    # ---------- 6 约束解码示例 ----------
    s = prs.slides.add_slide(layout)
    rect(s, 0, 0, W, H, CREAM)
    topbar(s, "二、图约束解码的输入与输出", 6)
    fit_pic(s, RES / "graph-constrained-decoding.png", Inches(0.5), Inches(1.2), Inches(12.3), Inches(2.4))
    caption(s, Inches(0.5), Inches(3.55), Inches(12.3), "图源：论文 Figure 3。路径写在 <PATH> 与 </PATH> 之间，受 Trie 约束；其后答案段恢复普通解码。")
    notes = [
        "起点实体由数据集给出（或 NER + 实体链接），本方法不把问句拆成子问题。",
        "微调损失（公式 8）是普通的下一个词预测：对着图上的最短路和标准答案学习书写格式。",
        "公式 7 不是损失，是 0/1 开关：前缀在 Trie 中合法为 1，否则为 0。",
        "第二阶段通用大模型不受 Trie 约束，只根据已生成的真路径归纳最终答案。",
    ]
    for i, t in enumerate(notes):
        y = Inches(4.0) + Inches(i * 0.7)
        rect(s, Inches(0.55), y, Inches(12.2), Inches(0.62), WHITE, LINE)
        add_text(s, Inches(0.8), y, Inches(0.4), Inches(0.62), "▸", 16, GOLD, True, anchor=MSO_ANCHOR.MIDDLE)
        add_text(s, Inches(1.25), y, Inches(11.2), Inches(0.62), t, 15, INK, False, anchor=MSO_ANCHOR.MIDDLE)

    # ---------- 7 论文主结果 ----------
    s = prs.slides.add_slide(layout)
    rect(s, 0, 0, W, H, CREAM)
    topbar(s, "三、论文报告的主结果（作者实验）", 7)
    fit_pic(s, RES / "KGQA.png", Inches(0.35), Inches(1.15), Inches(7.6), Inches(5.7))
    fit_pic(s, RES / "faithfulness.png", Inches(8.05), Inches(1.2), Inches(4.85), Inches(3.3))
    caption(s, Inches(8.05), Inches(4.5), Inches(4.85), "Figure 5：去掉约束后，正确样本中忠实路径降至 62.4% / 48.1%")
    rect(s, Inches(8.05), Inches(4.95), Inches(4.85), Inches(1.9), WHITE, LINE)
    tf = s.shapes.add_textbox(Inches(8.2), Inches(5.08), Inches(4.55), Inches(1.7)).text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    run = p.add_run()
    set_run(run, "阅读时需分开的两套数字", 13, GOLD, True)
    add_para(tf, "· 主结果来自 Llama-3.1-8B + ChatGPT / GPT-4o-mini。", 12, INK, False, 4)
    add_para(tf, "· 路径忠实率 100% 由 Trie 硬约束保证。", 12, INK, False, 4)
    add_para(tf, "· 不等于答案永远正确，也不等于图谱本身无缺失。", 12, INK, False, 4)

    # ---------- 8 本地复现设置 + 终端截图 ----------
    s = prs.slides.add_slide(layout)
    rect(s, 0, 0, W, H, CREAM)
    topbar(s, "四、本地复现设置与运行记录", 8)
    fit_pic(s, term, Inches(4.55), Inches(1.18), Inches(8.35), Inches(5.7))
    # left facts
    facts = [
        ("硬件", "Apple M2 Pro，统一内存 16 GB，无 NVIDIA"),
        ("模型", "rmanluo/GCR-Qwen2-0.5B-Instruct（官方公开权重）"),
        ("数据", "HuggingFace RoG-webqsp，test 前 20 条"),
        ("解码", "beam=2，L=2 hop Trie，SDPA，fp16"),
        ("未做", "未跑 8B；未调用第二阶段 ChatGPT"),
        ("耗时", "20 条推理约 53 秒（不含首次下载）"),
    ]
    for i, (k, v) in enumerate(facts):
        y = Inches(1.2) + Inches(i * 0.9)
        rect(s, Inches(0.45), y, Inches(3.95), Inches(0.82), WHITE, LINE)
        add_text(s, Inches(0.6), y + Inches(0.08), Inches(3.65), Inches(0.28), k, 12, GOLD, True)
        add_text(s, Inches(0.6), y + Inches(0.36), Inches(3.65), Inches(0.4), v, 12, INK)

    # ---------- 9 本地结果表 ----------
    s = prs.slides.add_slide(layout)
    rect(s, 0, 0, W, H, CREAM)
    topbar(s, "四、本地 20 条样本结果", 9)
    kpis = [("20", "评测条数"), ("13 / 20", "Hit"), ("65%", "Hit Rate"), ("45.7%", "F1")]
    for i, (n, lab) in enumerate(kpis):
        x = Inches(0.5) + Inches(i * 3.2)
        rect(s, x, Inches(1.18), Inches(3.0), Inches(1.15), WHITE, LINE)
        rect(s, x, Inches(1.18), Inches(0.1), Inches(1.15), GOLD)
        add_text(s, x + Inches(0.25), Inches(1.26), Inches(2.6), Inches(0.58), n, 26, NAVY, True, PP_ALIGN.CENTER)
        add_text(s, x + Inches(0.25), Inches(1.82), Inches(2.6), Inches(0.38), lab, 13, MUTED, False, PP_ALIGN.CENTER)

    # case table
    cases = [
        ("HIT", "牙买加使用何种语言", "Jamaica → languages_spoken → Jamaican English / Creole"),
        ("HIT", "马丁·路德·金遇刺地点", "… → place_of_death → Memphis"),
        ("HIT", "爱伦·坡去世地点", "… → place_of_death → Baltimore"),
        ("MISS", "Ken Barlow 由谁饰演", "走到创作者 Tony Warren，图中缺少演员边"),
        ("MISS", "JaMarcus Russell 来自何处", "走国籍美国 / 阿拉巴马，标准答案为出生地 Mobile"),
        ("MISS", "Anna Bligh 代表选区", "走到 Queensland，标准答案为 South Brisbane 选区"),
    ]
    y = Inches(2.5)
    rect(s, Inches(0.5), y, Inches(12.3), Inches(0.42), NAVY)
    add_text(s, Inches(0.65), y, Inches(1.3), Inches(0.42), "结果", 12, WHITE, True, anchor=MSO_ANCHOR.MIDDLE)
    add_text(s, Inches(2.1), y, Inches(4.2), Inches(0.42), "问题", 12, WHITE, True, anchor=MSO_ANCHOR.MIDDLE)
    add_text(s, Inches(6.4), y, Inches(6.2), Inches(0.42), "路径观察", 12, WHITE, True, anchor=MSO_ANCHOR.MIDDLE)
    for i, (tag, q, obs) in enumerate(cases):
        yy = Inches(2.92) + Inches(i * 0.6)
        bg = WHITE if i % 2 == 0 else CARD
        rect(s, Inches(0.5), yy, Inches(12.3), Inches(0.6), bg, LINE)
        tc = GREEN if tag == "HIT" else RED
        add_text(s, Inches(0.65), yy, Inches(1.3), Inches(0.6), tag, 13, tc, True, anchor=MSO_ANCHOR.MIDDLE)
        add_text(s, Inches(2.1), yy, Inches(4.2), Inches(0.6), q, 13, INK, False, anchor=MSO_ANCHOR.MIDDLE)
        add_text(s, Inches(6.4), yy, Inches(6.2), Inches(0.6), obs, 12, MUTED, False, anchor=MSO_ANCHOR.MIDDLE)
    add_text(s, Inches(0.5), Inches(6.58), Inches(12.3), Inches(0.45), "说明：0.5B、beam=2、无第二阶段大模型，不能与论文 92.6% 直接对比。价值在于验证「路径为真边、错误多为走错真路」。", 12, MUTED)

    # ---------- 10 论文案例对照 ----------
    s = prs.slides.add_slide(layout)
    rect(s, 0, 0, W, H, CREAM)
    topbar(s, "四、与论文案例对照", 10)
    fit_pic(s, RES / "cases.png", Inches(0.4), Inches(1.15), Inches(12.5), Inches(4.55))
    caption(s, Inches(0.5), Inches(5.7), Inches(12.3), "图源：论文 Table 5。无约束时可出现假边；有约束后路径可在图上核对。")
    add_text(s, Inches(0.55), Inches(6.1), Inches(12.2), Inches(0.9), "本地第 4 条即为 Table 5 Case 2 同题（JaMarcus Russell）。0.5B 在约束下未编造 Tampa，但选择了国籍边而非出生地，答案落在 United States / Alabama。这印证：Trie 消除假边，并不能保证选对关系。", 14, INK)

    # ---------- 11 结论 ----------
    s = prs.slides.add_slide(layout)
    rect(s, 0, 0, W, H, CREAM)
    topbar(s, "五、结论与适用边界", 11)
    blocks = [
        ("已完成", GREEN, [
            "完成 ICML 2025 GCR 精读，理清 Trie 约束解码与两阶段模型分工。",
            "在 Mac 上跑通官方开源推理，20 条样本 Hit 13/20。",
            "用真实题目验证：错误主要是真路边走错或图谱缺失，而非凭空编造。",
        ]),
        ("方法判断", GOLD, [
            "比 RAG 更适合「必须核对边是否存在」的问答；路径层更老实。",
            "上限由图决定。图不完整、关系标错，模型只能忠实复述。",
            "适合已有领域图谱的垂直场景（内部知识、术语、法规、馆藏）。",
        ]),
        ("未展开", MUTED, [
            "未复现论文主设置（8B + 通用大模型全量测集）。",
            "建图、实体链接与图谱维护成本不在本文范围内，落地时是主要工作量。",
            "后续可对照 RoG / ToG，或在 Windows 4060 上尝试量化 8B。",
        ]),
    ]
    for i, (title, accent, bullets) in enumerate(blocks):
        x = Inches(0.45) + Inches(i * 4.25)
        rect(s, x, Inches(1.2), Inches(4.05), Inches(5.7), WHITE, LINE)
        rect(s, x, Inches(1.2), Inches(4.05), Inches(0.58), NAVY)
        add_text(s, x, Inches(1.2), Inches(4.05), Inches(0.58), title, 16, WHITE, True, PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        tf = s.shapes.add_textbox(x + Inches(0.18), Inches(2.0), Inches(3.7), Inches(4.6)).text_frame
        tf.word_wrap = True
        first = True
        for b in bullets:
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            p.space_after = Pt(14)
            run = p.add_run()
            set_run(run, "•  " + b, 13, INK)

    prs.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
