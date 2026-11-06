"""Experiment U: detect an incomplete graph and complete it without answers or SPARQL.

T showed that a training-only pool plus SPARQL relations recovers most of the CWQ
test gap with small, correct searches. Neither answers nor SPARQL exist at test
time, so this replaces both:

  completer  predict relations from the question text (TF-IDF centroids of CWQ
             train questions per SPARQL relation, question entity names masked),
             then search own subgraph + strict pool along the top K relations.
             Controls: the K most frequent relations, and the SPARQL oracle.
  detector   predict "answer is outside the own subgraph" from features that use
             no answer. Trained on CWQ validation, scored on CWQ test. Relation
             centroids never saw either set. Ablation: subgraph size features only.

Answers are used only as labels. compositionality_type is an annotation and is
not a feature.

  .venv/bin/python -I experiments/u_detect_complete.py   (from gcr-lab/)
"""
import collections
import gzip
import json
import pickle
import re
import statistics
import time

import numpy as np
import pyarrow.parquet as pq
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import normalize
from scipy import sparse

from t_inference_pool import (CACHE, CWQ_TEST, CWQ_TRAIN, CWQ_VAL, POOLS, TYPE_RELS, Graph, Local, Padded)

PRED_RE = re.compile(r'ns:([a-z_0-9]+(?:\.[a-z_0-9]+){2,})')
KS = (5, 10, 20, 50, 100)
DETECT_K = 20
CAP = 300000
WH = ('what', 'who', 'where', 'which', 'when')
SIZE = ['log_edges', 'log_nodes', 'n_q', 'n_starts', 'q_words', 'log_own_deg']


def mask(question, entities):
    for e in sorted(entities, key=len, reverse=True):
        question = re.sub(re.escape(e), ' ', question, flags=re.I)
    return question


class RelationModel:
    def __init__(self, rel, train_files=None, sparql_train='data/hf/cwq_sparql_train.parquet'):
        t0 = time.time()
        entities = {}
        for f in CWQ_TRAIN if train_files is None else train_files:
            for row in pq.read_table(f, columns=['id', 'q_entity']).to_pylist():
                entities[row['id']] = row['q_entity'] or []
        table = pq.read_table(sparql_train, columns=['ID', 'question', 'sparql'])
        if train_files is not None:
            table = table.filter(np.array([i in entities for i in table['ID'].to_pylist()]))
        t = table.to_pydict()
        self.vec = TfidfVectorizer(stop_words='english', sublinear_tf=True, min_df=2, ngram_range=(1, 2))
        X = self.vec.fit_transform(mask(q, entities.get(i, [])) for i, q in zip(t['ID'], t['question']))
        index, rows, cols, freq = {}, [], [], collections.Counter()
        for i, s in enumerate(t['sparql']):
            for r in sorted(set(PRED_RE.findall(s or '')) - TYPE_RELS):
                if r in rel:
                    rows.append(index.setdefault(r, len(index)))
                    cols.append(i)
                    freq[r] += 1
        R = sparse.csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(index), X.shape[0]))
        self.centroid = normalize(R @ X).tocsr()
        self.ids = np.array([rel[r] for r in sorted(index, key=index.get)], np.int32)
        self.by_freq = np.array([rel[r] for r, _ in freq.most_common()], np.int32)
        print(f'relation model: {len(index)} relations ({time.time() - t0:.0f}s)', flush=True)

    def rank(self, question, entities):
        """Relation ids best first, with their similarity scores."""
        s = (self.centroid @ self.vec.transform([mask(question, entities)]).T).toarray().ravel()
        order = np.argsort(-s, kind='stable')
        return self.ids[order], s[order]


def reach(graphs, starts, depth, allowed):
    """Node -> hops along allowed relations, across the union of graphs."""
    seen = {s: 0 for s in starts}
    frontier = np.array(sorted(seen), np.int32)
    for d in range(1, depth + 1):
        if not len(frontier) or len(seen) > CAP:
            break
        nxt = np.unique(np.concatenate([g.step(frontier, allowed) for g in graphs]))
        fresh = [v for v in nxt.tolist() if v not in seen]
        seen.update((v, d) for v in fresh)
        frontier = np.array(fresh, np.int32)
    return seen


