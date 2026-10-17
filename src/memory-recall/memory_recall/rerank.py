"""問いと塊を並べて読み比べる reranker（cross-encoder）。models の下のモデルを transformers で動かす。"""

from __future__ import annotations

import os
from pathlib import Path

MODEL = "ruri-v3-reranker-310m"
MAX_LENGTH = 1024
BATCH = 8


def models_dir() -> Path:
    return Path(os.environ.get("WORKSPACE") or "/Users/taro/Workspace") / "models"


class Reranker:
    def __init__(self):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.name = MODEL
        path = models_dir() / self.name
        self.torch = torch
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(path)
        self.model = AutoModelForSequenceClassification.from_pretrained(path, dtype=torch.float16 if self.device == "mps" else torch.float32)
        self.model.to(self.device).eval()

    def score(self, query: str, passages: list[str]) -> list[float]:
        out: list[float] = []
        with self.torch.no_grad():
            for i in range(0, len(passages), BATCH):
                batch = passages[i : i + BATCH]
                inputs = self.tokenizer([query] * len(batch), batch, padding=True, truncation="only_second",
                                        max_length=MAX_LENGTH, return_tensors="pt").to(self.device)
                out += self.model(**inputs).logits.view(-1).float().cpu().tolist()
        return out
