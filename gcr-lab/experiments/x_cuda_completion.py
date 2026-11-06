"""Compare local, unconditional, and gated completion with the same C2 adapter."""
import argparse
import json
import pickle
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from huggingface_hub import HfApi, hf_hub_download
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import GroupShuffleSplit

import t_inference_pool as pool_tools
from u_detect_complete import Question, RelationModel, features
from v_rank_completion import MID, search

ROOT = Path(__file__).resolve().parents[2]
GCR = ROOT / 'graph-constrained-reasoning'
CWQ = 'rmanluo/RoG-cwq'
CWQ_REV = 'b0f6275586286312c4e99ef4b0adc65463c91f8e'
WEBQSP = 'rmanluo/RoG-webqsp'
WEBQSP_REV = 'c0632533135a06f8c5d536b420deec5fcb5c58f3'
SPARQL = 'drt/complex_web_questions'
SPARQL_REV = 'e0c1669689906cf154315f2347b7f8a081ec49c8'


def shards(repo, revision, split):
    files = HfApi().list_repo_files(repo, repo_type='dataset', revision=revision)
    files = sorted(f for f in files if f.startswith(f'data/{split}-') and f.endswith('.parquet'))
    return [hf_hub_download(repo, f, repo_type='dataset', revision=revision) for f in files]


def questions(files):
    columns = ['id', 'question', 'q_entity', 'a_entity', 'graph']
    for file in files:
        for batch in pq.ParquetFile(file).iter_batches(batch_size=64, columns=columns):
            yield from batch.to_pylist()


def top_paths(question, pool, model, entity_names, relation_names, local_names):
    ranked, scores = model.rank(question.text, question.names)
    score = np.full(len(relation_names), -2.0)
    score[ranked[:50]] = scores[:50]
    best = search(question, pool, score)

    def name(node):
        return entity_names[node] if node < pool.n else local_names[node]

    candidates = [node for node, (_, hops, _, _) in best.items()
                  if hops and not MID.fullmatch(name(node))]
    candidates.sort(key=lambda node: -best[node][0] / best[node][1])
    paths = []
    for node in candidates[:100]:
        path = []
        while best[node][2] is not None:
            _, _, parent, rel = best[node]
            path.append((name(parent), relation_names[rel], name(node)))
            node = parent
        paths.append(path[::-1])
    return paths


def prepare(work, limit):
    pool_tools.CWQ_TRAIN = shards(CWQ, CWQ_REV, 'train')
    pool_tools.CWQ_TEST = shards(CWQ, CWQ_REV, 'test')
    pool_tools.CWQ_VAL = shards(CWQ, CWQ_REV, 'validation')
    pool_tools.WQ_TRAIN = shards(WEBQSP, WEBQSP_REV, 'train')
    counts = [len(files) for files in (pool_tools.CWQ_TRAIN, pool_tools.CWQ_TEST,
                                      pool_tools.CWQ_VAL, pool_tools.WQ_TRAIN)]
    if counts != [18, 3, 3, 2]:
        raise ValueError(f'Unexpected dataset shard counts: {counts}')
    sparql = hf_hub_download(SPARQL, 'complex_web_questions/complex_web_questions-train.parquet',
                             repo_type='dataset', revision=SPARQL_REV)
    pool_tools.CACHE = work / 'pool_cache.pkl'
    if not pool_tools.CACHE.exists():
        try:
            pool_tools.build_cache()
        except BaseException:
            pool_tools.CACHE.unlink(missing_ok=True)
            raise
    with pool_tools.CACHE.open('rb') as f:
        cache = pickle.load(f)
    ent, rel = cache['ent'], cache['rel']
    strict = (cache['bits'] & pool_tools.POOLS['strict']) != 0
    h, r, t = (cache[key][strict] for key in ('h', 'r', 't'))
    pool = pool_tools.Padded(pool_tools.Graph(h, r, t, len(ent)))
    class_nodes = set(t[np.isin(r, [rel[x] for x in pool_tools.TYPE_RELS if x in rel])].tolist())
    entity_names = {i: name for name, i in ent.items()}
    relation_names = {i: name for name, i in rel.items()}
    held_out = {pool_tools.seed(i) for i in pool_tools.ids(pool_tools.CWQ_VAL + pool_tools.CWQ_TEST)}
    if held_out & {pool_tools.seed(i) for i in pool_tools.ids(pool_tools.CWQ_TRAIN)}:
        raise ValueError('CWQ train and evaluation share a seed; filter predictor training first')
    model = RelationModel(rel, pool_tools.CWQ_TRAIN, sparql)

    print('Extracting validation features and calibrating gate on separate seed groups', flush=True)
    rows, labels, groups = [], [], []
    for row in questions(pool_tools.CWQ_VAL):
        q = Question(row, ent, rel, class_nodes)
        rows.append(list(features(q, model, pool).values()))
        labels.append(q.gap)
        groups.append(pool_tools.seed(q.id))
    x, y = np.asarray(rows), np.asarray(labels)
    fit, calibrate = next(GroupShuffleSplit(test_size=.25, random_state=42).split(x, y, groups))
    clf = HistGradientBoostingClassifier(max_depth=4, learning_rate=.05,
                                         max_iter=200, random_state=0).fit(x[fit], y[fit])
    threshold = float(np.quantile(clf.predict_proba(x[calibrate])[:, 1], .7))
    print(f'Gate threshold {threshold:.4f}; preparing {limit} test questions', flush=True)
    records = {}
    for row in questions(pool_tools.CWQ_TEST):
        # Candidate generation sees the question and graph only.
        started = time.perf_counter()
        visible = dict(row, a_entity=[])
        q = Question(visible, ent, rel, class_nodes)
        probability = float(clf.predict_proba([list(features(q, model, pool).values())])[0, 1])
        gate_seconds = time.perf_counter() - started
        graph_nodes = dict.fromkeys(node for h, _, t in row['graph'] or [] for node in (h, t))
        names = dict.fromkeys([*q.names, *graph_nodes])
        local_names = dict(enumerate((name for name in names if name not in ent), len(ent)))
        started = time.perf_counter()
        paths = top_paths(q, pool, model, entity_names, relation_names, local_names)
        search_seconds = time.perf_counter() - started
        records[q.id] = dict(paths=paths, gated=probability >= threshold, probability=probability,
                             gap=not set(row['a_entity'] or []) & graph_nodes.keys(),
                             gate_seconds=gate_seconds, search_seconds=search_seconds)
        if len(records) == limit:
            break
    if len(records) != limit:
        raise ValueError(f'Expected {limit} test questions, got {len(records)}')
    return records, threshold


