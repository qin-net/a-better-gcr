import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import torch
from src.graph_constrained_decoding import GraphConstrainedDecoding


class Tokenizer:
    def __len__(self):
        return 10


class EmptyTrie:
    def get(self, prefix):
        return []


def test_fallback_counter_does_not_change_allowed_tokens():
    decoder = GraphConstrainedDecoding(Tokenizer(), EmptyTrie(), 7, 8)
    assert decoder.allowed_tokens_fn(0, torch.tensor([1, 7, 2])) == list(range(10))
    assert decoder.empty_prefix_fallbacks == 1
    assert decoder.allowed_tokens_fn(0, torch.tensor([1, 7, 2, 8])) == list(range(10))
    assert decoder.empty_prefix_fallbacks == 1


def test_prefilled_marker_immediately_activates_trie():
    from src.trie import Trie
    decoder = GraphConstrainedDecoding(Tokenizer(), Trie([[7, 2, 3, 8]]), 7, 8)
    assert decoder.allowed_tokens_fn(0, torch.tensor([1, 7])) == [2]
    assert decoder.allowed_tokens_fn(0, torch.tensor([1, 7, 2])) == [3]
    assert decoder.empty_prefix_fallbacks == 0
    assert decoder.allowed_tokens_fn(0, torch.tensor([1, 7, 2, 8])) == list(range(10))
    assert decoder.empty_prefix_fallbacks == 0
