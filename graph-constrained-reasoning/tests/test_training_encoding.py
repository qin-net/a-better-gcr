import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('train_cuda_lora', Path(__file__).resolve().parents[1] / 'workflow/train_cuda_lora.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Tokenizer:
    def apply_chat_template(self, chat, **kwargs):
        return [1, 2, 3] if len(chat) == 1 else [1, 2, 3, 4, 5]


def test_only_assistant_tokens_are_supervised():
    row = module.encode_pair(Tokenizer(), 'question', 'path', 8)
    assert row['labels'] == [-100, -100, -100, 4, 5]
    assert row['attention_mask'] == [1] * 5


def test_long_paths_are_rejected_without_truncation():
    assert module.encode_pair(Tokenizer(), 'question', 'path', 4) is None
