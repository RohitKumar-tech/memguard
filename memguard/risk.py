"""Risk-adaptive authorization of tool actions that were influenced by memory."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional

# parameters that move data or money outside the current conversation
HIGH_IMPACT = {'bcc', 'cc', 'share_with', 'payee_account', 'forward_to'}


@dataclass
class Action:
    tool: str
    params: Dict[str, str]
    # which memory entry supplied each parameter value (absent => came from the user's request)
    param_sources: Dict[str, str] = field(default_factory=dict)


@dataclass
class Decision:
    verdict: str                   # allow | hold | deny
    reason: str = ''
    culprit: Optional[str] = None  # first memory id responsible when verdict != allow
    culprits: list = field(default_factory=list)  # every responsible memory id


class RiskEngine:
    def __init__(self, internal_domains=('acme.com',)):
        self.internal = tuple(d.lower() for d in internal_domains)

    def is_internal(self, value: str) -> bool:
        v = value.lower()
        return any(v.endswith('@' + d) or v.endswith('.' + d) for d in self.internal)

    def evaluate(self, action: Action, store) -> Decision:
        """Check every high-impact parameter; report all memories that need a human look."""
        holds, denies, reasons = [], [], []
        for name, value in action.params.items():
            src = action.param_sources.get(name)
            if name.split('#')[0] not in HIGH_IMPACT or src is None:
                continue
            e = store.entries.get(src)
            if e is None:
                continue
            if e.status != 'active':
                denies.append(e.id); reasons.append(f'{name} comes from {e.status} memory')
                continue
            if '@' in value and self.is_internal(value):
                continue                                   # low impact: stays inside the organisation
            if e.trust <= 0:
                holds.append(e.id)
                reasons.append(f'external {name}={value!r} comes only from untrusted-origin memory {e.id}')
        if denies:
            return Decision('deny', '; '.join(reasons), denies[0], denies)
        if holds:
            return Decision('hold', '; '.join(reasons), holds[0], list(dict.fromkeys(holds)))
        return Decision('allow')
