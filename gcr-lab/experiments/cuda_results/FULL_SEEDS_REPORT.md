# 全量多 seed：C2 对 A_multi

## 2026-11-07 13:02:10 开始，GPU：NVIDIA GeForce RTX 4060 Laptop GPU，commit：9967736
- 命令：`graph-constrained-reasoning/workflow/run_full_seeds.py --push --hours 10`

- [2026-11-07 13:02:10] Starting webqsp/C2_s43
- [2026-11-07 13:39:08] Completed webqsp/C2_s43
```
run             n    hit     f1  f.hit f.strict unf.hit  faith
C2           1628  0.693  0.420  0.611    0.619   0.082  0.602
A_multi      1628  0.695  0.427  0.592    0.595   0.103  0.569
C2_s43       1628  0.691  0.420  0.612    0.620   0.079  0.604
```

```
C2 - A_multi, webqsp_1628, 1628 questions; points, 95% CI and sign-flip p over seed questions
seed 42      hit                   -0.2 [ -1.7,  +1.3]  p=0.88
seed 42      faithful_strict_hit   +2.3 [ +0.7,  +4.0]  p=0.0072
```

- [2026-11-07 13:39:21] Starting webqsp/A_multi_s43
- [2026-11-07 14:16:57] Completed webqsp/A_multi_s43
```
run             n    hit     f1  f.hit f.strict unf.hit  faith
C2           1628  0.693  0.420  0.611    0.619   0.082  0.602
A_multi      1628  0.695  0.427  0.592    0.595   0.103  0.569
C2_s43       1628  0.691  0.420  0.612    0.620   0.079  0.604
A_multi_s43  1628  0.694  0.426  0.593    0.596   0.101  0.566
```

```
C2 - A_multi, webqsp_1628, 1628 questions; points, 95% CI and sign-flip p over seed questions
seed 42      hit                   -0.2 [ -1.7,  +1.3]  p=0.88
seed 42      faithful_strict_hit   +2.3 [ +0.7,  +4.0]  p=0.0072
seed 43      hit                   -0.3 [ -1.9,  +1.2]  p=0.75
seed 43      faithful_strict_hit   +2.4 [ +0.6,  +4.1]  p=0.0081
2v2 pooled   hit                   -0.2 [ -1.8,  +1.2]  p=0.78
2v2 pooled   faithful_strict_hit   +2.4 [ +0.7,  +4.0]  p=0.0042
```

- [2026-11-07 14:17:12] Push failed: fatal: unable to access 'https://github.com/qin-net/a-better-gcr.git/': Recv failure: Connection was aborted
- [2026-11-07 14:17:12] Starting webqsp/C2_s44
- [2026-11-07 14:17:20] FAILED webqsp/C2_s44: exit code 1; kept as C2_s44_failed
```
run             n    hit     f1  f.hit f.strict unf.hit  faith
C2           1628  0.693  0.420  0.611    0.619   0.082  0.602
A_multi      1628  0.695  0.427  0.592    0.595   0.103  0.569
C2_s43       1628  0.691  0.420  0.612    0.620   0.079  0.604
A_multi_s43  1628  0.694  0.426  0.593    0.596   0.101  0.566
```

```
C2 - A_multi, webqsp_1628, 1628 questions; points, 95% CI and sign-flip p over seed questions
seed 42      hit                   -0.2 [ -1.7,  +1.3]  p=0.88
seed 42      faithful_strict_hit   +2.3 [ +0.7,  +4.0]  p=0.0072
seed 43      hit                   -0.3 [ -1.9,  +1.2]  p=0.75
seed 43      faithful_strict_hit   +2.4 [ +0.6,  +4.1]  p=0.0081
2v2 pooled   hit                   -0.2 [ -1.8,  +1.2]  p=0.78
2v2 pooled   faithful_strict_hit   +2.4 [ +0.7,  +4.0]  p=0.0042
```

