import math
import json
from pathlib import Path
from dataclasses import dataclass

@dataclass
class RagEntry:
    text: str
    vector: list[float]

class RagStore:
    def __init__(self, embedding_provider, store_path: Path | str | None=None):
        self.embedding_provider = embedding_provider
        self.entries: list[RagEntry] = []
        self.store_path = Path(store_path) if store_path else None
        if self.store_path and store_path.exists():
            self._load()

    async def add(self, text: str) -> None:
        if not text.strip():
            return
        vector = await self.embedding_provider.embed(text)
        if vector:
            self.entries.append(RagEntry(text=text, vector=vector))
            self._save()
    def _save(self) -> None:
        if not self.store_path:
            return
        data = [{"text": e.text, "vector": e.vector} for e in self.entries]
        tmp = self.store_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.store_path)

    def _load(self) -> None:
        data = json.loads(self.store_path.read_text(encoding="utf-8"))
        self.entries = [RagEntry(text=d["text"], vector=d["vector"]) for d in data]

    async def search(self, query: str, top_k: int = 5, min_score: float = 0.0) -> list[str]:
        if not self.entries:
            return []
        query_vec = await self.embedding_provider.embed(query)
        if not query_vec:
            return []

        scored = [(self._cosine(query_vec, e.vector), e.text) for e in self.entries]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [(s, t) for s, t in scored[:top_k] if s >= min_score]

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        return dot / (na * nb) if na and nb else 0.0