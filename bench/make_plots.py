"""Turn results/eval_main.json into figures and a markdown table."""
import os, json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
R = json.load(open(os.path.join(ROOT, 'results', 'eval_main.json')))['results']
LABEL = {'no_defense': 'No defense', 'retrieval_filter': 'Retrieval-time\nfilter', 'write_filter': 'Write-time\nfilter',
         'mg_provenance_risk': 'Provenance\n+ risk only', 'mg_no_rollback': 'MemGuard\nno rollback',
         'mg_no_risk': 'MemGuard\nno risk engine', 'mg_no_detector': 'MemGuard\nno detector',
         'mg_full': 'MemGuard\nfull', 'mg_full_rules_only': 'MemGuard full\n(rules detector)'}
names = [n for n in LABEL if n in R]
x = np.arange(len(names))

fig, ax = plt.subplots(1, 2, figsize=(13, 5.4))
w = 0.38
for i, (key, lab, col) in enumerate([('asr', 'Session 2', '#d9534f'), ('asr_session3', 'Session 3 (repeat)', '#f0ad4e')]):
    v = [R[n][key][0] for n in names]; e = [R[n][key][1] for n in names]
    ax[0].bar(x + (i - .5) * w, v, w, yerr=e, label=lab, color=col, capsize=2)
ax[0].set_xticks(x); ax[0].set_xticklabels([LABEL[n] for n in names], fontsize=7, rotation=35, ha='right')
ax[0].set_ylabel('Attack success rate'); ax[0].set_title('Attack success (lower is better)'); ax[0].legend()
u = [R[n]['utility_clean'][0] for n in names]; h = [R[n]['holds_per_clean_episode'][0] for n in names]
ax[1].bar(x - .5 * w, u, w, label='Benign task completion', color='#5cb85c')
ax[1].bar(x + .5 * w, h, w, label='Human approvals per clean episode', color='#5bc0de')
ax[1].set_xticks(x); ax[1].set_xticklabels([LABEL[n] for n in names], fontsize=7, rotation=35, ha='right')
ax[1].set_title('Cost of the defense (clean episodes)'); ax[1].legend()
plt.tight_layout(); plt.savefig(os.path.join(ROOT, 'results', 'fig_main.png'), dpi=160)

kinds = ['explicit', 'jailbreak', 'declarative', 'payee', 'share']
sel = [n for n in ('no_defense', 'retrieval_filter', 'write_filter', 'mg_full') if n in R]
fig, ax = plt.subplots(figsize=(8, 4))
for i, n in enumerate(sel):
    ax.bar(np.arange(len(kinds)) + (i - len(sel) / 2 + .5) * .2, [R[n]['asr_by_kind'].get(k, 0) for k in kinds], .2, label=LABEL[n].replace('\n', ' '))
ax.set_xticks(range(len(kinds))); ax.set_xticklabels(kinds); ax.set_ylabel('Attack success rate')
ax.set_title('Attack success by poison class'); ax.legend(fontsize=8)
plt.tight_layout(); plt.savefig(os.path.join(ROOT, 'results', 'fig_by_kind.png'), dpi=160)

f = lambda p: f'{100 * p[0]:.1f} ± {100 * p[1]:.1f}'
rows = ['| Defense | ASR % (s2) | ASR % (s3) | Benign completion % | Approvals / clean ep | Write FPR % | Write TPR % |', '|---|---|---|---|---|---|---|']
for n in names:
    r = R[n]
    rows.append(f"| {LABEL[n].replace(chr(10), ' ')} | {f(r['asr'])} | {f(r['asr_session3'])} | {f(r['utility_clean'])} | "
                f"{r['holds_per_clean_episode'][0]:.2f} | {f(r['write_fpr'])} | {f(r['write_tpr'])} |")
open(os.path.join(ROOT, 'results', 'table_main.md'), 'w').write('\n'.join(rows) + '\n')
print('\n'.join(rows))