- [2026-11-07 14:17:36] Push failed: fatal: unable to access 'https://github.com/qin-net/a-better-gcr.git/': Recv failure: Connection was aborted
- [2026-11-07 14:17:36] Starting webqsp/A_multi_s44
- [2026-11-07 14:17:42] FAILED webqsp/A_multi_s44: exit code 1; kept as A_multi_s44_failed
```
run             n    hit     f1  f.hit f.strict unf.hit  faith
C2           1628  0.693  0.420  0.611    0.619   0.082  0.602
A_multi      1628  0.695  0.427  0.592    0.595   0.103  0.569
C2_s43       1628  0.691  0.420  0.612    0.620   0.079  0.604
A_multi_s43  1628  0.694  0.426  0.593    0.596   0.101  0.566
```

```
C2 - A_multi, webqsp_1628, 1628 questions; points, 95% CI and sign-flip p over seed questions
seed 42      hit                   -0.2 [ -1.7,  +1.3]  p=0.88
seed 42      faithful_strict_hit   +2.3 [ +0.7,  +4.0]  p=0.0072
seed 43      hit                   -0.3 [ -1.9,  +1.2]  p=0.75
seed 43      faithful_strict_hit   +2.4 [ +0.6,  +4.1]  p=0.0081
2v2 pooled   hit                   -0.2 [ -1.8,  +1.2]  p=0.78
2v2 pooled   faithful_strict_hit   +2.4 [ +0.7,  +4.0]  p=0.0042
```

- [2026-11-07 14:17:57] Push failed: fatal: unable to access 'https://github.com/qin-net/a-better-gcr.git/': Recv failure: Connection was aborted
- [2026-11-07 14:17:57] Starting cwq/C2
- [2026-11-07 14:18:03] FAILED cwq/C2: exit code 1; kept as C2_failed
- [2026-11-07 14:18:03] Push failed: fatal: unable to access 'https://github.com/qin-net/a-better-gcr.git/': Recv failure: Connection was aborted
- [2026-11-07 14:18:03] Starting cwq/A_multi
- [2026-11-07 14:18:09] FAILED cwq/A_multi: exit code 1; kept as A_multi_failed
- [2026-11-07 14:18:09] Push failed: fatal: unable to access 'https://github.com/qin-net/a-better-gcr.git/': Recv failure: Connection was aborted
- [2026-11-07 14:18:09] Starting cwq/C2_s43
- [2026-11-07 14:18:15] FAILED cwq/C2_s43: exit code 1; kept as C2_s43_failed
- [2026-11-07 14:18:16] Push failed: fatal: unable to access 'https://github.com/qin-net/a-better-gcr.git/': Recv failure: Connection was aborted
- [2026-11-07 14:18:16] Starting cwq/A_multi_s43
- [2026-11-07 14:18:22] FAILED cwq/A_multi_s43: exit code 1; kept as A_multi_s43_failed
- [2026-11-07 14:18:22] Push failed: fatal: unable to access 'https://github.com/qin-net/a-better-gcr.git/': Recv failure: Connection was aborted
- [2026-11-07 14:18:22] Starting cwq/C2_s44
- [2026-11-07 14:18:28] FAILED cwq/C2_s44: exit code 1; kept as C2_s44_failed
- [2026-11-07 14:18:28] Push failed: fatal: unable to access 'https://github.com/qin-net/a-better-gcr.git/': Recv failure: Connection was aborted
- [2026-11-07 14:18:28] Starting cwq/A_multi_s44
- [2026-11-07 14:18:34] FAILED cwq/A_multi_s44: exit code 1; kept as A_multi_s44_failed
- [2026-11-07 14:18:34] Push failed: fatal: unable to access 'https://github.com/qin-net/a-better-gcr.git/': Recv failure: Connection was aborted
- [2026-11-07 14:18:34] All done, 8 failures: [{"dataset": "webqsp", "limit": 1628, "run": "C2_s44", "reason": "exit code 1", "log": "D:\\desktop\\vs\\a-better-gcr\\gcr-lab\\experiments\\cuda_results\\v2\\webqsp_1628\\C2_s44_failed.log"}, {"dataset": "webqsp", "limit": 1628, "run": "A_multi_s44", "reason": "exit code 1", "log": "D:\\desktop\\vs\\a-better-gcr\\gcr-lab\\experiments\\cuda_results\\v2\\webqsp_1628\\A_multi_s44_failed.log"}, {"dataset": "cwq", "limit": 3531, "run": "C2", "reason": "exit code 1", "log": "D:\\desktop\\vs\\a-better-gcr\\gcr-lab\\experiments\\cuda_results\\v2\\cwq_3531\\C2_failed.log"}, {"dataset": "cwq", "limit": 3531, "run": "A_multi", "reason": "exit code 1", "log": "D:\\desktop\\vs\\a-better-gcr\\gcr-lab\\experiments\\cuda_results\\v2\\cwq_3531\\A_multi_failed.log"}, {"dataset": "cwq", "limit": 3531, "run": "C2_s43", "reason": "exit code 1", "log": "D:\\desktop\\vs\\a-better-gcr\\gcr-lab\\experiments\\cuda_results\\v2\\cwq_3531\\C2_s43_failed.log"}, {"dataset": "cwq", "limit": 3531, "run": "A_multi_s43", "reason": "exit code 1", "log": "D:\\desktop\\vs\\a-better-gcr\\gcr-lab\\experiments\\cuda_results\\v2\\cwq_3531\\A_multi_s43_failed.log"}, {"dataset": "cwq", "limit": 3531, "run": "C2_s44", "reason": "exit code 1", "log": "D:\\desktop\\vs\\a-better-gcr\\gcr-lab\\experiments\\cuda_results\\v2\\cwq_3531\\C2_s44_failed.log"}, {"dataset": "cwq", "limit": 3531, "run": "A_multi_s44", "reason": "exit code 1", "log": "D:\\desktop\\vs\\a-better-gcr\\gcr-lab\\experiments\\cuda_results\\v2\\cwq_3531\\A_multi_s44_failed.log"}]
- [2026-11-07 14:18:35] Push failed: fatal: unable to access 'https://github.com/qin-net/a-better-gcr.git/': Recv failure: Connection was aborted

