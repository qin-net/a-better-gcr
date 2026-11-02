"""Experiment P: can structural priors pick the right path out of the trie?

Offline stage of structural-path-ranking-design.md §5.1 (E1–E3), no model.
For every CWQ question the candidate set is what a 2-hop trie on the
multi-relation graph contains: every walk of 1–2 steps from a topic entity in
the question's own subgraph, reverse steps allowed
(graph-constrained-reasoning/src/multi_relation_graph.py). Two labels:
  A  the path ends at an answer entity (what Hit rewards);
  S  A, and every relation on it appears in the question's SPARQL
     (a faithful path, as in experiment N).

Each path gets the design doc's features, computed only from CWQ training
data (subgraphs, questions, SPARQL), whose seed WebQSP questions are disjoint
from validation and test:
  LEN   hop count                  FREQ  log relation frequency in the pool
  F1    functional-ness of each step in its traversal direction, local fan-out
  F2    an inverse edge (support >= 0.5 in the pool) closes the step
  F3    precision of the 2-hop rule (r1, r2) in the pool
  F4    type PMI of each step's endpoints in their roles, CVT end, type relation
  F5    question-relation match: TF-IDF centroid of training questions whose
        SPARQL uses the relation, and stem overlap with the relation name
  P     how often the relation sequence is a faithful training path (dataset prior)

Logistic regressions on feature groups are fit on validation (positives plus
sampled negatives) and rank all candidates of every test question. Reported
over questions with at least one positive: MRR and Hit@1/10/100 of the best
positive, ties broken at random. faithful@1: on contested questions (both
faithful and spurious answer paths exist), the share whose top-scored answer
path is faithful.

Output: out/structural_ranking.json

Usage (the RuntimeWarnings are spurious matmul warnings from NumPy 2 on macOS
Accelerate; features and scores were checked to be finite):
  python -I -W ignore::RuntimeWarning experiments/p_structural_ranking.py \
      --train data/hf/cwq_full/train-*.parquet \
      --sparql-train data/hf/cwq_sparql_train.parquet \
      --val data/hf/cwq_eval/validation-*.parquet --sparql-val data/hf/cwq_sparql_validation.parquet \
      --test data/hf/cwq_eval/test-*.parquet --sparql-test data/hf/cwq_sparql_test.parquet \
      --train-paths out/train_variants/C/cwq.jsonl
"""

import argparse
import collections
import json
import math
import os
import random
import re
import sys
import time

import numpy as np
import pyarrow.parquet as pq
from scipy import sparse
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler, normalize

sys.path.insert(0, os.path.dirname(__file__))
from l_pool_paths import build_pool  # noqa: E402
from n_constrained_paths import PRED_RE, build_reverse, load_sparql_relations  # noqa: E402
from rog_io import iter_rows  # noqa: E402

NT = "common.topic.notable_types"
# Same list as train_variants/build_variants.py.
TYPE_RELS = {"common.topic.notable_types", "people.person.gender", "type.object.type",
             "common.topic.notable_for", "people.marriage.type_of_union",
             "government.government_position_held.basic_title"}
MID = re.compile(r"^[mg]\.[0-9a-z_]+$")
TOKEN = re.compile(r"[a-z]+")

COLS = ["hop2", "relfreq", "func_mean", "func_min", "fanout", "inverse", "rule", "has_rule",
        "type_from", "type_to", "end_cvt", "type_rel", "tfidf_mean", "tfidf_max", "tfidf_last",
        "lex", "prior_seq", "prior_last"]
GROUPS = {"LEN": ["hop2"], "FREQ": ["relfreq"], "F1": ["func_mean", "func_min", "fanout"],
          "F2": ["inverse"], "F3": ["rule", "has_rule"],
          "F4": ["type_from", "type_to", "end_cvt", "type_rel"],
          "F5": ["tfidf_mean", "tfidf_max", "tfidf_last", "lex"],
          "P": ["prior_seq", "prior_last"],
          # Part of F4, split out to see how much of F1–F4 is just "answers are not CVT nodes".
          "CVT": ["end_cvt"]}
