"""Score an off-the-shelf detector on the same two public datasets used for our own detector."""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from memguard.detector import ModelDetector
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
name = sys.argv[1]
det = ModelDetector(name)
print('labels:', det.model.config.id2label)
D = lambda n: pd.read_parquet(os.path.join(ROOT, 'data', n))
sets = {'safeguard_test': D('xTRam1_safe-guard-prompt-injection_test.parquet'),
        'deepset_all': pd.concat([D('deepset_prompt-injections_train.parquet'), D('deepset_prompt-injections_test.parquet')])}
out = {}
for k, df in sets.items():
    s = det.score(df.text.tolist()); y = df.label.values; p = (pd.Series(s) >= .5).astype(int).values
    out[k] = dict(f1=f1_score(y, p), precision=precision_score(y, p), recall=recall_score(y, p),
                  fpr=float(((p == 1) & (y == 0)).sum() / (y == 0).sum()), auc=roc_auc_score(y, s), n=len(y))
    print(k, {a: round(b, 3) for a, b in out[k].items()})
json.dump(out, open(os.path.join(ROOT, 'results', 'external_detector_' + name.replace('/', '_') + '.json'), 'w'), indent=1)
