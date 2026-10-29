| Defense | ASR % (s2) | ASR % (s3) | Benign completion % | Approvals / clean ep | Write FPR % | Write TPR % |
|---|---|---|---|---|---|---|
| No defense | 83.1 ± 1.6 | 83.1 ± 1.6 | 100.0 ± 0.0 | 0.00 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| Retrieval-time filter | 46.0 ± 2.5 | 46.0 ± 2.5 | 61.4 ± 3.7 | 0.00 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| Write-time filter | 45.8 ± 2.4 | 45.8 ± 2.4 | 61.4 ± 3.7 | 0.00 | 17.2 ± 0.8 | 49.4 ± 2.0 |
| Provenance + risk only | 3.3 ± 0.2 | 0.3 ± 0.3 | 99.9 ± 0.2 | 0.46 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| MemGuard no rollback | 1.3 ± 0.4 | 0.0 ± 0.0 | 89.0 ± 0.4 | 0.35 | 10.3 ± 0.7 | 49.4 ± 2.0 |
| MemGuard no risk engine | 44.9 ± 2.8 | 44.9 ± 2.8 | 89.3 ± 0.4 | 0.00 | 10.3 ± 0.7 | 49.4 ± 2.0 |
| MemGuard no detector | 2.1 ± 0.9 | 0.1 ± 0.2 | 98.4 ± 0.4 | 0.45 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| MemGuard full | 1.0 ± 0.5 | 0.0 ± 0.0 | 88.3 ± 0.2 | 0.35 | 10.3 ± 0.7 | 49.4 ± 2.0 |
| MemGuard full (rules detector) | 1.9 ± 0.2 | 0.1 ± 0.2 | 98.7 ± 0.3 | 0.46 | 0.0 ± 0.0 | 22.7 ± 0.5 |