STRUCT = ["F1", "F2", "F3", "F4"]
ALL = ["LEN", "FREQ"] + STRUCT + ["F5", "P"]
SCORERS = {
    "LEN": ["LEN"], "FREQ": ["FREQ"], "LEN+FREQ": ["LEN", "FREQ"],
    "F1-F4": STRUCT, "LEN+FREQ+F1-F4": ["LEN", "FREQ"] + STRUCT,
    "F5": ["F5"], "F5+LEN+FREQ": ["F5", "LEN", "FREQ"],
    "F5+LEN+FREQ+CVT": ["F5", "LEN", "FREQ", "CVT"],
    "F5+LEN+FREQ+F1-F4": ["F5", "LEN", "FREQ"] + STRUCT,
    "F5+LEN+FREQ+P": ["F5", "LEN", "FREQ", "P"],
    "F5+LEN+FREQ+P+CVT": ["F5", "LEN", "FREQ", "P", "CVT"], "ALL": ALL,
    **{f"ALL-{g}": [x for x in ALL if x != g] for g in STRUCT + ["F5", "P"]},
}
# Step-level columns, combined into path columns in `featurize`.
S_FREQ, S_FUNC, S_FAN, S_INV, S_TFROM, S_TTO, S_CVT, S_TREL, S_TFIDF, S_LEX, S_GOLD, S_ANS = range(12)


def stems(words):
    return frozenset(w[:5] for w in words if len(w) >= 3 and w not in ENGLISH_STOP_WORDS)


def default_types(e):
    return ("<cvt>",) if MID.match(e) else ("<none>",)


