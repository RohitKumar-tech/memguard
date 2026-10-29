"""Train the write-time instruction/injection detector on public data.

Protocol (no leakage into the memory benchmark):
  train : safe-guard-prompt-injection train
  eval  : safe-guard test (in-domain), deepset all 662 (external dataset)
Outputs metrics to results/detector_metrics.json and saves the model to models/detector.
"""
import os, sys, json, time, numpy as np, pandas as pd, torch
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from transformers import AutoTokenizer, AutoModelForSequenceClassification

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
D = lambda n: pd.read_parquet(os.path.join(ROOT, 'data', n))
tr = D('xTRam1_safe-guard-prompt-injection_train.parquet')
te = D('xTRam1_safe-guard-prompt-injection_test.parquet')
ds = pd.concat([D('deepset_prompt-injections_train.parquet'), D('deepset_prompt-injections_test.parquet')])

def metrics(y, p, s):
    fpr = float(((p == 1) & (y == 0)).sum() / max(1, (y == 0).sum()))
    return dict(f1=f1_score(y, p), precision=precision_score(y, p), recall=recall_score(y, p),
                fpr=fpr, auc=roc_auc_score(y, s), n=int(len(y)))

res = {}
# --- baseline: TF-IDF + logistic regression
vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)
Xtr = vec.fit_transform(tr.text); lr = LogisticRegression(max_iter=2000, C=4).fit(Xtr, tr.label)
for name, df in (('safeguard_test', te), ('deepset_external', ds)):
    s = lr.predict_proba(vec.transform(df.text))[:, 1]
    res[f'tfidf_lr/{name}'] = metrics(df.label.values, (s > .5).astype(int), s)
print(json.dumps(res, indent=1), flush=True)

# --- transformer
name = 'microsoft/deberta-v3-small'
try:
    tok = AutoTokenizer.from_pretrained(name)
except Exception as e:
    print('deberta tokenizer failed, falling back:', e); name = 'distilroberta-base'; tok = AutoTokenizer.from_pretrained(name)
model = AutoModelForSequenceClassification.from_pretrained(name, num_labels=2, dtype=torch.float32).cuda()
opt = torch.optim.AdamW(model.parameters(), lr=3e-5, weight_decay=0.01)
EPOCHS, BS, ML = 2, 32, 128
texts, labels = tr.text.tolist(), tr.label.values
steps = EPOCHS * ((len(texts) + BS - 1) // BS)
sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=3e-5, total_steps=steps, pct_start=0.1)
scaler = torch.amp.GradScaler()
t0 = time.time()
for ep in range(EPOCHS):
    model.train(); perm = np.random.RandomState(ep).permutation(len(texts))
    for i in range(0, len(perm), BS):
        idx = perm[i:i + BS]
        enc = tok([texts[j] for j in idx], truncation=True, max_length=ML, padding=True, return_tensors='pt').to('cuda')
        y = torch.tensor(labels[idx]).cuda()
        with torch.autocast('cuda', dtype=torch.float16):
            loss = model(**enc, labels=y).loss
        opt.zero_grad(); scaler.scale(loss).backward(); scaler.unscale_(opt)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); scaler.step(opt); scaler.update(); sched.step()
        if (i // BS) % 50 == 0: print(f'ep{ep} step{i // BS} loss {loss.item():.4f}', flush=True)
train_time = time.time() - t0

@torch.no_grad()
def score(tx):
    model.eval(); out = []
    for i in range(0, len(tx), 64):
        enc = tok(tx[i:i + 64], truncation=True, max_length=ML, padding=True, return_tensors='pt').to('cuda')
        with torch.autocast('cuda', dtype=torch.float16):
            out.append(torch.softmax(model(**enc).logits.float(), -1)[:, 1].cpu().numpy())
    return np.concatenate(out)

for nm, df in (('safeguard_test', te), ('deepset_external', ds)):
    s = score(df.text.tolist())
    res[f'{name}/{nm}'] = metrics(df.label.values, (s > .5).astype(int), s)
res['meta'] = dict(model=name, train_seconds=train_time, epochs=EPOCHS, train_n=len(tr))
os.makedirs(os.path.join(ROOT, 'models'), exist_ok=True)
model.save_pretrained(os.path.join(ROOT, 'models', 'detector')); tok.save_pretrained(os.path.join(ROOT, 'models', 'detector'))
json.dump(res, open(os.path.join(ROOT, 'results', 'detector_metrics.json'), 'w'), indent=1)
print(json.dumps(res, indent=1))
