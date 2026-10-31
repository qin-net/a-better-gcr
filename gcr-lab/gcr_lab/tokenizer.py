"""A transparent word-level tokenizer.

The real GCR uses a subword tokenizer, which is why the trie stores *token id*
sequences rather than strings. We keep the same idea but at word granularity
so every trie node is readable on screen.
"""

import re

SPECIALS = ["<PATH>", "</PATH>"]
SPACE = "▁"  # '▁' marks a word start, like SentencePiece


def words(text):
    return re.findall(r"[A-Za-z][A-Za-z'.\-]*|\d+", text)


class Tokenizer:
    def __init__(self, entities, relations, extra_entities=()):
        toks = set(SPECIALS)
        for e in list(entities) + list(extra_entities):
            toks.update(SPACE + w for w in words(e))
        for r in relations:
            toks.update(SPACE + w for w in r.split("."))
        self.id2tok = sorted(toks)
        self.tok2id = {t: i for i, t in enumerate(self.id2tok)}

    def __len__(self):
        return len(self.id2tok)

    def encode(self, text):
        return [self.tok2id[SPACE + w] for w in words(text)]

    def decode(self, ids):
        return " ".join(self.id2tok[i] for i in ids)

    def entity_tokens(self, entity):
        return self.encode(entity)

    def relation_tokens(self, relation):
        return [self.tok2id[SPACE + w] for w in relation.split(".")]

    def path_tokens(self, triples_of_path):
        """Serialize a path to <PATH> ... </PATH> as token ids."""
        ids = [self.tok2id["<PATH>"]]
        for i, (h, r, t) in enumerate(triples_of_path):
            if i == 0:
                ids.extend(self.entity_tokens(h))
            ids.extend(self.relation_tokens(r))
            ids.extend(self.entity_tokens(t))
        ids.append(self.tok2id["</PATH>"])
        return ids