class Question:
    """One test or validation row in pool ids; unseen names sit past the pool."""

    def __init__(self, row, ent, rel, class_nodes):
        self.id, self.text = row['id'], row['question']
        self.names = row['q_entity'] or []
        extra, n = {}, len(ent)

        def code(name):
            return ent[name] if name in ent else extra.setdefault(name, n + len(extra))

        graph = row['graph'] or []
        self.q = [code(x) for x in self.names]
        self.a = {code(x) for x in row['a_entity'] or []}
        self.local = Local([(code(x), rel.get(y, -1), code(z)) for x, y, z in graph])
        self.nodes = {code(x) for tr in graph for x in (tr[0], tr[2])}
        self.edges = len(graph)
        self.rels = {rel.get(tr[1], -1) for tr in graph}
        self.starts = [x for x in self.q if x not in class_nodes] or self.q
        self.gap = not (self.nodes & self.a)


def features(q, model, pool):
    ranked, scores = model.rank(q.text, q.names)
    top, s = ranked[:DETECT_K], scores[:DETECT_K]
    own = reach([q.local], q.starts, 2, top)
    both = reach([pool, q.local], q.starts, 3, top)
    present = np.array([r in q.rels for r in top.tolist()])
    own_deg = sum(len(q.local.adj.get(x, ())) for x in q.starts)
    pool_deg = sum(int(pool.graph.ptr[x + 1] - pool.graph.ptr[x]) for x in q.starts if x < pool.n)
    words = q.text.lower().split()
    f = {'log_edges': np.log1p(q.edges), 'log_nodes': np.log1p(len(q.nodes)), 'n_q': len(q.q),
         'n_starts': len(q.starts), 'q_words': len(words), 'log_own_deg': np.log1p(own_deg),
         'log_pool_deg': np.log1p(pool_deg), 'log_own_reach': np.log1p(len(own)), 'log_both_reach': np.log1p(len(both)),
         'log_new': np.log1p(len(set(both) - set(own))), 'own_end2': sum(d == 2 for d in own.values()),
         'top_score': float(s[0]), 'top5_score': float(s[:5].sum()),
         'covered': float(s[present].sum() / max(s.sum(), 1e-9)), 'covered5': float(present[:5].mean())}
    f.update({f'wh_{w}': float(w in words[:4]) for w in WH})
    return f


def load(files, ent, rel, class_nodes):
    out = []
    for f in files:
        for row in pq.read_table(f, columns=['id', 'question', 'q_entity', 'a_entity', 'graph']).to_pylist():
            if row['q_entity'] and row['a_entity']:
                out.append(Question(row, ent, rel, class_nodes))
    return out


def sweep(gap, model, pool, gold, rel):
    """Answer reachability on gap questions for each relation source."""
    rows = {}
    ranked = {q.id: model.rank(q.text, q.names)[0] for q in gap}

    def run(name, allowed_of):
        hit2 = hit3 = 0
        sizes = []
        for q in gap:
            best = None
            for allowed in allowed_of(q):
                got = reach([pool, q.local], q.starts, 3, allowed)
                d = [got[a] for a in q.a if a in got]
                cand = (min(d) if d else 9, len(got))
                best = cand if best is None or cand < best else best
            if best:
                hit2 += best[0] <= 2
                hit3 += best[0] <= 3
                sizes.append(best[1])
        sizes = sorted(sizes) or [0]
        rows[name] = {'hit2': hit2 / len(gap), 'hit3': hit3 / len(gap), 'median': statistics.median(sizes),
                      'p90': sizes[int(.9 * len(sizes))]}
        r = rows[name]
        print(f"{name:12} <=2 {r['hit2']:6.1%}  <=3 {r['hit3']:6.1%}  reached median {r['median']:>8} p90 {r['p90']:>8}",
              flush=True)

    def oracle(q):
        return [a for a in (np.array([rel[x] for x in set(p) - TYPE_RELS if x in rel], np.int32)
                            for p in gold.get(q.id, [])) if len(a)]

    run('sparql', oracle)
    for k in KS:
        run(f'pred@{k}', lambda q: [ranked[q.id][:k]])
    for k in (20, 50):
        run(f'freq@{k}', lambda q: [model.by_freq[:k]])
    recall = [np.mean([x in set(ranked[q.id][:20].tolist()) for x in oracle(q)[0]]) for q in gap if oracle(q)]
    print(f'SPARQL relations in pred@20 (first parse, mean per question): {np.mean(recall):.1%}', flush=True)
    rows['recall20'] = float(np.mean(recall))
    return rows