class Stats:
    """Everything learned from training data; nothing here sees validation or test."""

    def __init__(self, train_files, sparql_train, train_paths, rule_sample, seed):
        t0 = time.time()
        pool = build_pool(train_files)
        rev = build_reverse(pool)
        print(f"pool: {len(pool)} source nodes  ({time.time() - t0:.0f}s)", flush=True)

        # F1 functional-ness per traversal direction: share of (u, r) with one neighbour.
        self.relcount = collections.Counter()
        single, groups = collections.Counter(), collections.Counter()
        for b, adj in ((0, pool), (1, rev)):
            for u, nbrs in adj.items():
                per = collections.Counter(r for rels in nbrs.values() for r in rels)
                for r, c in per.items():
                    groups[r, b] += 1
                    single[r, b] += c == 1
                    if b == 0:
                        self.relcount[r] += c
        self.func = {k: single[k] / n for k, n in groups.items()}

        # F4 type PMI of a relation's subject (role 0) and object (role 1).
        types = collections.defaultdict(list)
        for h, nbrs in pool.items():
            for t, rels in nbrs.items():
                if NT in rels:
                    types[h].append(t)
        self.role = [collections.Counter() for _ in range(2)]       # (r, ty)
        self.role_r = [collections.Counter() for _ in range(2)]     # r
        self.role_ty = [collections.Counter() for _ in range(2)]    # ty
        for h, nbrs in pool.items():
            th = types.get(h) or default_types(h)
            for t, rels in nbrs.items():
                tt = types.get(t) or default_types(t)
                for r in rels:
                    for role, tys in ((0, th), (1, tt)):
                        for ty in tys:
                            self.role[role][r, ty] += 1
                            self.role_ty[role][ty] += 1
                        self.role_r[role][r] += len(tys)
        self.n_types = len(set(self.role_ty[0]) | set(self.role_ty[1]))
        self.role_n = [sum(c.values()) for c in self.role_ty]
        print(f"F1/F4 stats  ({time.time() - t0:.0f}s)", flush=True)

        # F2 inverse relations: (h, r, t) usually comes with (t, r2, h).
        inv_n = collections.Counter()
        for h, nbrs in pool.items():
            for t, rels in nbrs.items():
                back = pool.get(t, {}).get(h)
                if back:
                    for r in rels:
                        for r2 in back:
                            if r2 != r:
                                inv_n[r, r2] += 1
        self.inverse = collections.defaultdict(set)
        for (r, r2), n in inv_n.items():
            if n >= 20 and n / self.relcount[r] >= 0.5:
                self.inverse[r].add(r2)
        print(f"F2: {sum(map(len, self.inverse.values()))} inverse pairs  "
              f"({time.time() - t0:.0f}s)", flush=True)

        # F3 rule precision P((h,r2,t) | (h,r1,x),(x,r2,t)), forward steps only,
        # sampled like experiment A (low-degree heads, no hub middles).
        heads = [h for h, nbrs in pool.items() if sum(map(len, nbrs.values())) <= 24]
        random.Random(seed).shuffle(heads)
        rule_n, rule_hit = collections.Counter(), collections.Counter()
        for h in heads[:rule_sample]:
            edges = {(r, t) for t, rels in pool[h].items() for r in rels}
            for r1, x in edges:
                xn = pool.get(x)
                if not xn or len(xn) > 300:
                    continue
                for t, rels in xn.items():
                    if t == h:
                        continue
                    for r2 in rels:
                        if r2 != r1:
                            rule_n[r1, r2] += 1
                            rule_hit[r1, r2] += (r2, t) in edges
        self.rules = {k: rule_hit[k] / n for k, n in rule_n.items() if n >= 100}
        print(f"F3: {len(self.rules)} rules  ({time.time() - t0:.0f}s)", flush=True)
        del pool, rev

        # F5 TF-IDF centroid of training questions per SPARQL relation.
        t = pq.read_table(sparql_train, columns=["question", "sparql"]).to_pydict()
        self.vec = TfidfVectorizer(stop_words="english", sublinear_tf=True, min_df=2)
        X = self.vec.fit_transform(t["question"])
        self.rel_index, rows, cols = {}, [], []
        for i, s in enumerate(t["sparql"]):
            for r in set(PRED_RE.findall(s or "")):
                rows.append(self.rel_index.setdefault(r, len(self.rel_index)))
                cols.append(i)
        R = sparse.csr_matrix((np.ones(len(rows)), (rows, cols)),
                              shape=(len(self.rel_index), X.shape[0]))
        self.centroid = normalize(R @ X).tocsr()
        self._rel_stems = {}

        # P: faithful training paths (variant C, relations all in the question's SPARQL),
        # counted once per question.
        gold = load_sparql_relations(sparql_train)
        self.prior_seq, self.prior_last = collections.Counter(), collections.Counter()
        with open(train_paths) as f:
            for line in f:
                row = json.loads(line)
                g = gold.get(row["id"], set())
                seqs = {tuple(s[1] for s in p) for p in row["ground_truth_paths"]}
                seqs = {s for s in seqs if s and set(s) <= g}
                self.prior_seq.update(seqs)
                self.prior_last.update({s[-1] for s in seqs})
        print(f"F5/P: {len(self.rel_index)} relations with questions, "
              f"{len(self.prior_seq)} path patterns  ({time.time() - t0:.0f}s)", flush=True)

    def type_pmi(self, r, role, tys):
        n_r = self.role_r[role].get(r, 0)
        if not n_r:
            return 0.0
        c, m, T, N = self.role[role], self.role_ty[role], self.n_types, self.role_n[role]
        return max(math.log((c.get((r, ty), 0) + 1) / (n_r + T))
                   - math.log((m.get(ty, 0) + 1) / (N + T)) for ty in tys)

    def tfidf(self, question, rels):
        idx = [self.rel_index.get(r, -1) for r in rels]
        known = [i for i in idx if i >= 0]
        sims = {}
        if known:
            s = (self.centroid[known] @ self.vec.transform([question]).T).toarray().ravel()
            sims = dict(zip(known, s))
        return {r: float(sims.get(i, 0.0)) for r, i in zip(rels, idx)}

    def rel_stems(self, r):
        if r not in self._rel_stems:
            self._rel_stems[r] = stems(re.split(r"[._]", r))
        return self._rel_stems[r]


