"""Experiment W: confidence intervals that respect seed clusters.

CWQ questions are rewrites of a few hundred WebQSP seeds, so questions sharing a
seed are correlated and a per-question bootstrap is too narrow. V also found a
13-point validation/test gap. This resamples whole seeds, compares the two splits
under the SPARQL search as well (if it shows the same gap, the split differs, not
the predictor), and tests the detector's feature gain with a paired seed bootstrap.

  PYTHONPATH=experiments .venv/bin/python experiments/w_seed_clusters.py
"""
import collections
import gzip
import json
import pickle

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

from t_inference_pool import CACHE, CWQ_TEST, CWQ_VAL, POOLS, TYPE_RELS, Graph, Padded, seed
from u_detect_complete import SIZE, RelationModel, features, load, reach


def clusters(ids):
    groups = collections.defaultdict(list)
    for i, q in enumerate(ids):
        groups[seed(q)].append(i)
    return list(groups.values())


def boot(groups, stat, n=2000):
    rng = np.random.default_rng(0)
    out = []
    for _ in range(n):
        idx = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        try:
            out.append(stat(idx))
        except ValueError:
            pass
    return np.percentile(out, [2.5, 97.5])


def main():
    with open(CACHE, 'rb') as f:
        c = pickle.load(f)
    ent, rel, h, r, t, bits = c['ent'], c['rel'], c['h'], c['r'], c['t'], c['bits']
    type_ids = np.array([rel[x] for x in TYPE_RELS if x in rel], np.int32)
    class_nodes = set(t[np.isin(r, type_ids)].tolist())
    keep = bits & POOLS['strict'] != 0
    pool = Padded(Graph(h[keep], r[keep], t[keep], len(ent)))
    model = RelationModel(rel)
    gold = {x['id']: x['parses'] for x in map(json.loads, gzip.open('eval/gold_relations.jsonl.gz', 'rt'))}
    val, test = load(CWQ_VAL, ent, rel, class_nodes), load(CWQ_TEST, ent, rel, class_nodes)

    def hit(q, allowed):
        got = reach([pool, q.local], q.starts, 3, allowed)
        return any(a in got for a in q.a)

    def sparql(q):
        sets = [np.array([rel[x] for x in set(p) - TYPE_RELS if x in rel], np.int32) for p in gold.get(q.id, [])]
        return any(hit(q, a) for a in sets if len(a))

    print('split       questions seeds  gap  gap seeds  gap rate')
    for name, split in (('validation', val), ('test', test)):
        gap = [q for q in split if q.gap]
        g = clusters([q.id for q in split])
        y = np.array([q.gap for q in split], float)
        lo, hi = boot(g, lambda i: y[i].mean())
        print(f'{name:11} {len(split):8} {len(g):5} {len(gap):4} {len(clusters([q.id for q in gap])):8}  '
              f'{y.mean():.1%} [{lo:.1%}, {hi:.1%}]')
    for name, split in (('validation', val), ('test', test)):
        gap = [q for q in split if q.gap]
        g = clusters([q.id for q in gap])
        rows = {'sparql': [sparql(q) for q in gap]}
        for k in (20, 50):
            rows[f'pred@{k}'] = [hit(q, model.rank(q.text, q.names)[0][:k]) for q in gap]
        for label, v in rows.items():
            v = np.array(v, float)
            lo, hi = boot(g, lambda i: v[i].mean())
            print(f'{name:11} {label:8} reached {v.mean():.1%}  seed CI [{lo:.1%}, {hi:.1%}]', flush=True)
        kinds = collections.defaultdict(list)
        for q, v in zip(gap, rows['sparql']):
            kinds[seed(q.id).split('-')[0]].append(v)
        print(f'{name:11} sparql reach by seed kind: ' +
              ', '.join(f'{k} {np.mean(v):.1%} (n={len(v)})' for k, v in sorted(kinds.items())))
        sizes = sorted(map(len, g), reverse=True)
        print(f'{name:11} largest seed clusters {sizes[:5]}, top 10 seeds hold {sum(sizes[:10]) / len(gap):.1%} of gap questions')

    fv, ft = [[features(q, model, pool) for q in s] for s in (val, test)]
    names = list(fv[0])
    yv, yt = (np.array([q.gap for q in s]) for s in (val, test))
    probs = {}
    for label, cols in (('size', SIZE), ('all', names)):
        clf = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.05, max_iter=200, random_state=0)
        clf.fit(np.array([[f[c] for c in cols] for f in fv]), yv)
        probs[label] = clf.predict_proba(np.array([[f[c] for c in cols] for f in ft]))[:, 1]
    g = clusters([q.id for q in test])
    for label, p in probs.items():
        lo, hi = boot(g, lambda i: roc_auc_score(yt[i], p[i]))
        print(f'detector {label:5} AUROC {roc_auc_score(yt, p):.3f}  seed CI [{lo:.3f}, {hi:.3f}]')
    lo, hi = boot(g, lambda i: roc_auc_score(yt[i], probs['all'][i]) - roc_auc_score(yt[i], probs['size'][i]))
    print(f"detector gain {roc_auc_score(yt, probs['all']) - roc_auc_score(yt, probs['size']):+.3f}  paired seed CI [{lo:+.3f}, {hi:+.3f}]")


if __name__ == '__main__':
    main()
