"""HTTP gateway so any agent runtime (MCP client, n8n, LangChain, plain scripts) can use MemGuard.

    uvicorn memguard.server:app --port 8099

Set MEMGUARD_DETECTOR=/path/to/models/detector to enable the transformer detector;
without it the rule detector is used.
"""
from __future__ import annotations
import os
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .store import MemoryStore
from .gateway import Gateway
from .detector import Detector, ModelDetector
from .risk import RiskEngine, Action
from .embed import HashEmbedder

app = FastAPI(title='MemGuard gateway', version='0.1')
_det_path = os.environ.get('MEMGUARD_DETECTOR')
gw = Gateway(MemoryStore(HashEmbedder()), Detector(ModelDetector(_det_path) if _det_path else None),
             RiskEngine(os.environ.get('MEMGUARD_INTERNAL_DOMAINS', 'acme.com').split(',')))
_pending: Dict[str, dict] = {}


class WriteReq(BaseModel):
    text: str
    source: str
    parents: List[str] = []
    tool_call: Optional[str] = None


class SearchReq(BaseModel):
    query: str
    k: int = 5


class ActionReq(BaseModel):
    tool: str
    params: Dict[str, str]
    param_sources: Dict[str, str] = {}


class ResolveReq(BaseModel):
    hold_id: str
    approve: bool


@app.post('/memory/write')
def write(r: WriteReq):
    res = gw.write(r.text, r.source, r.parents, r.tool_call)
    e = res.entry
    return dict(id=e.id, status=e.status, trust=e.trust, flagged=res.flagged, score=round(res.score, 3), version=gw.store.version)


@app.post('/memory/search')
def search(r: SearchReq):
    return [dict(id=e.id, text=e.text, source=e.source, trust=e.trust) for e in gw.retrieve(r.query, r.k)]


@app.post('/action/authorize')
def authorize(r: ActionReq):
    d = gw.authorize(Action(r.tool, r.params, r.param_sources))
    out = dict(verdict=d.verdict, reason=d.reason, culprits=d.culprits)
    if d.verdict == 'hold':
        hid = f'h{len(_pending) + 1}'
        _pending[hid] = dict(culprits=d.culprits)
        out['hold_id'] = hid
    return out


@app.post('/action/resolve')
def resolve(r: ResolveReq):
    h = _pending.pop(r.hold_id, None)
    if h is None:
        raise HTTPException(404, 'unknown hold')
    if r.approve:
        return dict(rolled_back=[], new=[])
    rolled, new = [], []
    for cid in h['culprits']:
        v, n = gw.reject(cid)
        rolled += v; new += [e.id for e in n]
    return dict(rolled_back=rolled, new=new)


@app.get('/audit/verify')
def verify():
    return dict(chain_ok=gw.store.verify_chain(), records=gw.store.version)


@app.get('/audit/log')
def log(limit: int = 50):
    return gw.store.log[-limit:]
