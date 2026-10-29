"""Append-only, hash-chained memory store with versioned state, dependency tracing and rollback."""
from __future__ import annotations
import hashlib, json, time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional
import numpy as np

ACTIVE, QUARANTINED, POISONED, ROLLED_BACK = 'active', 'quarantined', 'poisoned', 'rolled_back'


@dataclass
class MemoryEntry:
    id: str
    text: str
    source: str
    trust: int
    parents: List[str] = field(default_factory=list)
    status: str = ACTIVE
    seq: int = 0                     # log position of the write that created it
    tool_call: Optional[str] = None
    meta: dict = field(default_factory=dict)
    emb: Optional[np.ndarray] = None


def _h(prev: str, payload: dict) -> str:
    return hashlib.sha256((prev + json.dumps(payload, sort_keys=True)).encode()).hexdigest()


class MemoryStore:
    """Every change is a record in a hash-chained log, so tampering is detectable and any
    past version can be reconstructed from the log prefix."""

    def __init__(self, embedder: Optional[Callable[[List[str]], np.ndarray]] = None):
        self.log: List[dict] = []
        self.entries: Dict[str, MemoryEntry] = {}
        self.embedder = embedder
        self._n = 0

    # ---- log primitives -------------------------------------------------
    def _append(self, op: str, **payload) -> dict:
        prev = self.log[-1]['hash'] if self.log else 'genesis'
        rec = {'seq': len(self.log), 'op': op, 'ts': time.time(), **payload}
        rec['prev'] = prev
        rec['hash'] = _h(prev, {k: v for k, v in rec.items() if k not in ('hash', 'ts')})
        self.log.append(rec)
        return rec

    def verify_chain(self) -> bool:
        prev = 'genesis'
        for rec in self.log:
            body = {k: v for k, v in rec.items() if k not in ('hash', 'ts')}
            if rec['prev'] != prev or _h(prev, body) != rec['hash']:
                return False
            prev = rec['hash']
        return True

    @property
    def version(self) -> int:
        return len(self.log)

    # ---- writes ---------------------------------------------------------
    def write(self, text: str, source: str, trust: int, parents=None, status: str = ACTIVE,
              tool_call: Optional[str] = None, meta: Optional[dict] = None) -> MemoryEntry:
        self._n += 1
        eid = f'm{self._n}'
        rec = self._append('write', id=eid, text=text, source=source, trust=int(trust),
                           parents=list(parents or []), status=status, tool_call=tool_call)
        e = MemoryEntry(eid, text, source, int(trust), list(parents or []), status, rec['seq'], tool_call, meta or {})
        if self.embedder is not None:
            e.emb = self.embedder([text])[0]
        self.entries[eid] = e
        return e

    def set_status(self, eid: str, status: str, reason: str = '') -> None:
        self._append('status', id=eid, status=status, reason=reason)
        self.entries[eid].status = status

    # ---- graph ----------------------------------------------------------
    def dependents(self, eid: str) -> List[str]:
        """All entries transitively derived from `eid` (BFS over the parent links)."""
        children: Dict[str, List[str]] = {}
        for e in self.entries.values():
            for p in e.parents:
                children.setdefault(p, []).append(e.id)
        seen, queue = [], [eid]
        while queue:
            for c in children.get(queue.pop(0), []):
                if c not in seen:
                    seen.append(c)
                    queue.append(c)
        return seen

    def rollback(self, poisoned_id: str, rederive: Optional[Callable[[MemoryEntry, List[MemoryEntry]], Optional[str]]] = None):
        """Mark the poisoned entry and everything derived from it as rolled back, then re-derive
        each dependent from its remaining clean parents. Returns (rolled_back_ids, new_entries)."""
        from .provenance import derive_trust
        victims = [poisoned_id] + self.dependents(poisoned_id)
        self._append('rollback', root=poisoned_id, victims=victims, restore_to=self.entries[poisoned_id].seq)
        bad = set(victims)
        for v in victims:
            self.entries[v].status = POISONED if v == poisoned_id else ROLLED_BACK
        new = []
        if rederive is not None:
            for v in victims[1:]:
                old = self.entries[v]
                clean = [self.entries[p] for p in old.parents if p not in bad and self.entries[p].status == ACTIVE]
                if not clean:
                    continue
                text = rederive(old, clean)
                if text:
                    new.append(self.write(text, 'derived', derive_trust(c.trust for c in clean),
                                          parents=[c.id for c in clean], meta={'rederived_from': v}))
        return victims, new

    # ---- retrieval ------------------------------------------------------
    def search(self, query: str, k: int = 5, trust_weight: float = 0.0, include=(ACTIVE,)) -> List[MemoryEntry]:
        cands = [e for e in self.entries.values() if e.status in include and e.emb is not None]
        if not cands:
            return []
        q = self.embedder([query])[0]
        sims = np.array([float(e.emb @ q) for e in cands])
        if trust_weight:
            sims = sims * (1.0 - trust_weight * (2 - np.array([e.trust for e in cands])) / 2.0)
        order = np.argsort(-sims)[:k]
        return [cands[i] for i in order]
