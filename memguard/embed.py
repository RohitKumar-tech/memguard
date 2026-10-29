"""Embedders. The default is dependency-free so the gateway and the tests run anywhere."""
from __future__ import annotations
import hashlib, re
from typing import List
import numpy as np


class HashEmbedder:
    """Bag of hashed word uni/bi-grams, L2-normalised. Crude but deterministic and offline."""

    def __init__(self, dim: int = 512):
        self.dim = dim

    def __call__(self, texts: List[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            w = re.findall(r'\w+', t.lower())
            for tok in w + [a + '_' + b for a, b in zip(w, w[1:])]:
                h = int(hashlib.md5(tok.encode()).hexdigest()[:8], 16)
                out[i, h % self.dim] += 1.0 if (h >> 16) & 1 else -1.0
        n = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.maximum(n, 1e-9)
