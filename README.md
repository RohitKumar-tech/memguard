# MemGuard

**Provenance-tracked, rollback-capable memory for MCP / n8n agents.**

LLM agents keep notes, preferences and retrieved facts across sessions. If an attacker gets one
malicious entry into that memory (for example through a document the agent fetched), the entry can
steer every later session. MemGuard is a gateway that sits between an agent and its memory and tools:

* **Provenance.** Every write is labelled with its source and a trust level
  (`user` > verified system such as CRM > untrusted tool output). A derived memory inherits the
  *lowest* trust of its parents. Unknown sources fail closed.
* **Write-time detection.** A fine-tuned DeBERTa-v3-small plus lexical rules flags instruction-like
  text and quarantines it.
* **Risk-adaptive approval.** Actions whose high-impact parameters (cc/bcc, share-with, payee
  account) come only from untrusted-origin memory and point outside the organisation are held for a
  human; internal addresses and user-sourced values pass.
* **Versioning and rollback.** Memory is an append-only, SHA-256 hash-chained log. When a reviewer
  rejects an entry, MemGuard traces everything derived from it, rolls all of it back and re-derives
  the dependents from their clean parents.

**Website:** https://demo-six-kappa-23.vercel.app (overview, how it works, results, interactive simulation, research notes). Source in `website/` (static HTML, no build step required; `build_site.py` regenerates the pages).

Components: `memguard/` (store, provenance, detector, risk engine, gateway), a FastAPI server
(`memguard/server.py`), an MCP server (`memguard/mcp_server.py`), an n8n workflow
(`n8n/memguard-guarded-agent.json`), the benchmark and evaluation (`bench/`), and detector training
(`train/`).

## Results

Benchmark: **MemBench-Lite**, 600 episodes x 3 seeds (50% attack), identical episodes for every
defence. Five poison classes: explicit injection, jailbreak text from a public dataset,
declarative (no imperative cues), payee swap, external share. Reviewer is simulated at 95% accuracy.
Mean ± std over seeds.

| Defense | ASR % (session 2) | ASR % (repeat, session 3) | Benign completion % | Approvals / clean episode |
|---|---|---|---|---|
| No defense | 83.1 ± 1.6 | 83.1 ± 1.6 | 100.0 | 0.00 |
| Retrieval-time filter | 46.0 ± 2.5 | 46.0 ± 2.5 | 61.4 | 0.00 |
| Write-time filter | 45.8 ± 2.4 | 45.8 ± 2.4 | 61.4 | 0.00 |
| Provenance + risk only | 3.3 ± 0.2 | 0.3 ± 0.3 | 99.9 | 0.46 |
| MemGuard, no rollback | 1.3 ± 0.4 | 0.0 | 89.0 | 0.35 |
| MemGuard, no risk engine | 44.9 ± 2.8 | 44.9 ± 2.8 | 89.3 | 0.00 |
| MemGuard, no detector (rollback on) | 2.1 ± 0.9 | 0.1 ± 0.2 | 98.4 | 0.45 |
| **MemGuard, full** | **1.0 ± 0.5** | **0.0** | 88.3 | 0.35 |
| MemGuard, full, rules-only detector | 1.9 ± 0.2 | 0.1 ± 0.2 | 98.7 | 0.46 |

Figures: `results/fig_main.png`, `results/fig_by_kind.png`. Raw per-episode data: `results/eval_main.csv`.
Overhead per call is microseconds (`write_ms`, `auth_ms` in `results/eval_main.json`).

What the numbers say:

1. **Provenance plus the risk engine does most of the work** (83% to 3%). The transformer detector
   adds little on top (3.3% to 1.0%) and **costs benign tasks**: it flags about 10% of benign writes
   and completion falls from 99.9% to 88%. The best utility/safety trade-off here is the
   no-detector configuration with rollback.
