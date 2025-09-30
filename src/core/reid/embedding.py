from typing import List, Dict, Any, Optional, Tuple
import numpy as np

try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover - optional during scaffold
    faiss = None  # type: ignore


class ReidIndex:
    """Simple ReID index with cosine search, top-k candidates, and per-ID last-seen/EMA.

    Implementation notes:
    - Stores a bank of embeddings and parallel global_id mapping for search.
    - Maintains an EMA feature per global ID for lightweight online updates.
    - Tracks last_seen timestamps per global ID for TTL filtering (set via set_ttl_seconds).
    - FAISS (if available) is used for fast IP search over the raw bank; fallback is numpy.
    """

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim
        self.embeddings: List[np.ndarray] = []
        self.global_ids: List[str] = []
        self._index = faiss.IndexFlatIP(dim) if faiss is not None else None
        # Per-ID derived state
        self.id_to_ema: Dict[str, np.ndarray] = {}
        self.id_to_last_seen: Dict[str, float] = {}
        self._ema_momentum: float = 0.9
        self._ttl_seconds: int = 60

    def set_ema_momentum(self, momentum: float) -> None:
        self._ema_momentum = float(np.clip(momentum, 0.0, 1.0))

    def set_ttl_seconds(self, ttl_seconds: int) -> None:
        self._ttl_seconds = max(0, int(ttl_seconds))

    def _normalize(self, vec: np.ndarray) -> np.ndarray:
        v = vec.astype(np.float32)
        n = float(np.linalg.norm(v))
        if n > 0:
            v = v / (n + 1e-8)
        return v

    def add(self, global_id: str, emb: np.ndarray, now_ts: Optional[float] = None) -> None:
        emb_n = self._normalize(emb)
        self.embeddings.append(emb_n)
        self.global_ids.append(global_id)
        if self._index is not None:
            self._index.add(emb_n.reshape(1, -1))
        # Initialize EMA and last_seen
        self.id_to_ema[global_id] = emb_n.copy()
        if now_ts is not None:
            self.id_to_last_seen[global_id] = now_ts

    def update(self, global_id: str, emb: np.ndarray, now_ts: Optional[float] = None) -> None:
        emb_n = self._normalize(emb)
        prev = self.id_to_ema.get(global_id)
        if prev is None:
            self.id_to_ema[global_id] = emb_n.copy()
        else:
            m = self._ema_momentum
            self.id_to_ema[global_id] = m * prev + (1.0 - m) * emb_n
            self.id_to_ema[global_id] = self._normalize(self.id_to_ema[global_id])
        if now_ts is not None:
            self.id_to_last_seen[global_id] = now_ts
        # Optionally append to bank to retain some diversity
        self.embeddings.append(emb_n)
        self.global_ids.append(global_id)
        if self._index is not None:
            self._index.add(emb_n.reshape(1, -1))

    def mark_seen(self, global_id: str, now_ts: float) -> None:
        self.id_to_last_seen[global_id] = now_ts

    def _is_alive(self, global_id: str, now_ts: float) -> bool:
        if self._ttl_seconds <= 0:
            return True
        last = self.id_to_last_seen.get(global_id)
        if last is None:
            return True
        return (now_ts - last) <= self._ttl_seconds

    def search_topk(self, emb: np.ndarray, topk: int = 5, now_ts: Optional[float] = None) -> List[Tuple[str, float]]:
        """Return top-k candidate (global_id, similarity) after aggregating per-id max sim.
        TTL filtering applied if now_ts is provided.
        """
        if len(self.embeddings) == 0:
            return []
        q = self._normalize(emb)
        if self._index is not None:
            k = min(topk * 5, len(self.embeddings))
            D, I = self._index.search(q.reshape(1, -1), k)
            sims = [float(D[0][i]) for i in range(k)]
            ids = [self.global_ids[int(I[0][i])] for i in range(k)]
        else:
            sims_all = np.dot(np.stack(self.embeddings), q)
            idxs = np.argsort(-sims_all)[: min(topk * 5, sims_all.shape[0])]
            sims = [float(sims_all[i]) for i in idxs]
            ids = [self.global_ids[int(i)] for i in idxs]
        # Aggregate by global_id (take max sim per id)
        best_by_id: Dict[str, float] = {}
        for gid, s in zip(ids, sims):
            if now_ts is not None and not self._is_alive(gid, now_ts):
                continue
            if gid not in best_by_id or s > best_by_id[gid]:
                best_by_id[gid] = s
        # Sort and return topk
        candidates = sorted(best_by_id.items(), key=lambda x: x[1], reverse=True)[:topk]
        return candidates

    def search(self, emb: np.ndarray, topk: int = 1, now_ts: Optional[float] = None) -> Optional[Tuple[str, float]]:
        cands = self.search_topk(emb, topk=topk, now_ts=now_ts)
        if not cands:
            return None
        return cands[0]


class ReidEmbedder:
    """Stub embedder. Replace with a trained ReID network."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, crop_bgr: np.ndarray) -> np.ndarray:  # noqa: F821
        rng = np.random.default_rng(seed=int(crop_bgr.size) % 2**32)
        vec = rng.random(self.dim).astype(np.float32)
        vec /= (np.linalg.norm(vec) + 1e-8)
        return vec


