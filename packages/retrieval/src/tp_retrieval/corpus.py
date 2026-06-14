"""Curated POI corpus — the ground truth retrieval pulls from.

Committed JSONL keeps the corpus reproducible (the eval baseline depends on it).
Production swaps this loader for client documents / a larger POI dataset.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

_DEFAULT_CORPUS = Path(__file__).resolve().parents[4] / "data" / "corpus" / "pois.jsonl"


class CorpusDoc(BaseModel):
    city: str
    name: str
    category: str
    description: str
    latitude: float
    longitude: float
    source: str = "seed"

    def embed_text(self) -> str:
        return f"{self.name} ({self.category}) in {self.city}. {self.description}"


def load_corpus(path: Path | None = None) -> list[CorpusDoc]:
    target = path or _DEFAULT_CORPUS
    docs: list[CorpusDoc] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            docs.append(CorpusDoc.model_validate(json.loads(line)))
    return docs