def featurize(row, st, gold):
    """All <=2-step walks from the topic entities: features (n x COLS), labels A and S."""
    raw = {(h.strip(), r.strip(), t.strip()) for h, r, t in row["graph"]}
    # A step prints as (u, r, v); when both directions exist the trie has it once,
    # so keep the forward reading.
    steps_of = collections.defaultdict(dict)
    for h, r, t in raw:
        steps_of[h][r, t] = 0
    for h, r, t in raw:
        steps_of[t].setdefault((r, h), 1)
    out = {u: [(r, v, b) for (r, v), b in d.items()] for u, d in steps_of.items()}
    starts = [s for s in dict.fromkeys(x.strip() for x in row["q_entity"]) if s in out]
    if not starts:
        return None
    ltypes = collections.defaultdict(list)
    for h, r, t in raw:
        if r == NT:
            ltypes[h].append(t)
    rels = sorted({r for _, r, _ in raw})
    loc = {r: i for i, r in enumerate(rels)}
    sim = st.tfidf(row["question"], rels)
    qst = stems(TOKEN.findall(row["question"].lower()))
    lex = {r: len(qst & st.rel_stems(r)) for r in rels}
    answers = {a.strip() for a in row["a_entity"]}

    steps, step_rel, step_dir, step_end, block = [], [], [], [], {}

    def add_block(u):
        if u not in block:
            start = len(steps)
            fan = collections.Counter((r, b) for r, _, b in out[u])
            tu = ltypes.get(u) or default_types(u)
            for r, v, b in out[u]:
                tv = ltypes.get(v) or default_types(v)
                closes = (v, u) if b == 0 else (u, v)
                inv = any((closes[0], r2, closes[1]) in raw for r2 in st.inverse.get(r, ()))
                steps.append((math.log1p(st.relcount.get(r, 0)), st.func.get((r, b), 0.5),
                              math.log(fan[r, b]), inv,
                              st.type_pmi(r, b, tu), st.type_pmi(r, 1 - b, tv),
                              bool(MID.match(v)), r in TYPE_RELS, sim[r], lex[r],
                              r in gold, v in answers))
                step_rel.append(loc[r])
                step_dir.append(b)
                step_end.append(v)
            block[u] = (start, len(steps))
        return block[u]

    I1 = np.concatenate([np.arange(*add_block(s)) for s in starts])
    spans = [add_block(step_end[i]) for i in I1]
    F = np.array(steps, dtype=np.float64)
    rel = np.array(step_rel)
    rd = rel * 2 + np.array(step_dir)
    cnt = np.array([b - a for a, b in spans])
    Pi = np.repeat(I1, cnt)
    Pj = np.concatenate([np.arange(a, b) for a, b in spans]) if len(spans) else np.array([], int)

    def lookup(codes, fn):
        uniq, inv = np.unique(codes, return_inverse=True)
        return np.array([fn(c) for c in uniq], dtype=np.float64)[inv] if len(uniq) else \
            np.zeros(0)

    L = len(rels)
    seq2 = lookup(rel[Pi] * L + rel[Pj],
                  lambda c: math.log1p(st.prior_seq.get((rels[c // L], rels[c % L]), 0)))
    rule2 = lookup(rd[Pi] * 2 * L + rd[Pj],
                   lambda c: st.rules.get((rels[c // (2 * L) // 2], rels[c % (2 * L) // 2]), -1.0)
                   if c // (2 * L) % 2 == 0 and c % 2 == 0 else -1.0)
    seq1 = np.array([math.log1p(st.prior_seq.get((r,), 0)) for r in rels])[rel[I1]]
    last = np.array([math.log1p(st.prior_last.get(r, 0)) for r in rels])

    a, b = F[Pi], F[Pj]
    X1 = np.column_stack([
        np.zeros(len(I1)), F[I1, S_FREQ], F[I1, S_FUNC], F[I1, S_FUNC], F[I1, S_FAN],
        F[I1, S_INV], np.zeros(len(I1)), np.zeros(len(I1)), F[I1, S_TFROM], F[I1, S_TTO],
        F[I1, S_CVT], F[I1, S_TREL], F[I1, S_TFIDF], F[I1, S_TFIDF], F[I1, S_TFIDF],
        F[I1, S_LEX], seq1, last[rel[I1]]])
    X2 = np.column_stack([
        np.ones(len(Pi)), (a[:, S_FREQ] + b[:, S_FREQ]) / 2, (a[:, S_FUNC] + b[:, S_FUNC]) / 2,
        np.minimum(a[:, S_FUNC], b[:, S_FUNC]), a[:, S_FAN] + b[:, S_FAN],
        (a[:, S_INV] + b[:, S_INV]) / 2, np.maximum(rule2, 0), rule2 >= 0,
        (a[:, S_TFROM] + b[:, S_TFROM]) / 2, (a[:, S_TTO] + b[:, S_TTO]) / 2,
        b[:, S_CVT], np.maximum(a[:, S_TREL], b[:, S_TREL]),
        (a[:, S_TFIDF] + b[:, S_TFIDF]) / 2, np.maximum(a[:, S_TFIDF], b[:, S_TFIDF]),
        b[:, S_TFIDF], (a[:, S_LEX] + b[:, S_LEX]) / 2, seq2, last[rel[Pj]]])
    X = np.vstack([X1, X2])
    yA = np.concatenate([F[I1, S_ANS], b[:, S_ANS]]) > 0
    yS = yA & (np.concatenate([F[I1, S_GOLD], a[:, S_GOLD] * b[:, S_GOLD]]) > 0)
    return X, yA, yS


def iter_questions(files, sparql, limit):
    gold = load_sparql_relations(sparql)
    n = 0
    for p in files:
        for row in iter_rows(p):
            if limit and n >= limit:
                return
            n += 1
            yield row, gold.get(row["id"], set())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", nargs="+", required=True)
    ap.add_argument("--sparql-train", required=True)
    ap.add_argument("--val", nargs="+", required=True)
    ap.add_argument("--sparql-val", required=True)
    ap.add_argument("--test", nargs="+", required=True)
    ap.add_argument("--sparql-test", required=True)
    ap.add_argument("--train-paths", required=True)
    ap.add_argument("--rule-sample", type=int, default=200000)
    ap.add_argument("--neg-per-question", type=int, default=200)
    ap.add_argument("--limit", type=int, default=0, help="questions per split, 0 = all")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    t0 = time.time()
    st = Stats(args.train, args.sparql_train, args.train_paths, args.rule_sample, args.seed)
    rng = np.random.default_rng(args.seed)

    # Fit on validation: all positives (label A covers S) plus sampled negatives.
    Xs, As, Ss = [], [], []
    for i, (row, gold) in enumerate(iter_questions(args.val, args.sparql_val, args.limit)):
        f = featurize(row, st, gold)
        if f is None:
            continue
        X, yA, yS = f
        pos = np.flatnonzero(yA)
        neg = np.flatnonzero(~yA)
        pos = rng.choice(pos, min(len(pos), 100), replace=False)
        neg = rng.choice(neg, min(len(neg), args.neg_per_question), replace=False)
        keep = np.concatenate([pos, neg])
        Xs.append(X[keep])
        As.append(yA[keep])
        Ss.append(yS[keep])
        if (i + 1) % 500 == 0:
            print(f"  val {i + 1}  ({time.time() - t0:.0f}s)", flush=True)
    Xv, Av, Sv = np.vstack(Xs), np.concatenate(As), np.concatenate(Ss)
    print(f"validation rows {len(Xv)}  A+ {Av.sum()}  S+ {Sv.sum()}", flush=True)

    models = {}
    for label, y in (("A", Av), ("S", Sv)):
        for name, groups in SCORERS.items():
            cols = [COLS.index(c) for g in groups for c in GROUPS[g]]
            m = make_pipeline(StandardScaler(),
                              LogisticRegression(max_iter=2000, class_weight="balanced"))
            m.fit(Xv[:, cols], y)
            models[label, name] = (cols, m)
    print(f"fit {len(models)} models  ({time.time() - t0:.0f}s)", flush=True)

    names = ["random"] + list(SCORERS)
    acc = {(label, n): collections.defaultdict(list) for label in "AS" for n in names}
    cover = collections.Counter()
    sizes = []
    for i, (row, gold) in enumerate(iter_questions(args.test, args.sparql_test, args.limit)):
        cover["questions"] += 1
        cover["with_sparql"] += bool(gold)
        f = featurize(row, st, gold)
        if f is None:
            continue
        X, yA, yS = f
        cover["with_candidates"] += 1
        cover["with_A"] += bool(yA.any())
        cover["with_S"] += bool(yS.any())
        contested = yS.any() and (yA & ~yS).any()
        cover["contested"] += bool(contested)
        sizes.append(len(X))
        noise = rng.random(len(X)) * 1e-9
        for label, y in (("A", yA), ("S", yS)):
            for n in names:
                if n == "random":
                    s = rng.random(len(X))
                else:
                    cols, m = models[label, n]
                    s = m.decision_function(X[:, cols]) + noise
                r = acc[label, n]
                if y.any():
                    rank = 1 + int((s > s[y].max()).sum())
                    r["rr"].append(1 / rank)
                    for k in (1, 10, 100):
                        r[f"hit@{k}"].append(rank <= k)
                if contested:
                    top = np.flatnonzero(yA)[np.argmax(s[yA])]
                    r["faithful@1"].append(bool(yS[top]))
        if (i + 1) % 500 == 0:
            print(f"  test {i + 1}  ({time.time() - t0:.0f}s)", flush=True)

    sizes = np.array(sizes)
    summary = {"coverage": dict(cover),
               "candidates": {q: int(np.percentile(sizes, q)) for q in (10, 50, 90, 99)},
               "metrics": {}, "coef": {}}
    for label in "AS":
        print(f"\nlabel {label}  (questions with a positive: {cover['with_' + label]})")
        print(f"{'scorer':<22}{'MRR':>7}{'H@1':>7}{'H@10':>7}{'H@100':>7}{'faith@1':>9}")
        for n in names:
            r = acc[label, n]
            m = {k: float(np.mean(v)) for k, v in r.items()}
            summary["metrics"][f"{label}/{n}"] = m
            print(f"{n:<22}{m['rr']:>7.3f}{m['hit@1']:>7.3f}{m['hit@10']:>7.3f}"
                  f"{m['hit@100']:>7.3f}{m.get('faithful@1', float('nan')):>9.3f}")
        cols, m = models[label, "ALL"]
        coef = m[-1].coef_[0]
        summary["coef"][label] = {COLS[c]: round(float(w), 3) for c, w in zip(cols, coef)}
    print("\ncandidates per question p10/p50/p90/p99:", summary["candidates"])
    print("coverage:", dict(cover))
    print("standardized coefficients (ALL):", json.dumps(summary["coef"], indent=1))
    dest = os.path.join(os.path.dirname(__file__), "..", "out", "structural_ranking.json")
    with open(dest, "w") as f:
        json.dump(summary, f, indent=1)
    print(f"wrote out/structural_ranking.json  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
