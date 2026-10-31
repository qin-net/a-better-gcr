"""Token-level trie: the KG-Trie from the paper, at word granularity.

Same contract as src/trie.py in the official repo -- get(prefix) returns the
set of token ids that can legally follow. The difference is that this one is
readable, so we can print and draw it.
"""


class Trie:
    def __init__(self, sequences=None):
        self.root = {}
        self.n_sequences = 0
        for seq in sequences or []:
            self.add(seq)

    def add(self, sequence):
        node = self.root
        for tok in sequence:
            node = node.setdefault(tok, {})
        node["$"] = True  # terminal marker
        self.n_sequences += 1

    def get(self, prefix):
        node = self.root
        for tok in prefix:
            if tok not in node:
                return []
            node = node[tok]
        return [k for k in node if k != "$"]

    def contains(self, sequence):
        node = self.root
        for tok in sequence:
            if tok not in node:
                return False
            node = node[tok]
        return node.get("$", False)

    def __len__(self):
        return self.n_sequences
