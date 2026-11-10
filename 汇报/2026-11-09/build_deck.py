"""Render the reviewed Markdown as deterministic slide images, PPTX and PDF.

Local fallback: no image API is configured. Text and charts are rasterized
together for portable Chinese typography; speaker notes remain real text.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import re
import sys

from PIL import Image, ImageDraw, ImageFont
import pymupdf
from pptx import Presentation
from pptx.util import Inches

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
W, H = 1920, 1080
BG, INK, MUTED = '#F7F8FA', '#172536', '#566577'
BLUE, PALE, LINE = '#003DA5', '#E7EEF9', '#D7DFE9'
FONT = '/System/Library/Fonts/Hiragino Sans GB.ttc'
LATIN = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'
OUT = HERE / 'images'
OUT.mkdir(exist_ok=True)
checks = []


def font(size, number=False):
    return ImageFont.truetype(LATIN if number else FONT, size)


def rect(box, fill):
    draw.rectangle(box, fill=fill)


def text(s, x, y, width, size=36, color=INK, height=500, number=False):
    s = str(s).replace('−', '-')
    f = font(size, number and not re.search(r'[\u3400-\u9fff]', s))
    lines = []
    for para in s.split('\n'):
        line = ''
        for c in para:
            if line and draw.textlength(line + c, font=f) > width:
                if c in '。，；：！？、）】》”’%' and len(line) > 1:
                    lines.append(line[:-1])
                    line = line[-1] + c
                else:
                    lines.append(line)
                    line = c
            else:
                line += c
        lines.append(line)
    step = int(size * 1.45)
    used = len(lines) * step
    assert used <= height, (page, s, used, height)
    assert x >= 0 and y >= 0 and x + width <= W and y + used <= H
    for line in lines:
        draw.text((x, y), line, fill=color, font=f, anchor='lt')
        y += step
    checks.append(dict(page=page, text=s, x=x, bottom=y, lines=len(lines)))
    return used


def rule(y, x=92, right=1828, color=LINE):
    draw.line((x, y, right, y), fill=color, width=2)


def base(d):
    text(d['标签'], 94, 54, 1540, 25, BLUE, 50)
    text(f'{page:02d}', 1742, 48, 85, 30, BLUE, 60, True)
    text(d['title'], 92, 124, 1736, 53, INK, 154)
    text(d['摘要'], 94, 264, 1730, 30, MUTED, 88)
    rule(1014)
    text(d['来源'], 94, 1030, 1610, 19, MUTED, 34)


def takeaway(d):
    rect((92, 916, 1828, 992), PALE)
    rect((92, 916, 101, 992), BLUE)
    text(d['提示'], 124, 935, 1656, 26, BLUE, 50)


def rows(items, top=366):
    gap = 24
    h = min(151, (520 - gap * (len(items)-1)) // len(items))
    for i, (head, body) in enumerate(items):
        y = top + i * (h + gap)
        rect((92, y, 1828, y+h), '#FFFFFF')
        text(f'{i+1:02d}', 119, y+22, 80, 36, BLUE, 70, True)
        head = re.sub(r'^\d+\s+', '', head)
        text(head, 228, y+18, 500, 32, INK, h-20)
        text(body, 752, y+18, 1022, 31, MUTED, h-18)


def metric_cards(items):
    for i,(head,body) in enumerate(items):
        x=92+i*590
        rect((x,370,x+556,865),'#FFFFFF')
        rect((x,370,x+556,381),BLUE)
        text(head,x+30,423,496,76,BLUE,120,True)
        rule(551,x+30,x+526)
        text(body,x+30,589,496,35,INK,245)


def evidence_cards(items):
    for i,(head,body) in enumerate(items):
        x=92+i*590
        rect((x,370,x+556,868),'#FFFFFF')
        text(f'证据 {i+1:02d}',x+30,399,496,25,BLUE,45)
        text(head,x+30,462,496,34,INK,109)
        rule(586,x+30,x+526)
        text(body,x+30,626,496,32,MUTED,200)


def chart_gaps():
    for y,label,pct in [(382,'CWQ',19.3),(579,'WebQSP',4.4)]:
        text(label,94,y,300,43,INK,75,True)
        text(f'{pct:.1f}%',1490,y,335,59,BLUE,90,True)
        rect((94,y+95,1420,y+133),PALE)
        rect((94,y+95,94+1326*pct/100,y+133),BLUE)
    text('同一比例尺：0%—100%（整条代表全部测试题）',94,755,1430,26,MUTED,50)
    text('CWQ嵌套题型缺口达38.2%，但成因还需逐题核查。',94,822,1710,34,INK,60)


def completion(items):
    rect((92,368,1828,603),'#FFFFFF')
    text('答案命中率',127,402,650,30,MUTED,52)
    text('46.2%  →  47.2%',127,476,1590,79,BLUE,120,True)
    for i,(head,body) in enumerate(items[1:]):
        x=92+i*886
        rect((x,633,x+850,868),'#FFFFFF')
        text(head,x+32,664,786,43,BLUE,76)
        text(body,x+32,752,786,31,INK,105)


def results():
    # Exact rounded estimates and confidence intervals from the final report.
    x0,x1=390,1240
    mapx=lambda v:x0+(v+1)/6*(x1-x0)
    for v in range(-1,6):
        x=mapx(v)
        draw.line((x,406,x,750),fill=LINE,width=2)
        text(str(v),x-20,778,70,27,MUTED,50,True)
    draw.line((mapx(0),392,mapx(0),754),fill=MUTED,width=3)
    for y,label,estimate,lo,hi,p in [(487,'WebQSP',2.4,.8,4.1,'0.0024'),(669,'CWQ',1.8,.2,3.5,'0.032')]:
        text(label,94,y-26,285,41,INK,65,True)
        draw.line((mapx(lo),y,mapx(hi),y),fill=BLUE,width=8)
        for v in (lo,hi): draw.line((mapx(v),y-15,mapx(v),y+15),fill=BLUE,width=4)
        draw.ellipse((mapx(estimate)-12,y-12,mapx(estimate)+12,y+12),fill=BLUE)
        text(f'+{estimate:.1f}  [{lo:+.1f}, {hi:+.1f}]',1300,y-53,513,38,BLUE,66,True)
        text(f'p = {p}',1300,y+10,510,29,MUTED,50,True)
    text('修正忠实命中变化（百分点）；横线表示95%置信区间',94,845,1740,27,MUTED,48)
    text('答案命中率：WebQSP −0.1点 ／ CWQ −1.0点',94,348,1710,32,INK,58)


def audit():
    colors=[BLUE,'#667C9D','#B0C1D9','#E0E5ED']
    labels=['AI判改善','双方未通过','双方通过','不确定']
    for y,ds,values in [(413,'WebQSP',[6,3,0,1]),(627,'CWQ',[2,6,1,1])]:
        text(ds,94,y,370,43,INK,75,True)
        x=458
        for count,c in zip(values,colors):
            if not count: continue
            width=count*133
            rect((x,y,x+width-5,y+94),c)
            text(str(count),x+width/2-15,y+25,45,34,'#FFFFFF' if c in colors[:2] else INK,60,True)
            x+=width
        text('自动判为改善的10题',458,y+114,1230,27,MUTED,50)
    for i,(name,c) in enumerate(zip(labels,colors)):
        x=94+i*440
        rect((x,838,x+24,862),c)
        text(name,x+42,834,350,28,MUTED,49)


def cover(d):
    rect((0,0,W,H),BLUE)
    text(d['标签'],100,74,1600,29,'#FFFFFF',55)
    draw.line((100,162,1816,162),fill='#7098DA',width=2)
    text('从修补训练路径，\n到重新检验推理质量',100,259,1710,86,'#FFFFFF',300)
    text(d['摘要'],104,569,1700,38,'#DCE8FF',75)
    for i,(a,b) in enumerate(d['items']):
        y=727+i*93
        text(a,104,y,250,29,'#AFCBFF',50)
        text(b,384,y,1420,33,'#FFFFFF',60)
    text('2026.11.09  /  14页正文 + 2页附录',104,1000,1700,26,'#DCE8FF',50)


raw=(HERE/'slides_plan.md').read_text()
# Use the skill's Markdown converter; no network/image-generation backend.
converter=Path('/Users/zhaoshuyang.7/.agents/skills/gpt-image2-ppt-skills/scripts/md_to_plan.py')
spec=importlib.util.spec_from_file_location('md_to_plan',converter)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
plan=module.md_to_plan(raw)
plan['_generated']='由slides_plan.md生成；修改文案请编辑Markdown后重建。'
slides=[]
for s in plan['slides']:
    title,_,body=s['content'].partition('\n')
    data=dict(title=title,items=[])
    for line in body.splitlines():
        if '：' not in line: continue
        k,v=line.split('：',1)
        if k=='条目': data['items'].append(v.split('｜',1))
        else: data[k]=v
    slides.append(data)
    s['slide_spec']={'layout':'本地确定性蓝白网格；详见build_deck.py页号分配',
                     'elements':{'title':{'type':'text','content':title},
                                 **{f'item_{i+1}':{'type':'text','heading':a,'body':b} for i,(a,b) in enumerate(data['items'])}}}
(HERE/'slides_plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
assert len(slides)==16

prs=Presentation(); prs.slide_width=Inches(13.333333);prs.slide_height=Inches(7.5)
prs.core_properties.title=plan['title'];prs.core_properties.author='JoyCode'
prs.core_properties.subject='阶段研究汇报；自动指标与完整推理的证据边界'
pdf=pymupdf.open()
notes=['# 逐页讲稿\n\n建议正文约15分钟；第15–16页为答疑附录。\n']
for page,d in enumerate(slides,1):
    canvas=Image.new('RGB',(W,H),BG);draw=ImageDraw.Draw(canvas)
    if page==1: cover(d)
    else:
        base(d)
        if page==4:metric_cards(d['items'])
        elif page==6:chart_gaps()
        elif page==7:completion(d['items'])
        elif page==10:results()
        elif page==11:audit()
        elif page==12:evidence_cards(d['items'])
        else:rows(d['items'])
        takeaway(d)
    path=OUT/f'slide-{page:02}.png';canvas.save(path)
    slide=prs.slides.add_slide(prs.slide_layouts[6])
    slide.shapes.add_picture(str(path),0,0,width=prs.slide_width,height=prs.slide_height)
    slide.notes_slide.notes_text_frame.text=f"{d['title']}\n\n{d['讲稿']}\n\n出处：{d['来源']}"
    p=pdf.new_page(width=960,height=540);p.insert_image(p.rect,filename=str(path))
    notes.append(f"## {page:02}. {d['title']}\n\n{d['讲稿']}\n\n出处：{d['来源']}\n")

name='知识图谱问答_阶段汇报_2026-11-09'
prs.save(str(HERE/f'{name}.pptx'))
pdf.set_metadata({'title':plan['title'],'author':'JoyCode'});pdf.save(HERE/f'{name}.pdf',deflate=True);pdf.close()
(HERE/'逐页讲稿.md').write_text('\n'.join(notes))
for group in range(4):
    sheet=Image.new('RGB',(1920,1080),'#D7DFE9')
    for j in range(4):
        img=Image.open(OUT/f'slide-{group*4+j+1:02}.png');img.thumbnail((940,529))
        sheet.paste(img,((j%2)*960+10,(j//2)*540+5))
    sheet.save(HERE/f'预览-{group+1}.png')

sources=['gcr-lab/experiments/FINDINGS.md','gcr-lab/experiments/cuda_results/FULL_SEEDS_REPORT.md',
         'gcr-lab/STATUS_AND_NEXT.md','AI审阅报告_2026-11-08.md',
         'gcr-lab/eval/ai_review_2026-11-08/summary.json',
         'gcr-lab/eval/ai_review_2026-11-08/judgments.jsonl',
         'gcr-lab/eval/ai_review_2026-11-08/frozen.json',
         'gcr-lab/eval/ai_review_2026-11-08/dataset_anomalies.json',
         'gcr-lab/eval/ai_review_2026-11-08/AI逐题详解.md']
index={'sources':[{ 'path':p,'sha256':hashlib.sha256((ROOT/p).read_bytes()).hexdigest()} for p in sources],
       'as_of':'2026-11-08','presentation_date':'2026-11-09','external_research':False}
(HERE/'证据索引.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
(HERE/'排版检查.json').write_text(json.dumps({'canvas':[W,H],'pages':16,'text_boxes':len(checks),
    'overflow':0,'backend':'Pillow local raster; PNGs embedded in PPTX and PDF',
    'visual_review':'pending','checks':checks},ensure_ascii=False,indent=2)+'\n')
print(f'生成16页PPTX、PDF、PNG与讲稿：{HERE}')
