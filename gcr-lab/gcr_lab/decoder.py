"""Graph-constrained decoding, step by step, with a full trace.

Mirrors src/graph_constrained_decoding.py: while inside <PATH>...</PATH>,
every token must be a legal trie prefix; when the path closes, the model is
free again. Here we also record *why* each token won, so the HTML stepper can
show the mask.
"""


class Step:
    def __init__(self, prefix, allowed, scores, chosen, constrained):
        self.prefix = prefix
        self.allowed = allowed
        self.scores = scores
        self.chosen = chosen
        self.constrained = constrained

    @property
    def forced(self):
        """True when the model wanted something else and the trie overruled it."""
        if not self.scores:
            return False
        best = max(self.scores, key=lambda t: (self.scores[t], -t))
        return best != self.chosen and self.scores[best] > self.scores[self.chosen]


class Decoder:
    def __init__(self, tokenizer, trie, lm, max_steps=40):
        self.tok = tokenizer
        self.trie = trie
        self.lm = lm
        self.max_steps = max_steps
        self.start = tokenizer.tok2id["<PATH>"]
        self.end = tokenizer.tok2id["</PATH>"]

    def decode(self, prefs, constrained=True):
        prefix = [self.start]
        trace = []
        closed = False
        for _ in range(self.max_steps):
            inside = not closed and prefix.count(self.end) == 0
            scores = self.lm.next_token_scores(prefs, prefix[1:])  # drop <PATH>
            if not scores:
                break
            allowed = None
            if constrained and inside:
                allowed = self.trie.get(prefix)
                if not allowed:
                    allowed = None  # official code falls back to all tokens
            pool = scores
            if allowed is not None:
                pool = {t: s for t, s in scores.items() if t in allowed}
                if not pool:
                    pool = scores
            chosen = max(pool, key=lambda t: (pool[t], -t))
            step = Step(list(prefix), None if allowed is None else list(allowed),
                        dict(scores), chosen, constrained and inside)
            trace.append(step)
            prefix.append(chosen)
            if chosen == self.end:
                closed = True
                break
        return prefix, trace

    def path_from_ids(self, ids):
        """Turn a decoded id sequence back into human triples."""
        toks = [self.tok.id2tok[i] for i in ids]
        words = [t.lstrip("▁") for t in toks]
        text = " ".join(words[1:-1])
        return text

    def verify(self, ids):
        """Parse <PATH>...</PATH> into triples; mark each edge as in-KB or not."""
        words = [self.tok.id2tok[i].lstrip("▁").rstrip(",") for i in ids][1:-1]
        ents = sorted(self.lm._entity_vocab, key=lambda e: -len(e.split()))
        rels = sorted(self.lm.kb.relations, key=lambda r: -len(r.split()))

        def match(text, i, cands, sep):
            for c in cands:
                parts = [p.rstrip(",") for p in (
                    c.split(sep) if sep else c.split())]
                if text[i:i + len(parts)] == parts:
                    return c, len(parts)
            return None, 0

        triples, i = [], 0
        while i < len(words):
            head, n = match(words, i, ents, None)
            if head is None:
                break
            i += n
            rel, n = match(words, i, rels, ".")
            if rel is None:
                break
            i += n
            tail, n = match(words, i, ents, None)
            if tail is None:
                break
            i += n
            triples.append({"h": head, "r": rel, "t": tail,
                            "in_kb": self.lm.kb.has_edge(head, rel, tail)})
        return triples
