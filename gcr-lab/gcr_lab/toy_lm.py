"""A hand-built language model, so the demo runs with no GPU and no download.

Scores come from three per-question tables:
  topic      -- the entity the question is about (always the path's start)
  relations  -- how much the model "wants" each relation given the question
  entities   -- how much it expects each answer (some are NOT in the graph)

The entity table is where hallucination lives: a fluent model happily prefers
"Philadelphia" as Poe's birthplace even though the graph says Boston. The trie
cannot fix the prior; it can only make that token undecodable.
"""


class ToyLM:
    def __init__(self, tokenizer, kb, extra_entities=()):
        self.tok = tokenizer
        self.kb = kb
        self.end_path = tokenizer.tok2id["</PATH>"]
        self._entity_vocab = sorted(set(kb.entities) | set(extra_entities),
                                    key=lambda e: -len(e.split()))
        self._relation_vocab = sorted(kb.relations, key=lambda r: -len(r.split()))

    def _parse(self, prefix):
        """Walk the prefix; return (slot, remainder, n_relations)."""
        i, slot, n_rel = 0, "topic", 0
        while i < len(prefix):
            hit = False
            if slot in ("topic", "answer"):
                for e in self._entity_vocab:
                    seq = self.tok.entity_tokens(e)
                    if prefix[i:i + len(seq)] == seq:
                        i += len(seq)
                        slot = "relation"
                        hit = True
                        break
            else:
                for r in self._relation_vocab:
                    seq = self.tok.relation_tokens(r)
                    if prefix[i:i + len(seq)] == seq:
                        i += len(seq)
                        slot = "answer"
                        n_rel += 1
                        hit = True
                        break
            if not hit:
                break
        return slot, prefix[i:], n_rel

    def next_token_scores(self, prefs, prefix):
        slot, rem, n_rel = self._parse(prefix)
        table = prefs.get("relations" if slot == "relation" else "entities", {})
        floor = prefs.get("floor", -20.0)

        if slot == "topic":
            cands = [(self.tok.entity_tokens(prefs["topic"]), 10.0)]
        elif slot == "relation":
            cands = [(self.tok.relation_tokens(r), s) for r, s in table.items()]
            cands += [(self.tok.relation_tokens(r), floor)
                      for r in self.kb.relations if r not in table]
        else:
            cands = [(self.tok.entity_tokens(e), s) for e, s in table.items()]
            cands += [(self.tok.entity_tokens(e), floor)
                      for e in self.kb.entities if e not in table]

        scores = {}
        for seq, score in cands:
            if seq[: len(rem)] == rem and len(seq) > len(rem):
                nxt = seq[len(rem)]
                scores[nxt] = max(scores.get(nxt, float("-inf")), score)

        if slot == "relation" and rem == []:
            if n_rel >= prefs.get("max_hops", 1):
                scores[self.end_path] = prefs.get("end_path", 6.0)
            else:
                scores[self.end_path] = prefs.get("continue_path", 0.5)
        return scores
