"""Run every demo question with and without the KG-Trie and dump a trace JSON.

Usage:  python3 -m gcr_lab.demo
Writes: out/traces.json and prints a compact console report.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gcr_lab.kb import KB_DEFAULT, QUESTIONS, TRIPLES
from gcr_lab.tokenizer import Tokenizer
from gcr_lab.trie import Trie
from gcr_lab.toy_lm import ToyLM
from gcr_lab.decoder import Decoder

# What the "model" believes. Hallucinated answers are in these tables but not
# in the graph -- that is what constrained decoding has to survive.
PREFS = {
    "poe-birth": {
        "topic": "Edgar Allan Poe",
        "relations": {"people.person.place_of_birth": 5.0,
                      "people.person.place_of_death": 1.0},
        "entities": {"Philadelphia": 4.0, "Boston": 2.0},
    },
    "mlk-school": {
        "topic": "Martin Luther King, Jr.",
        "relations": {"people.person.education": 5.0},
        "entities": {"Harvard University": 4.0, "Morehouse College": 3.0,
                     "Boston University": 2.5},
    },
    "ja-lang": {
        "topic": "Jamaica",
        "relations": {"location.country.languages_spoken": 5.0},
        "entities": {"Spanish language": 4.0, "Jamaican English": 2.0},
    },
    "balt-country": {
        "topic": "Baltimore",
        "relations": {"location.location.containedby": 5.0,
                      "location.country.languages_spoken": 4.5},
        "entities": {"North America": 4.2, "United States": 3.0},
        "max_hops": 2,
    },
}
for q in PREFS.values():
    q.setdefault("max_hops", 1)
    q.setdefault("floor", -20.0)
    q.setdefault("end_path", 6.0)
    q.setdefault("continue_path", 0.5)


def build():
    kb = KB_DEFAULT
    extra = sorted({e for q in PREFS.values() for e in q["entities"]})
    tok = Tokenizer(kb.entities, kb.relations, extra_entities=extra)
    lm = ToyLM(tok, kb, extra_entities=extra)
    return kb, tok, lm


def run_one(kb, tok, lm, q, constrained):
    paths = kb.walk_paths(q["topic"], max_hops=PREFS[q["id"]]["max_hops"])
    trie = Trie([tok.path_tokens(p) for p in paths])
    dec = Decoder(tok, trie, lm)
    ids, trace = dec.decode(PREFS[q["id"]], constrained=constrained)
    triples = dec.verify(ids)
    faithful = bool(triples) and all(t["in_kb"] for t in triples)
    steps = []
    for st in trace:
        scores = st.scores
        top = sorted(scores.items(), key=lambda kv: -kv[1])[:8]
        steps.append({
            "prefix": [tok.id2tok[i] for i in st.prefix],
            "allowed": None if st.allowed is None else
                       sorted(tok.id2tok[i] for i in st.allowed),
            "scores": [{"token": tok.id2tok[t], "score": round(s, 2)}
                       for t, s in top],
            "chosen": tok.id2tok[st.chosen],
            "constrained": st.constrained,
            "forced": st.forced,
        })
    return {
        "ids": ids,
        "text": " ".join(t.lstrip("▁") for t in
                         [tok.id2tok[i] for i in ids][1:-1]),
        "triples": triples,
        "faithful": faithful,
        "steps": steps,
        "n_paths_in_trie": len(trie),
    }


def main():
    kb, tok, lm = build()
    out = {"vocab": tok.id2tok, "questions": []}
    print(f"vocab={len(tok)}  entities={len(kb.entities)}  "
          f"relations={len(kb.relations)}  triples={len(TRIPLES)}")
    print()
    for q in QUESTIONS:
        row = {"id": q["id"], "question": q["question"],
               "gold": [[list(t) for t in q["gold"]]], "runs": {}}
        for mode in (True, False):
            r = run_one(kb, tok, lm, q, mode)
            row["runs"]["constrained" if mode else "free"] = r
            tag = "GCR " if mode else "free"
            mark = "faithful" if r["faithful"] else "HALLUCINATED"
            print(f"[{tag}] {q['id']:<13} {mark:<12} {r['text']}")
        out["questions"].append(row)
        print()

    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "out"), exist_ok=True)
    dest = os.path.join(os.path.dirname(__file__), "..", "out", "traces.json")
    with open(dest, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("wrote", os.path.abspath(dest))


if __name__ == "__main__":
    main()
