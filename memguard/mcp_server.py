"""MemGuard as an MCP server: any MCP client (Claude Desktop, agents) can use guarded memory.

    python -m memguard.mcp_server        # stdio transport

Tools: memory_write, memory_search, authorize_action, resolve_hold, audit_verify.
Written against the `mcp` 2.x Python SDK (MCPServer).
"""
from __future__ import annotations
import os
from typing import Dict, List, Optional
from mcp.server.mcpserver import MCPServer
from .store import MemoryStore
from .gateway import Gateway
from .detector import Detector, ModelDetector
from .risk import RiskEngine, Action
from .embed import HashEmbedder

_det = os.environ.get('MEMGUARD_DETECTOR')
gw = Gateway(MemoryStore(HashEmbedder()), Detector(ModelDetector(_det) if _det else None), RiskEngine())
holds: Dict[str, List[str]] = {}
mcp = MCPServer('memguard')


@mcp.tool()
def memory_write(text: str, source: str, parents: Optional[List[str]] = None) -> dict:
    """Store a memory. `source` names where it came from (user, crm, fetch_doc, email, web, ...)."""
    r = gw.write(text, source, parents or [])
    return dict(id=r.entry.id, status=r.entry.status, trust=r.entry.trust, flagged=r.flagged)


@mcp.tool()
def memory_search(query: str, k: int = 5) -> list:
    """Retrieve active memories, trust-weighted. Quarantined or rolled-back entries never appear."""
    return [dict(id=e.id, text=e.text, source=e.source, trust=e.trust) for e in gw.retrieve(query, k)]


@mcp.tool()
def authorize_action(tool: str, params: Dict[str, str], param_sources: Optional[Dict[str, str]] = None) -> dict:
    """Ask before executing a tool call. Returns allow, hold (needs a human) or deny."""
    d = gw.authorize(Action(tool, params, param_sources or {}))
    out = dict(verdict=d.verdict, reason=d.reason, culprits=d.culprits)
    if d.verdict == 'hold':
        hid = f'h{len(holds) + 1}'; holds[hid] = d.culprits; out['hold_id'] = hid
    return out


@mcp.tool()
def resolve_hold(hold_id: str, approve: bool) -> dict:
    """A human decision on a held action. Rejecting rolls back the culprit memory and everything derived from it."""
    culprits = holds.pop(hold_id, [])
    if approve:
        return dict(rolled_back=[])
    rolled: List[str] = []
    for c in culprits:
        rolled += gw.reject(c)[0]
    return dict(rolled_back=rolled)


@mcp.tool()
def audit_verify() -> dict:
    """Verify the tamper-evident hash chain of the memory log."""
    return dict(chain_ok=gw.store.verify_chain(), records=gw.store.version)


if __name__ == '__main__':
    mcp.run()