def decode(records, work, output):
    output.mkdir(parents=True, exist_ok=False)
    for mode in ('local', 'always', 'gated'):
        command = [sys.executable, '-u', str(GCR / 'workflow' / 'cuda_baseline.py'),
                   '--dataset', CWQ, '--dataset-revision', CWQ_REV, '--graph', 'multi',
                   '--limit', str(len(records)), '--prefill-path',
                   '--adapter', str(GCR / 'training_runs' / 'v2' / 'C2' / 'adapter'),
                   '--output', str(output / mode)]
        if mode != 'local':
            paths_file = work / f'{mode}_{len(records)}.json'
            paths = {qid: r['paths'] if mode == 'always' or r['gated'] else []
                     for qid, r in records.items()}
            paths_file.write_text(json.dumps(paths), encoding='utf-8')
            command += ['--completion-paths', str(paths_file)]
        print(f'Decoding {mode}: {len(records)} questions', flush=True)
        with (output / f'{mode}.log').open('w', encoding='utf-8') as log:
            subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)


def summarize(records, threshold, output):
    sys.path.insert(0, str(GCR))
    from src.utils.qa_utils import eval_hit

    report = {'threshold': threshold, 'revisions': {'cwq': CWQ_REV, 'webqsp': WEBQSP_REV,
                                                   'sparql_train': SPARQL_REV}, 'runs': {}}
    baseline = {}
    for mode in ('local', 'always', 'gated'):
        manifest = json.loads((output / mode / 'manifest.json').read_text(encoding='utf-8'))
        groups = {name: dict(n=0, hit=0, gained=0, lost=0) for name in ('all', 'gap', 'non_gap')}
        with (output / mode / 'predictions.jsonl').open(encoding='utf-8') as f:
            for line in f:
                row = json.loads(line)
                qid = row['id']
                answers = [p.split('# Answer:', 1)[1].strip()
                           for p in row['prediction'] if '# Answer:' in p]
                hit = bool(eval_hit(' '.join(answers), row['ground_truth']))
                if mode == 'local':
                    baseline[qid] = hit
                for name in ('all', 'gap' if records[qid]['gap'] else 'non_gap'):
                    stats = groups[name]
                    stats['n'] += 1
                    stats['hit'] += hit
                    stats['gained'] += hit and not baseline[qid]
                    stats['lost'] += baseline[qid] and not hit
        cost = sum((r['gate_seconds'] if mode == 'gated' else 0)
                   + (r['search_seconds'] if mode == 'always' or (mode == 'gated' and r['gated']) else 0)
                   for r in records.values())
        report['runs'][mode] = dict(groups=groups, preparation_seconds=cost,
                                    decode_seconds=manifest['elapsed_seconds'],
                                    path_audit=manifest['path_audit'],
                                    answer_metrics=manifest['answer_section_metrics'])
    report['gated_count'] = sum(r['gated'] for r in records.values())
    (output / 'comparison.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--limit', type=int, default=500)
    parser.add_argument('--smoke', type=int, default=20)
    args = parser.parse_args()
    if not 0 <= args.smoke <= args.limit or args.limit < 1:
        parser.error('Require 0 <= smoke <= limit and limit >= 1')
    work, output = args.work.resolve(), args.output.resolve()
    work.mkdir(parents=True, exist_ok=True)
    records, threshold = prepare(work, args.limit)
    if args.smoke:
        smoke = dict(list(records.items())[:args.smoke])
        decode(smoke, work, work / 'smoke')
        summarize(smoke, threshold, work / 'smoke')
    decode(records, work, output)
    summarize(records, threshold, output)


if __name__ == '__main__':
    main()