def detect(val, test, model, pool):
    t0 = time.time()
    fv, ft = [[features(q, model, pool) for q in s] for s in (val, test)]
    print(f'features ({time.time() - t0:.0f}s)', flush=True)
    names = list(fv[0])
    yv, yt = (np.array([q.gap for q in s]) for s in (val, test))
    out = {}
    for label, cols in (('size only', SIZE), ('all', names)):
        Xv = np.array([[f[c] for c in cols] for f in fv])
        Xt = np.array([[f[c] for c in cols] for f in ft])
        clf = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.05, max_iter=200, random_state=0).fit(Xv, yv)
        p = clf.predict_proba(Xt)[:, 1]
        rng = np.random.default_rng(0)
        boots = []
        for _ in range(1000):
            i = rng.integers(0, len(yt), len(yt))
            boots.append(roc_auc_score(yt[i], p[i]))
        auc = roc_auc_score(yt, p)
        lo, hi = np.percentile(boots, [2.5, 97.5])
        out[label] = {'auroc': auc, 'ci': [lo, hi], 'ap': average_precision_score(yt, p)}
        print(f'{label:10} AUROC {auc:.3f} [{lo:.3f}, {hi:.3f}]  AP {out[label]["ap"]:.3f}  base rate {yt.mean():.3f}', flush=True)
        thr = np.quantile(clf.predict_proba(Xv)[:, 1], [.9, .8, .7, .5])
        for q, th in zip((10, 20, 30, 50), thr):
            flag = p >= th
            print(f'   top {q}% by validation threshold: flagged {flag.mean():.1%}, precision {yt[flag].mean():.1%}, '
                  f'recall {flag[yt].mean():.1%}', flush=True)
    return out, p


def main():
    t0 = time.time()
    with open(CACHE, 'rb') as f:
        c = pickle.load(f)
    ent, rel, h, r, t, bits = c['ent'], c['rel'], c['h'], c['r'], c['t'], c['bits']
    type_ids = np.array([rel[x] for x in TYPE_RELS if x in rel], np.int32)
    class_nodes = set(t[np.isin(r, type_ids)].tolist())
    keep = bits & POOLS['strict'] != 0
    pool = Padded(Graph(h[keep], r[keep], t[keep], len(ent)))
    del c, h, r, t, bits, keep
    print(f'strict pool ready ({time.time() - t0:.0f}s)', flush=True)
    model = RelationModel(rel)
    gold = {x['id']: x['parses'] for x in map(json.loads, gzip.open('eval/gold_relations.jsonl.gz', 'rt'))}
    val, test = load(CWQ_VAL, ent, rel, class_nodes), load(CWQ_TEST, ent, rel, class_nodes)
    gap = [q for q in test if q.gap]
    print(f'validation {len(val)} (gap {sum(q.gap for q in val)}), test {len(test)} (gap {len(gap)}) '
          f'({time.time() - t0:.0f}s)', flush=True)

    print('\n== completer, CWQ test gap questions ==')
    rows = sweep(gap, model, pool, gold, rel)
    print('\n== detector, trained on validation, scored on test ==')
    det, p = detect(val, test, model, pool)
    with open('out/detect_complete.json', 'w') as f:
        json.dump({'completer': rows, 'detector': det,
                   'test_scores': {q.id: float(s) for q, s in zip(test, p)}}, f, default=float)
    print(f'done ({time.time() - t0:.0f}s)')


if __name__ == '__main__':
    main()
