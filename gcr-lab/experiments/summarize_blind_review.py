"""Summarize frozen AI judgments after revealing paired method identities.

No model scoring or label generation happens here. The original human forms
remain blank. Only descriptive stratum counts are reported, not population
effect estimates or significance tests from this diagnostic sample.
"""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIELDS = ('answer_correct', 'path_sufficient', 'error_tags', 'reason')


def joint(labels):
    if any(a == p == '是' for a, p, *_ in labels):
        return '通过'
    if any('否' not in (a, p) for a, p, *_ in labels):
        return '不确定'
    return '未通过'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--packet', type=Path, default=ROOT / 'gcr-lab/out/blind_review_2026-11-08')
    ap.add_argument('--review', type=Path, default=ROOT / 'gcr-lab/eval/ai_review_2026-11-08')
    args = ap.parse_args()
    outputs = [args.review / name for name in ('AI逐条审阅.csv', 'AI逐题详解.md', 'summary.json')]
    if any(p.exists() for p in outputs):
        ap.error('Output exists; preserve the completed review instead of overwriting it')
    frozen = json.loads((args.review / 'frozen.json').read_text())
    for path, digest in frozen['files'].items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Frozen input changed: {path}')
    judgments = [json.loads(s) for s in (args.review / 'judgments.jsonl').read_text().splitlines()]
    labels = {r['case_id']: r['labels'] for r in judgments}
    if len(labels) != len(judgments):
        raise ValueError('Duplicate review IDs')
    # Reveal only after the frozen inputs have been validated.
    key_path = args.packet / 'private/key.json'
    key = json.loads(key_path.read_text())
    if set(labels) != {r['case_id'] for r in key}:
        raise ValueError('Review/packet ID mismatch')
    book = (args.packet / '题册.md').read_text()
    parts = re.split(r'(?m)^## (R\d+)\n', book)
    pages = dict(zip(parts[1::2], parts[2::2]))
    counts, cases, flat = defaultdict(Counter), [], []
    docs = ['# AI逐题审阅详解\n',
            '单轮AI初审，不是人工标签。原始材料、判定理由与揭晓后的方法身份如下；'
            '身份是在320条标签写完并固定文件指纹后用于汇总的。\n',
            '通过＝至少一个同一候选的答案正确且路径充分；不确定不强行记为错。'
            '此处评价单条候选，不能替代多路径联合推理或全题库收益评估。\n']
    for item in key:
        case_id = item['case_id']
        page = pages[case_id]
        prediction_blocks = re.findall(r'```text\n(# Reasoning Path:.*?)\n```', page, re.S)
        ls = labels[case_id]
        if len(ls) != 4 or len(prediction_blocks) != 4:
            raise ValueError(f'{case_id}: expected four candidate labels and predictions')
        question = re.search(r'题目：\s*```text\n(.*?)\n```', page, re.S).group(1)
        sides = {}
        docs += [f'## {case_id} 判定\n', f'题库：{item["dataset"]}；训练版本：{item["seed"]}；自动分组：{item["stratum"]}。\n']
        for side, offset in (('甲', 0), ('乙', 2)):
            mapping = item['mapping'][side]
            selected = ls[offset:offset + 2]
            if any(len(row) != 4 or any(v not in ('是', '否', '不确定') for v in row[:2]) for row in selected):
                raise ValueError(f'{case_id}: invalid judgment')
            status = joint(selected)
            auto = bool(mapping['automatic']['faithful_strict_hit'])
            arm = 'C2' if mapping['run'].startswith('C2') else 'A_multi'
            sides[arm] = {'side': side, 'status': status, 'automatic_pass': auto}
            counts[(item['dataset'], 'auto_pass' if auto else 'auto_fail')][status] += 1
            docs.append(f'### {side}：{mapping["run"]}；自动指标：{"通过" if auto else "未通过"}；AI单路径审阅：{status}\n')
            for j, row in enumerate(selected, 1):
                flat.append(dict(case_id=case_id, side=side, candidate=j, dataset=item['dataset'],
                                 run=mapping['run'], question=question,
                                 prediction=prediction_blocks[offset+j-1], **dict(zip(FIELDS, row))))
                docs.append(f'- 候选{j}：答案{row[0]}；路径充分性{row[1]}。标签：{row[2]}。{row[3]}\n')
        c, a = sides['C2']['status'], sides['A_multi']['status']
        outcome = ('不确定' if '不确定' in (c, a) else
                   '改善' if c == '通过' and a != '通过' else
                   '退步' if a == '通过' and c != '通过' else
                   '均通过' if c == '通过' else '均未通过')
        counts[(item['dataset'], item['stratum'])][outcome] += 1
        cases.append(dict(case_id=case_id, dataset=item['dataset'], qid=item['qid'], seed=item['seed'],
                          stratum=item['stratum'], outcome=outcome, arms=sides,
                          tags=sorted({tag for row in ls for tag in row[2].split(';')})))
        docs.append(page)
    summary = {'review_type': 'AI单轮诊断审阅，非人工，非全题库效果估计',
               'n_cases': len(cases), 'n_candidates': len(flat),
               'counts': {f'{ds}/{group}': dict(c) for (ds, group), c in sorted(counts.items())},
               'cases': cases,
               'key_sha256': hashlib.sha256(key_path.read_bytes()).hexdigest(),
               'label_sha256': hashlib.sha256((args.review / 'judgments.jsonl').read_bytes()).hexdigest()}
    with outputs[0].open('x', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
    with outputs[1].open('x', encoding='utf-8') as f:
        f.write('\n'.join(docs))
    with outputs[2].open('x', encoding='utf-8') as f:
        f.write(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary['counts'], ensure_ascii=False, indent=2))
    print(f'{len(cases)} cases, {len(flat)} candidates; outputs: {args.review}')


if __name__ == '__main__':
    main()
