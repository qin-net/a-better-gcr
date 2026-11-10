"""Build a blinded, stratified pilot review from full-set predictions.

Run with the production scorer's dependencies; see eval/BLIND_REVIEW.md.
No labels are filled automatically. The output directory must not exist.
"""
import argparse
import csv
import hashlib
import json
import random
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq

LAB = Path(__file__).resolve().parents[1]
ROOT = LAB.parent
sys.path.insert(0, str(ROOT / 'graph-constrained-reasoning' / 'workflow'))
import score_faithfulness as sf

PAIRS = {42: ('C2', 'A_multi'), 43: ('C2_s43', 'A_multi_s43'), 44: ('C2_s44', 'A_multi_s44')}
DATASETS = {'webqsp_1628': 1628, 'cwq_3531': 3531}
STRATA = ('gain', 'loss', 'both_pass', 'both_fail')


def read_predictions(path, expected):
    rows = [json.loads(line) for line in path.open(encoding='utf-8')]
    ids = [r['id'] for r in rows]
    if len(rows) != expected or len(set(ids)) != expected:
        raise ValueError(f'{path}: incomplete or duplicate question IDs')
    if any(len(r['prediction']) != len(r['path_audit']) for r in rows):
        raise ValueError(f'{path}: candidate/audit length mismatch')
    return {r['id']: r for r in rows}


def stratum(c, a):
    return {(True, False): 'gain', (False, True): 'loss',
            (True, True): 'both_pass', (False, False): 'both_fail'}[bool(c), bool(a)]


def pick_cases(runs, labels, per_stratum, rng):
    """Assign one training seed before stratifying, then sample unique families."""
    pools = {s: [] for s in STRATA}
    for qid in sorted(runs['C2']):
        seed = rng.choice(list(PAIRS))
        c, a = PAIRS[seed]
        s = stratum(labels[c][qid]['faithful_strict_hit'], labels[a][qid]['faithful_strict_hit'])
        pools[s].append({'qid': qid, 'seed': seed, 'stratum': s})
    counts = {s: len(rows) for s, rows in pools.items()}
    selected, used = [], set()
    # Rare strata first, without reusing a CWQ rewrite family within a dataset.
    for s in sorted(STRATA, key=lambda s: counts[s]):
        rng.shuffle(pools[s])
        chosen = 0
        for case in pools[s]:
            family = case['qid'].split('_')[0]
            if family in used:
                continue
            selected.append(case)
            used.add(family)
            chosen += 1
            if chosen == per_stratum:
                break
        if chosen != per_stratum:
            raise ValueError(f'{s}: only {chosen} distinct families available')
    return selected, counts


def references(selected):
    wanted = {c['qid'] for c in selected}
    queries = {}
    for q in json.loads((LAB / 'data/webqsp_raw/WebQSP/data/WebQSP.test.json').read_text())['Questions']:
        if q['QuestionId'] in wanted:
            queries[q['QuestionId']] = [p['Sparql'] or '' for p in q['Parses']]
    for q in pq.read_table(LAB / 'data/hf/cwq_sparql_test.parquet', columns=['ID', 'sparql']).to_pylist():
        if q['ID'] in wanted:
            queries[q['ID']] = [q['sparql'] or '']
    graphs = {}
    paths = [LAB / 'data/hf/test.parquet', *sorted((LAB / 'data/hf/cwq_eval').glob('test-*.parquet'))]
    for path in paths:
        pf = pq.ParquetFile(path)
        for batch in pf.iter_batches(batch_size=32, columns=['id', 'q_entity', 'graph']):
            for row in batch.to_pylist():
                if row['id'] in wanted:
                    graphs[row['id']] = row
    if wanted - queries.keys() or wanted - graphs.keys():
        raise ValueError('Missing original query or graph for selected questions')
    return queries, graphs


