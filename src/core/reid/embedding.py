from typing import List, Dict, Any, Optional, Tuple
import numpy as np

try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover - optional during scaffold
    faiss = None  # type: ignore


class ReidIndex:
    def __init__(self, dim: int = 256) -> None:
        self.dim = dim
        self.embeddings: List[np.ndarray] = []
        self.global_ids: List[str] = []
        self._index = faiss.IndexFlatIP(dim) if faiss is not None else None

    def add(self, global_id: str, emb: np.ndarray) -> None:
        emb = emb.astype(np.float32)
        if np.linalg.norm(emb) > 0:
            emb = emb / (np.linalg.norm(emb) + 1e-8)
        self.embeddings.append(emb)
        self.global_ids.append(global_id)
        if self._index is not None:
            self._index.add(emb.reshape(1, -1))

    def search(self, emb: np.ndarray, topk: int = 1) -> Optional[Tuple[str, float]]:
        if len(self.embeddings) == 0:
            return None
        emb = emb.astype(np.float32)
        if np.linalg.norm(emb) > 0:
            emb = emb / (np.linalg.norm(emb) + 1e-8)
        if self._index is not None:
            D, I = self._index.search(emb.reshape(1, -1), topk)
            idx = int(I[0][0])
            return self.global_ids[idx], float(D[0][0])
        # Fallback: brute-force cosine similarity
        sims = [float(np.dot(e, emb)) for e in self.embeddings]
        idx = int(np.argmax(sims))
        return self.global_ids[idx], sims[idx]


class ReidEmbedder:
    """Stub embedder. Replace with a trained ReID network."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, crop_bgr: np.ndarray) -> np.ndarray:  # noqa: F821
        rng = np.random.default_rng(seed=int(crop_bgr.size) % 2**32)
        vec = rng.random(self.dim).astype(np.float32)
        vec /= (np.linalg.norm(vec) + 1e-8)
        return vec


