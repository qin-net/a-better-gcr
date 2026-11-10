"""Build the denser 10-page supervisor edition without changing the original.

Markdown is the content source. Local raster fallback (no image API configured),
with identical slide PNGs in PPTX/PDF and editable speaker notes.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import re
from io import BytesIO
from zipfile import ZipFile

from PIL import Image, ImageDraw, ImageFont
import pymupdf
from pptx import Presentation
from pptx.util import Inches

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / 'images'
NAME = '知识图谱问答_导师汇报版_10页_2026-11-09'
W, H = 1920, 1080
INK, BLUE, MUTED = '#172536', '#003DA5', '#566577'
BG, PALE, LINE = '#F6F8FB', '#E7EEF9', '#D7DFE9'
FONT = '/System/Library/Fonts/Hiragino Sans GB.ttc'
checks = []


def wrap(value, width, size):
    value = str(value).replace('−', '-').replace('~', '\n')
    font = ImageFont.truetype(FONT, size)
    lines = []
    for paragraph in value.split('\n'):
        line = ''
        # Keep numeric values and short Latin identifiers intact across lines.
        for char in re.findall(r'[A-Za-z0-9][A-Za-z0-9_.,%/+-]*|.', paragraph):
            if line and draw.textlength(line + char, font=font) > width:
                if len(char) == 1 and char in '。，；：！？、）】》”’%' and len(line) > 1:
                    lines.append(line[:-1])
                    line = line[-1] + char
                else:
                    lines.append(line)
                    line = char
            else:
                line += char
        lines.append(line)
    return font, lines


def text(value, box, size=32, color=INK, minimum=None):
    x, y, width, height = box
    minimum = size if minimum is None else minimum
    for actual in range(size, minimum-1, -1):
        font, lines = wrap(value, width, actual)
        step = round(actual * 1.37)
        if len(lines)*step <= height:
            break
    else:
        raise ValueError(f'Page {page}: text overflow: {value}')
    assert 0 <= x and 0 <= y and x+width <= W and y+height <= H
    for i, line in enumerate(lines):
        draw.text((x, y+i*step), line, fill=color, font=font, anchor='lt')
    checks.append({'page': page, 'text': value, 'size_px': actual,
                   'box': box, 'lines': len(lines), 'used_height': len(lines)*step})


def rect(box, fill):
    draw.rectangle(box, fill=fill)


def base(data):
    rect((0, 0, W, 12), BLUE)
    text(data['标签'], (80, 44, 1620, 42), 25, BLUE)
    text(f'{page:02d} / 10', (1700, 44, 160, 42), 25, BLUE)
    text(data['title'], (80, 112, 1760, 78), 50, minimum=47)
    draw.line((80, 210, 1840, 210), fill=LINE, width=2)
    text(data['摘要'], (82, 230, 1756, 83), 30, MUTED, minimum=29)
    rect((80, 939, 1840, 1007), PALE)
    rect((80, 939, 89, 1007), BLUE)
    text(data['提示'], (107, 957, 1705, 44), 28, BLUE, minimum=25)
    text(data['来源'], (82, 1026, 1755, 37), 19, MUTED)


def grid(items):
    assert len(items) == 4
    for i, (heading, body) in enumerate(items):
        x, y = 80+(i % 2)*896, 327+(i // 2)*300
        rect((x, y, x+864, y+280), '#FFFFFF')
        rect((x, y, x+5, y+280), BLUE)
        text(heading, (x+25, y+21, 816, 52), 33, BLUE, minimum=30)
        text(body, (x+25, y+84, 816, 180), 31, minimum=28)


def rows(items):
    assert len(items) == 3
    for i, (heading, body) in enumerate(items):
        y = 327+i*200
        rect((80, y, 1840, y+181), '#FFFFFF')
        rect((80, y, 494, y+181), PALE)
        text(heading, (104, y+26, 366, 140), 34, BLUE, minimum=31)
        text(body, (524, y+15, 1288, 164), 32, minimum=29)


def table(headers, data, widths, row_height):
    y = 326
    rect((80, y, 1840, y+64), BLUE)
    x = 80
    for label, width in zip(headers, widths):
        text(label, (x+22, y+16, width-44, 46), 29, '#FFFFFF', minimum=27)
        x += width
    for i, row in enumerate(data):
        y = 390+i*row_height
        rect((80, y, 1840, y+row_height), '#FFFFFF' if i % 2 == 0 else PALE)
        x = 80
        for col, (value, width) in enumerate(zip(row, widths)):
            text(value, (x+22, y+23, width-44, row_height-28), 34,
                 BLUE if col == 1 else INK, minimum=31)
            x += width


def lower_cards(items, top, height):
    for i, (heading, body) in enumerate(items):
        x = 80+i*896
        rect((x, top, x+864, top+height), '#FFFFFF')
        text(heading, (x+24, top+19, 816, 50), 32, BLUE, minimum=30)
        text(body, (x+24, top+80, 816, height-94), 31, minimum=29)


converter = Path('/Users/zhaoshuyang.7/.agents/skills/gpt-image2-ppt-skills/scripts/md_to_plan.py')
spec = importlib.util.spec_from_file_location('md_to_plan', converter)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
plan = module.md_to_plan((HERE / 'slides_plan.md').read_text())
plan['_generated'] = '由slides_plan.md派生；修改Markdown后重建，不直接编辑JSON。'
slides = []
for item in plan['slides']:
    title, _, body = item['content'].partition('\n')
    data = {'title': title, 'items': [], 'table': []}
    for line in body.splitlines():
        if '：' not in line:
            continue
        key, value = line.split('：', 1)
        if key == '条目':
            data['items'].append(value.split('｜', 1))
        elif key == '表行':
            data['table'].append(value.split('｜'))
        elif key == '表头':
            data['headers'] = value.split('｜')
        else:
            data[key] = value
    item['slide_spec'] = {'layout': data['版式'], 'elements': {
        'title': {'type': 'text', 'content': title},
        'summary': {'type': 'text', 'content': data['摘要']},
        **{f'item_{n}': {'type': 'text', 'heading': h, 'body': b}
           for n, (h, b) in enumerate(data['items'], 1)},
        'table': {'type': 'table', 'headers': data.get('headers', []), 'rows': data['table']},
        'takeaway': {'type': 'text', 'content': data['提示']}}}
    slides.append(data)
assert len(slides) == 10
OUT.mkdir(exist_ok=True)
(HERE/'slides_plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2)+'\n')

prs = Presentation()
prs.slide_width = Inches(13.333333)
prs.slide_height = Inches(7.5)
prs.core_properties.title = plan['title']
prs.core_properties.author = 'JoyCode'
prs.core_properties.subject = '导师汇报版：问题—方案—过程—结果；10页'
pdf = pymupdf.open()
notes = ['# 导师汇报版逐页讲稿\n\n10页，建议约15分钟；每页讲稿同时写入PPT备注。\n']
for page, data in enumerate(slides, 1):
    canvas = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(canvas)
    base(data)
    layout = data['版式']
    if layout == 'grid':
        grid(data['items'])
    elif layout == 'rows':
        rows(data['items'])
    elif layout == 'results':
        table(data['headers'], data['table'], [650, 240, 530, 340], 81)
        lower_cards(data['items'], 731, 194)
    elif layout == 'completion':
        table(data['headers'], data['table'], [630, 310, 360, 460], 78)
        lower_cards(data['items'], 644, 281)
    else:
        raise ValueError(layout)
    path = OUT/f'slide-{page:02d}.png'
    canvas.save(path)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_picture(str(path), 0, 0, width=prs.slide_width, height=prs.slide_height)
    slide.notes_slide.notes_text_frame.text = f"{data['title']}\n\n{data['讲稿']}\n\n{data['来源']}"
    p = pdf.new_page(width=960, height=540)
    p.insert_image(p.rect, filename=str(path))
    notes.append(f"## {page:02d}. {data['title']}\n\n{data['讲稿']}\n\n来源：{data['来源']}\n")

prs.save(HERE/f'{NAME}.pptx')
pdf.set_metadata({'title': plan['title'], 'author': 'JoyCode'})
pdf.save(HERE/f'{NAME}.pdf', deflate=True)
pdf.close()
(HERE/'逐页讲稿.md').write_text('\n'.join(notes))
for group in range(3):
    sheet = Image.new('RGB', (1920, 1080), LINE)
    for j in range(4):
        number = group*4+j+1
        if number > 10:
            break
        img = Image.open(OUT/f'slide-{number:02d}.png')
        img.thumbnail((940, 529))
        sheet.paste(img, ((j % 2)*960+10, (j//2)*540+5))
    sheet.save(HERE/f'预览-{group+1}.png')

sources = {
    '1': ['gcr-lab/experiments/FINDINGS.md'],
    '2': ['gcr-lab/experiments/cuda_results/FULL_SEEDS_REPORT.md'],
    '3': ['AI审阅报告_2026-11-08.md', 'gcr-lab/STATUS_AND_NEXT.md'],
    '4': ['2410.13080v2.pdf'],
    '5': ['汇报/2026-11-09/原论文与我们的方法对照.md'],
    '6': ['gcr-lab/train_variants/build_v2.py', 'gcr-lab/train_variants/data/v2_stats.json',
          'graph-constrained-reasoning/src/multi_relation_graph.py'],
    '7': ['graph-constrained-reasoning/workflow/score_faithfulness.py',
          'graph-constrained-reasoning/workflow/run_full_seeds.py'],
    '8': ['gcr-lab/experiments/cuda_results/cwq_completion_500/comparison.json',
          'gcr-lab/experiments/y_completion_eval.py'],
    '9': ['gcr-lab/eval/ai_review_2026-11-08/summary.json',
          'gcr-lab/eval/ai_review_2026-11-08/judgments.jsonl',
          'gcr-lab/eval/ai_review_2026-11-08/dataset_anomalies.json'],
}
index = {key: [{'path': path, 'sha256': hashlib.sha256((ROOT/path).read_bytes()).hexdigest()}
               for path in paths] for key, paths in sources.items()}
(HERE/'证据索引.json').write_text(json.dumps(index, ensure_ascii=False, indent=2)+'\n')

# Verify package integrity, exact image payloads, notes, and PDF image content.
with ZipFile(HERE/f'{NAME}.pptx') as package:
    assert package.testzip() is None
loaded = Presentation(HERE/f'{NAME}.pptx')
assert len(loaded.slides) == 10
assert abs(loaded.slide_width/loaded.slide_height-16/9) < 1e-6
pdf = pymupdf.open(HERE/f'{NAME}.pdf')
assert len(pdf) == 10
for i, slide in enumerate(loaded.slides):
    assert len(slide.shapes) == 1
    payload = (OUT/f'slide-{i+1:02d}.png').read_bytes()
    assert slide.shapes[0].image.blob == payload
    assert slides[i]['讲稿'] in slide.notes_slide.notes_text_frame.text
    images = pdf[i].get_images()
    assert len(images) == 1
    extracted = pdf.extract_image(images[0][0])['image']
    assert Image.open(BytesIO(extracted)).convert('RGB').tobytes() == Image.open(BytesIO(payload)).convert('RGB').tobytes()
pdf[5].get_pixmap(matrix=pymupdf.Matrix(2, 2)).save(HERE/'PDF验证-第6页.png')
pdf.close()
report = {'pages': 10, 'canvas': [W, H], 'overflow': 0, 'text_boxes': len(checks),
          'backend': 'Pillow local fallback; image-based PPTX/PDF',
          'visual_review': 'pending', 'pptx_zip': 'passed', 'exact_embedded_images': 'passed',
          'speaker_notes': 'passed', 'pdf_image_pixels': 'passed',
          'powerpoint_keynote_rerender': 'not performed; exact full-page images checked instead',
          'checks': checks}
(HERE/'排版检查.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
print(f'已生成并通过结构检查：{HERE/NAME}，10页；待逐页视觉检查。')