## 2026-11-07 16:13:06 开始，GPU：NVIDIA GeForce RTX 4060 Laptop GPU，commit：89759e2
- 命令：`graph-constrained-reasoning/workflow/run_full_seeds.py --push --hours 10`

- [2026-11-07 16:13:06] Skipping completed webqsp_1628/C2_s43
- [2026-11-07 16:13:06] Skipping completed webqsp_1628/A_multi_s43
- [2026-11-07 16:13:06] Starting webqsp/C2_s44
- [2026-11-07 16:50:31] Completed webqsp/C2_s44
```
run             n    hit     f1  f.hit f.strict unf.hit  faith
C2           1628  0.693  0.420  0.611    0.619   0.082  0.602
A_multi      1628  0.695  0.427  0.592    0.595   0.103  0.569
C2_s43       1628  0.691  0.420  0.612    0.620   0.079  0.604
A_multi_s43  1628  0.694  0.426  0.593    0.596   0.101  0.566
C2_s44       1628  0.696  0.426  0.614    0.620   0.082  0.608
```

```
C2 - A_multi, webqsp_1628, 1628 questions; points, 95% CI and sign-flip p over seed questions
seed 42      hit                   -0.2 [ -1.7,  +1.3]  p=0.88
seed 42      faithful_strict_hit   +2.3 [ +0.7,  +4.0]  p=0.0072
seed 43      hit                   -0.3 [ -1.9,  +1.2]  p=0.75
seed 43      faithful_strict_hit   +2.4 [ +0.6,  +4.1]  p=0.0081
2v2 pooled   hit                   -0.2 [ -1.8,  +1.2]  p=0.78
2v2 pooled   faithful_strict_hit   +2.4 [ +0.7,  +4.0]  p=0.0042
```

- [2026-11-07 16:50:51] Starting webqsp/A_multi_s44
- [2026-11-07 17:27:37] Completed webqsp/A_multi_s44
```
run             n    hit     f1  f.hit f.strict unf.hit  faith
C2           1628  0.693  0.420  0.611    0.619   0.082  0.602
A_multi      1628  0.695  0.427  0.592    0.595   0.103  0.569
C2_s43       1628  0.691  0.420  0.612    0.620   0.079  0.604
A_multi_s43  1628  0.694  0.426  0.593    0.596   0.101  0.566
C2_s44       1628  0.696  0.426  0.614    0.620   0.082  0.608
A_multi_s44  1628  0.695  0.426  0.592    0.595   0.103  0.571
```

