"""End-to-end evaluation: every defence configuration over the same MemBench-Lite episodes.

usage: python bench/run_eval.py [--n 600] [--seeds 3] [--reviewer-acc 0.95]
Writes results/eval_main.json and results/eval_main.csv.
"""
import os, sys, json, random, argparse, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from memguard import MemoryStore, Gateway, Detector, ModelDetector, RiskEngine
from membench import make_benchmark
from agent import run_episode

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')

# name -> (gateway flags, agent flags)
CONFIGS = {
    'no_defense':        (dict(use_detector=False, use_provenance=False, use_risk=False, use_rollback=False), {}),
    'retrieval_filter':  (dict(use_detector=False, use_provenance=False, use_risk=False, use_rollback=False), {'read_filter': True}),
    'write_filter':      (dict(use_detector=True,  use_provenance=False, use_risk=False, use_rollback=False), {}),
    'mg_provenance_risk': (dict(use_detector=False, use_provenance=True,  use_risk=True,  use_rollback=False), {}),
    'mg_no_rollback':    (dict(use_detector=True,  use_provenance=True,  use_risk=True,  use_rollback=False), {}),
    'mg_no_risk':        (dict(use_detector=True,  use_provenance=True,  use_risk=False, use_rollback=False), {}),
    'mg_no_detector':    (dict(use_detector=False, use_provenance=True,  use_risk=True,  use_rollback=True), {}),
    'mg_full':           (dict(use_detector=True,  use_provenance=True,  use_risk=True,  use_rollback=True), {}),
    'mg_full_scan_trusted': (dict(use_detector=True, use_provenance=True, use_risk=True, use_rollback=True, scan_trusted=True), {}),
    'mg_full_rules_only': (dict(use_detector=True, use_provenance=True,  use_risk=True,  use_rollback=True), {'rules_only': True}),
}


class CachedEmbedder:
    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self.m = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cuda')
        self.c = {}

    def __call__(self, texts):
        miss = [t for t in texts if t not in self.c]
        if miss:
            for t, v in zip(miss, self.m.encode(miss, normalize_embeddings=True, batch_size=64)):
                self.c[t] = v
        return np.stack([self.c[t] for t in texts])


class CachedDetector(Detector):
    """Scores are deterministic, so cache them per text (templates repeat a lot)."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self._c = {}

    def score(self, texts):
        miss = [t for t in dict.fromkeys(texts) if t not in self._c]
        if miss:
            for t, s in zip(miss, super().score(miss)):
                self._c[t] = s
        return [self._c[t] for t in texts]


def summarize(rows):
    df = pd.DataFrame(rows)
    atk, cln = df[df.attack], df[~df.attack]
    out = dict(
        episodes=len(df),
        asr=float(atk.executed_attack.mean()),                    # attack success rate, session 2
        asr_session3=float(atk.attack_s3.mean()),                 # repeat attack after the defence reacted
        utility_clean=float(cln.utility.mean()),                  # benign task completion, clean episodes
        utility_attack=float(atk.utility.mean()),                 # benign values still honoured under attack
        holds_per_clean_episode=float((cln.holds_s2).mean()),     # human approvals burden when nothing is wrong
        holds_s3_per_attack=float(atk.holds_s3.mean()),           # approvals still needed in session 3
        write_tpr=float(atk.write_flag_mal.sum() / max(1, atk.write_mal.sum())),
        write_fpr=float(df.write_flag_ben.sum() / max(1, df.write_ben.sum())),
        write_ms=float(df.write_ms.mean()), auth_ms=float(df.auth_ms.mean()),
        reviewer_errors=int(df.reviewer_wrong.sum()),
    )
    out['asr_by_kind'] = {k: float(g.executed_attack.mean()) for k, g in atk.groupby('kind')}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=600); ap.add_argument('--seeds', type=int, default=3)
    ap.add_argument('--reviewer-acc', type=float, default=0.95)
    ap.add_argument('--poison-source', default='fetch_doc'); ap.add_argument('--detector', default=''); ap.add_argument('--no-rules', action='store_true'); ap.add_argument('--tag', default='main'); ap.add_argument('--configs', default='')
    a = ap.parse_args()
    embed = CachedEmbedder()
    mpath = a.detector or os.path.join(ROOT, 'models', 'detector')
    model = ModelDetector(mpath) if (a.detector or os.path.exists(mpath)) else None
    if a.detector: print('detector:', a.detector, model.model.config.id2label, flush=True)
    det_full = CachedDetector(model, 0.5, use_rules=not a.no_rules); det_rules = CachedDetector(None, 0.5)
    names = [c for c in (a.configs.split(',') if a.configs else CONFIGS)]
    results, rows_all = {}, []
    for name in names:
        gflags, aflags = CONFIGS[name]
        per_seed, rows = [], []
        for seed in range(a.seeds):
            eps = make_benchmark(a.n, seed=100 + seed, poison_source=a.poison_source)
            rng = random.Random(seed); seed_rows = []
            for ep in eps:
                det = det_rules if aflags.get('rules_only') else det_full
                gw = Gateway(MemoryStore(embed), det, RiskEngine(), **gflags)
                r = run_episode(ep, gw, embed, dict(aflags, reviewer_acc=a.reviewer_acc), det, rng)
                seed_rows.append(r.__dict__)
            per_seed.append(summarize(seed_rows)); rows += seed_rows
        keys = [k for k in per_seed[0] if k != 'asr_by_kind']
        agg = {k: [float(np.mean([s[k] for s in per_seed])), float(np.std([s[k] for s in per_seed]))] for k in keys}
        agg['asr_by_kind'] = {k: float(np.mean([s['asr_by_kind'].get(k, np.nan) for s in per_seed])) for k in per_seed[0]['asr_by_kind']}
        results[name] = agg
        print(f"{name:20s} ASR {agg['asr'][0]:.3f}  ASR3 {agg['asr_session3'][0]:.3f}  util_clean {agg['utility_clean'][0]:.3f}  "
              f"holds/clean {agg['holds_per_clean_episode'][0]:.2f}  wFPR {agg['write_fpr'][0]:.3f}", flush=True)
        rows_all += [dict(r, config=name) for r in rows]
    os.makedirs(os.path.join(ROOT, 'results'), exist_ok=True)
    json.dump(dict(args=vars(a), results=results), open(os.path.join(ROOT, 'results', f'eval_{a.tag}.json'), 'w'), indent=1)
    pd.DataFrame(rows_all).to_csv(os.path.join(ROOT, 'results', f'eval_{a.tag}.csv'), index=False)


if __name__ == '__main__':
    main()