2. **Detectors alone are weak.** Trained on public injection data the detector scores F1 0.994 on its
   own test set but only **F1 0.295 on the external deepset dataset** (recall 0.175); TF-IDF drops
   from 0.986 to 0.154 (`results/detector_metrics.json`). Declarative poison ("the vendor's
   accountant is ...") passes write and retrieval filters 83% of the time.
3. **Rollback has only a small measurable effect in this benchmark.** It removes derived memories
   built from poison, and repeat-attack success falls from 0.3% to 0.1% (provenance + risk with and
   without rollback), but the difference is within noise, and it does **not** reduce repeat
   approvals (0.33 vs 0.32 per attack episode). Its value (clean re-derivation, audit trail) is real
   by design but not demonstrated strongly by these numbers.
4. **Human cost is real**: about 0.35-0.46 approvals per clean episode, mostly benign external
   addresses mentioned by untrusted documents.

### Comparison with an existing open-source detector

To check the result is not an artefact of our own detector, the same episodes were re-run with
`protectai/deberta-v3-base-prompt-injection-v2` (Apache-2.0, a widely used open model) in place of our
fine-tuned DeBERTa, with no extra rules (`results/eval_protectai.json`).

| Setup | ASR % | Benign completion % | Notes |
|---|---|---|---|
| ProtectAI detector as write-time filter | 46.5 ± 2.4 | 83.7 ± 4.0 | 3.9% of benign writes flagged |
| ProtectAI detector as retrieval-time filter | 46.5 ± 2.4 | 83.7 ± 4.0 | |
| **MemGuard gateway + ProtectAI detector** | **1.1 ± 0.7** | **99.0 ± 0.3** | 0.46 approvals per clean episode |

Detector-only accuracy (`results/external_detector_*.json`): ProtectAI scores F1 0.898 on the
safe-guard test split and F1 0.576 on deepset (recall 0.41), versus our model's 0.994 and 0.295. Its
training data is not fully documented here, so the deepset figure may be optimistic if that set was
in its training mix. Takeaway: a stronger off-the-shelf detector gives a better trade-off inside
MemGuard than our own fine-tune, and the gateway cuts attack success from about 46% to about 1% over
the same detector used as a plain filter. **No commercial product, and none of the published
memory-poisoning defenses (CaMeL, APPA, etc.), was run head-to-head**; their code or access was not
available to this project, so no claim is made against them.

### Stress test: poison through a trusted channel (a known failure)

If the attacker's text is written under the trusted `user` source (a MINJA-style attack that works
through ordinary queries), provenance has nothing to catch:

| Defense | ASR % | Benign completion % |
|---|---|---|
| No defense | 83.1 | 100.0 |
| Write-time filter | 45.8 | 61.4 |
| MemGuard (provenance + risk) | 98.8 | 99.9 |
| MemGuard full | 99.3 | 88.6 |
| MemGuard full, scanning trusted writes too | 50.6 | 60.9 |

MemGuard's guarantee is conditional on correct channel labelling. Scanning trusted writes halves
the attack but costs about 40% of benign tasks with the current detector. This is the main open
problem.

## Limitations (read before citing any number)

* The benchmark is **synthetic and written by the authors**; its poison arrives through untrusted
  channels by default, which favours provenance by construction. It is not MPBench, AgentPoison or
  MINJA, and results here are **not comparable** with theirs.
* The agent is **scripted**, not an LLM. It fills tool parameters from retrieved memory, which is
  the behaviour poisoning exploits, but real models differ in susceptibility.
* The reviewer is simulated (95% accurate); real human behaviour will differ and approval fatigue is
  not modelled.
* The detector is trained on public prompt-injection data (safe-guard-prompt-injection, mostly
  synthetic) and generalises poorly to memory-style text.
* The n8n workflow is a template validated as JSON but **not executed against a live n8n instance**.
  The MCP server was exercised with a real MCP client over stdio (`tests/mcp_client_check.py`): all five tools called, poison quarantined, action held, rollback and audit chain verified.
* The HTTP gateway was exercised end to end with a live local server (write, quarantine, hold, audit).

## Quick start

```bash
pip install fastapi uvicorn numpy pandas pyarrow scikit-learn torch transformers sentence-transformers matplotlib pytest mcp
python scripts/get_data.py              # downloads public datasets
python train/train_detector.py          # ~2 min on a laptop GPU
python -m pytest -q tests               # 8 tests
python bench/run_eval.py --n 600 --seeds 3 --tag main
python bench/make_plots.py
MEMGUARD_DETECTOR=models/detector uvicorn memguard.server:app --port 8099
```

## Data and licences

`deepset/prompt-injections` (Apache-2.0) and `xTRam1/safe-guard-prompt-injection` are downloaded
from Hugging Face by `scripts/get_data.py` and are not redistributed here. Check each dataset card
for its licence before reuse. Trained weights are not committed.

## Related work

AgentPoison (Chen et al., NeurIPS 2024), MINJA (Dong et al., 2025), CaMeL (Debenedetti et al., 2025),
and 2026 work on memory poisoning, long-term-memory security and recoverable information-flow
control (MPBench, APPA and surveys cited in the project deck).
