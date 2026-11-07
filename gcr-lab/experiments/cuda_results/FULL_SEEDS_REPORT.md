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