def block(text):
    # Longer than any backtick run in the source, preserving arbitrary model text.
    fence = '`' * (max([len(s) for s in re.findall(r'`+', text)] + [2]) + 1)
    return f'{fence}text\n{text}\n{fence}\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--per-stratum', type=int, default=10)
    parser.add_argument('--seed', type=int, default=20261108)
    args = parser.parse_args()
    if args.per_stratum < 1:
        parser.error('--per-stratum must be positive')
    if args.output.exists():
        parser.error('Output exists; choose a new directory to preserve reviews')
    rng = random.Random(args.seed)
    gold = sf.load_gold(sf.DEFAULT_GOLD)
    canon, shortcuts = sf.load_criterion(sf.DEFAULT_CRITERION)
    selected, all_runs, all_labels, inventory, hashes = [], {}, {}, {}, {}
    for ds, expected in DATASETS.items():
        runs, labels = {}, {}
        for pair in PAIRS.values():
            for name in pair:
                path = LAB / 'experiments/cuda_results/v2' / ds / name / 'predictions.jsonl'
                runs[name] = read_predictions(path, expected)
                _, questions, _, missing = sf.score_questions(path, gold, canon, shortcuts)
                labels[name] = {q['id']: q for q in questions}
                if missing or set(labels[name]) != set(runs[name]):
                    raise ValueError(f'{path}: incomplete scoring coverage')
                hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        ids = set(runs['C2'])
        for qid in ids:
            for name in runs:
                if qid not in runs[name] or any(runs[name][qid][k] != runs['C2'][qid][k]
                                               for k in ('question', 'ground_truth')):
                    raise ValueError(f'{ds}/{name}/{qid}: questions or gold answers differ')
        cases, counts = pick_cases(runs, labels, args.per_stratum, rng)
        selected.extend(dict(c, dataset=ds) for c in cases)
        all_runs[ds], all_labels[ds], inventory[ds] = runs, labels, counts
        print(ds, 'selected', len(cases), 'population', counts, flush=True)
    queries, graphs = references(selected)
    rng.shuffle(selected)
    docs = ['# 推理路径盲审题册\n', '先读同目录的「审阅说明.md」。不要打开 private 目录。所有标签由审阅者独立填写。\n']
    key, blanks = [], []
    for i, case in enumerate(selected, 1):
        case_id = f'R{i:03d}'
        ds, qid = case['dataset'], case['qid']
        names = list(PAIRS[case['seed']])
        rng.shuffle(names)
        source = all_runs[ds][names[0]][qid]
        docs.extend([f'## {case_id}\n', '题目：\n' + block(source['question']),
                     '题库参考答案（标注也可能有错）：\n' + block(' / '.join(source['ground_truth'])),
                     '问题起点：\n' + block(' / '.join(graphs[qid]['q_entity']))])
        mapping = {}
        for side, name in zip(('甲', '乙'), names):
            row = all_runs[ds][name][qid]
            mapping[side] = {'run': name, 'automatic': all_labels[ds][name][qid]}
            docs.append(f'### 方案{side}\n')
            for j, (prediction, audit) in enumerate(zip(row['prediction'], row['path_audit']), 1):
                docs.extend([f'候选 {j}（完整原始输出）：\n', block(prediction)])
                pairs = {frozenset((h, t)) for h, _, t in sf.path_steps(audit.get('path', ''))}
                edges = sorted({tuple(e) for e in graphs[qid]['graph'] if frozenset((e[0], e[2])) in pairs})
                docs.extend(['原子图中这些节点对之间的事实（保留存储方向；不是完整子图）：\n',
                             block('\n'.join(' -> '.join(e) for e in edges) or '未找到对应事实。')])
                blanks.append({'case_id': case_id, 'side': side, 'candidate': j,
                               'answer_correct': '', 'path_sufficient': '', 'error_tags': '', 'reason': ''})
        docs.extend(['### 题库原始查询（辅助核对条件，不是自动评分结果）\n',
                     *[block(q) for q in queries[qid]],
                     '如需完整子图、日期比较或无法辨认的实体信息，请记“证据不足”，不要靠猜测补全。\n'])
        key.append(dict(case, case_id=case_id, mapping=mapping))
    manifest = {'sampling_seed': args.seed, 'per_stratum': args.per_stratum,
                'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'population_after_random_training_seed_assignment': inventory,
                'selected': len(key), 'training_seed_counts': dict(Counter(c['seed'] for c in key)),
                'sha256': hashes}
    for path in (Path(__file__), Path(sf.__file__), sf.DEFAULT_GOLD, sf.DEFAULT_CRITERION):
        hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    args.output.mkdir(parents=True, exist_ok=False)
    private = args.output / 'private'
    private.mkdir()
    (args.output / '题册.md').write_text('\n'.join(docs), encoding='utf-8')
    (args.output / '审阅说明.md').write_text((LAB / 'eval/BLIND_REVIEW.md').read_text(encoding='utf-8'), encoding='utf-8')
    for reviewer in ('审阅者1', '审阅者2'):
        with (args.output / f'{reviewer}.csv').open('w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=list(blanks[0]))
            writer.writeheader()
            writer.writerows(blanks)
    (private / 'key.json').write_text(json.dumps(key, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (private / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(key)} cases, {len(blanks)} candidate rows per reviewer -> {args.output}', flush=True)


if __name__ == '__main__':
    main()
