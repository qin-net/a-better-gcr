"""Diagnose the CWQ questions that remain unrepaired.

For each of the roughly 67 failures, classify WHY. Candidate causes, checked
in order:

  value_answer      -- gold answer is a literal (year, number, date), not an
                       entity node; the graph stores it as a value, so no
                       entity-to-entity path can ever end there
  alias_present     -- answer not matched exactly, but a node contains the
                       answer string (e.g. "Mazie K. Hirono"); entity linking
                       failure rather than knowledge absence
  topic_not_entity  -- q_entity is a concept/relation ("Quarterback",
                       "President"), so BFS starts from the wrong node
  no_inbound        -- answer node exists but has no inbound edges at all
  deep_or_capped    -- present and reachable in principle, but >6 hops or the
                       node cap cut the search

Outputs counts and examples per class, and writes them to JSON.
"""

import collections
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from rog_io import iter_rows  # noqa: E402


VALUE_RE = re.compile(r"^[-+]?\d{1,5}(\.\d+)?$|^\d{4}-\d{2}-\d{2}$")


def bfs(adj, starts, goals, cap=6, node_cap=2_000_000):
    goals = set(goals)
    seen = set(starts)
    frontier = [(s, 0) for s in starts]
    explored = 0
    while frontier:
        nxt = []
        for u, d in frontier:
            explored += 1
            if u in goals:
                return d, explored, False
            if d >= cap:
                continue
            for v in adj.get(u, ()):
                if v not in seen:
                    seen.add(v)
                    nxt.append((v, d + 1))
                    if explored > node_cap:
                        return None, explored, True
        frontier = nxt
    return None, explored, False


def main():
    cwq_files = sorted(glob.glob("data/hf/cwq_full/train-*.parquet"))
    pool = collections.defaultdict(set)
    indeg = collections.Counter()
    for p in cwq_files + ["data/hf/train.parquet"]:
        for row in iter_rows(p):
            for h, r, t in row["graph"]:
                pool[h].add(t)
                indeg[t] += 1

    nodes = set(pool) | set(indeg)
    lower_nodes = collections.defaultdict(list)
    for n in nodes:
        lower_nodes[n.lower()].append(n)

    classes = collections.Counter()
    examples = collections.defaultdict(list)

    rows = (row for p in cwq_files for row in iter_rows(p))
    for row in rows:
        q, a = row["q_entity"], row["a_entity"]
        if not q or not a:
            continue
        sub = collections.defaultdict(set)
        for h, r, t in row["graph"]:
            sub[h].add(t)
        d, _, _ = bfs(sub, q, a, cap=99)
        if d is not None:
            continue

        present = [x for x in a if x in nodes]
        if present:
            dd, _, capped = bfs(pool, q, present)
            if dd is not None:
                continue
            cause = "capped" if capped else "deep_or_capped"
            # distinguish topic problems
            if all(len(e.split()) == 1 and e[:1].isupper() and e in
                   {"President", "Quarterback", "Placekicker", "Coach"}
                   for e in q):
                cause = "topic_not_entity"
            classes[cause] += 1
            if len(examples[cause]) < 5:
                examples[cause].append({
                    "question": row["question"][:95], "q": q, "a": a[:3],
                    "hops_explored": _, "capped": capped})
            continue

        # answer absent as a node -- why?
        val = [x for x in a if VALUE_RE.match(x.strip())]
        if val:
            classes["value_answer"] += 1
            if len(examples["value_answer"]) < 5:
                examples["value_answer"].append(
                    {"question": row["question"][:95], "q": q, "a": a[:3]})
            continue
        alias = []
        for x in a:
            key = x.lower().strip()
            for n in lower_nodes.get(key, []):
                if n != x:
                    alias.append((x, n))
            if not alias:
                for n in nodes:
                    if key in n.lower() and len(n) < len(x) + 25:
                        alias.append((x, n))
                        break
        if alias:
            classes["alias_present"] += 1
            if len(examples["alias_present"]) < 5:
                examples["alias_present"].append(
                    {"question": row["question"][:95], "a": a[:3],
                     "alias": alias[:3]})
            continue

        # truly absent: is it at least plausible as a real-world entity?
        classes["entity_truly_absent"] += 1
        if len(examples["entity_truly_absent"]) < 8:
            examples["entity_truly_absent"].append(
                {"question": row["question"][:95], "q": q, "a": a[:3]})

    total = sum(classes.values())
    print(f"unrepaired: {total}")
    print(f"{'cause':<26}{'count':>7}{'share':>8}")
    for k, v in classes.most_common():
        print(f"{k:<26}{v:>7}{v / total:>8.1%}")
    for k in classes:
        print(f"\n--- {k} ---")
        for ex in examples[k]:
            print(f"  Q: {ex['question']}")
            print(f"     q={ex['q']}  a={ex['a']}  extra={ {kk: vv for kk, vv in ex.items() if kk not in ('question','q','a')} }")

    dest = os.path.join(os.path.dirname(__file__), "..", "out", "unrepaired_causes.json")
    json.dump({"total": total, "classes": classes,
               "examples": {k: v for k, v in examples.items()}},
              open(dest, "w"), ensure_ascii=False, indent=1)
    print("\nwrote out/unrepaired_causes.json")


if __name__ == "__main__":
    main()