```
C2 - A_multi, webqsp_1628, 1628 questions; points, 95% CI and sign-flip p over seed questions
seed 42      hit                   -0.2 [ -1.7,  +1.3]  p=0.88
seed 42      faithful_strict_hit   +2.3 [ +0.7,  +4.0]  p=0.0072
seed 43      hit                   -0.3 [ -1.9,  +1.2]  p=0.75
seed 43      faithful_strict_hit   +2.4 [ +0.6,  +4.1]  p=0.0081
seed 44      hit                   +0.1 [ -1.4,  +1.6]  p=0.94
seed 44      faithful_strict_hit   +2.6 [ +0.9,  +4.3]  p=0.0021
3v3 pooled   hit                   -0.1 [ -1.6,  +1.3]  p=0.89
3v3 pooled   faithful_strict_hit   +2.4 [ +0.8,  +4.1]  p=0.0024
```

## 2026-11-07 20:15:58 开始，GPU：NVIDIA GeForce RTX 4060 Laptop GPU，commit：156612d
- 命令：`graph-constrained-reasoning/workflow/run_full_seeds.py --push`

- [2026-11-07 20:15:59] Skipping completed webqsp_1628/C2_s43
- [2026-11-07 20:15:59] Skipping completed webqsp_1628/A_multi_s43
- [2026-11-07 20:15:59] Skipping completed webqsp_1628/C2_s44
- [2026-11-07 20:15:59] Skipping completed webqsp_1628/A_multi_s44
- [2026-11-07 20:15:59] Starting cwq/C2
- [2026-11-07 20:41:10] Completed cwq/C2
```
run             n    hit     f1  f.hit f.strict unf.hit  faith
C2           3531  0.378  0.267  0.174    0.312   0.204  0.335
```

- [2026-11-07 20:41:19] Starting cwq/A_multi
- [2026-11-07 23:12:52] Completed cwq/A_multi
```
run             n    hit     f1  f.hit f.strict unf.hit  faith
C2           3531  0.378  0.267  0.174    0.312   0.204  0.335
A_multi      3531  0.387  0.276  0.116    0.292   0.272  0.239
```

```
C2 - A_multi, cwq_3531, 3531 questions; points, 95% CI and sign-flip p over seed questions
seed 42      hit                   -0.9 [ -2.5,  +0.7]  p=0.31
seed 42      faithful_strict_hit   +2.0 [ +0.4,  +3.7]  p=0.026
```

- [2026-11-07 23:13:00] Starting cwq/C2_s43
- [2026-11-08 00:31:09] Completed cwq/C2_s43
```
run             n    hit     f1  f.hit f.strict unf.hit  faith
C2           3531  0.378  0.267  0.174    0.312   0.204  0.335
A_multi      3531  0.387  0.276  0.116    0.292   0.272  0.239
C2_s43       3531  0.379  0.268  0.173    0.311   0.206  0.328
```

```
C2 - A_multi, cwq_3531, 3531 questions; points, 95% CI and sign-flip p over seed questions
seed 42      hit                   -0.9 [ -2.5,  +0.7]  p=0.31
seed 42      faithful_strict_hit   +2.0 [ +0.4,  +3.7]  p=0.026
```

- [2026-11-08 00:31:17] Starting cwq/A_multi_s43
- [2026-11-08 01:49:56] Completed cwq/A_multi_s43
```
run             n    hit     f1  f.hit f.strict unf.hit  faith
C2           3531  0.378  0.267  0.174    0.312   0.204  0.335
A_multi      3531  0.387  0.276  0.116    0.292   0.272  0.239
C2_s43       3531  0.379  0.268  0.173    0.311   0.206  0.328
A_multi_s43  3531  0.390  0.279  0.118    0.294   0.272  0.240
```

```
C2 - A_multi, cwq_3531, 3531 questions; points, 95% CI and sign-flip p over seed questions
seed 42      hit                   -0.9 [ -2.5,  +0.7]  p=0.31
seed 42      faithful_strict_hit   +2.0 [ +0.4,  +3.7]  p=0.026
seed 43      hit                   -1.1 [ -2.7,  +0.5]  p=0.22
seed 43      faithful_strict_hit   +1.6 [ +0.1,  +3.3]  p=0.056
2v2 pooled   hit                   -1.0 [ -2.6,  +0.6]  p=0.24
2v2 pooled   faithful_strict_hit   +1.8 [ +0.2,  +3.5]  p=0.034
```

