"""Download the public prompt-injection datasets used to train the detector.

deepset/prompt-injections        (Apache-2.0)  662 labelled prompts
xTRam1/safe-guard-prompt-injection            10,296 labelled prompts (synthetic)
"""
import os, urllib.request
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
os.makedirs(OUT, exist_ok=True)
for ds in ('deepset/prompt-injections', 'xTRam1/safe-guard-prompt-injection'):
    for split in ('train', 'test'):
        url = f'https://huggingface.co/api/datasets/{ds}/parquet/default/{split}/0.parquet'
        dst = os.path.join(OUT, f"{ds.replace('/', '_')}_{split}.parquet")
        if not os.path.exists(dst):
            print('downloading', url)
            urllib.request.urlretrieve(url, dst)
print('ok')
