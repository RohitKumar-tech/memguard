"""The MemGuard gateway: the single enforcement point between an agent and its memory/tools.

Each defence layer can be switched off so the ablations in bench/run_eval.py are meaningful.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
from .store import MemoryStore, MemoryEntry, ACTIVE, QUARANTINED, POISONED
from .provenance import Trust, source_trust, derive_trust
from .detector import Detector
from .risk import RiskEngine, Action, Decision


def default_rederive(old: MemoryEntry, clean_parents: List[MemoryEntry]) -> str:
    """Rebuild a derived summary from its surviving parents only."""
    return 'Summary: ' + ' '.join(p.text for p in clean_parents)


@dataclass
class WriteResult:
    entry: MemoryEntry
    flagged: bool
    score: float


class Gateway:
    def __init__(self, store: MemoryStore, detector: Optional[Detector] = None, risk: Optional[RiskEngine] = None,
                 use_detector=True, use_provenance=True, use_risk=True, use_rollback=True, trust_weight=0.35,
                 scan_trusted=False):
        self.store, self.detector, self.risk = store, detector, risk or RiskEngine()
        self.use_detector, self.use_provenance = use_detector and detector is not None, use_provenance
        self.use_risk, self.use_rollback, self.trust_weight = use_risk, use_rollback, trust_weight
        self.scan_trusted = scan_trusted               # also scan writes from the trusted user channel
        self.holds = 0

    # ---- memory writes --------------------------------------------------
    def write(self, text: str, source: str, parents: Optional[List[str]] = None,
              tool_call: Optional[str] = None) -> WriteResult:
        parents = parents or []
        if self.use_provenance:
            trust = derive_trust(self.store.entries[p].trust for p in parents) if parents else source_trust(source)
        else:
            trust = Trust.USER                      # no provenance: everything looks equally trusted
        flagged, score = False, 0.0
        if self.use_detector and (not self.use_provenance or self.scan_trusted or trust < Trust.USER):
            (flagged, score), = self.detector.flag([text])
        status = QUARANTINED if flagged else ACTIVE
        e = self.store.write(text, source, trust, parents, status, tool_call, meta={'score': score})
        return WriteResult(e, flagged, score)

    def retrieve(self, query: str, k: int = 5) -> List[MemoryEntry]:
        return self.store.search(query, k, trust_weight=self.trust_weight if self.use_provenance else 0.0)

    # ---- actions --------------------------------------------------------
    def authorize(self, action: Action) -> Decision:
        if not self.use_risk:
            return Decision('allow')
        d = self.risk.evaluate(action, self.store)
        if d.verdict == 'hold':
            self.holds += 1
        return d

    def reject(self, culprit: Optional[str]):
        """A reviewer judged this memory malicious: contain it (and, with rollback, everything derived from it)."""
        if culprit is None:
            return [], []
        if self.use_rollback:
            return self.store.rollback(culprit, default_rederive)
        self.store.set_status(culprit, POISONED, 'reviewer rejected')
        return [culprit], []
