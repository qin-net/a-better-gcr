# v2 训练与评测记录

- 开始：2026-11-05 23:23:25，GPU：NVIDIA GeForce RTX 4060 Laptop GPU，commit：6682324
- 命令：`graph-constrained-reasoning/workflow/run_v2_night.py --push --hours 10`

- [2026-11-05 23:23:25] Stage 1: train ['C2', 'D2'], eval ['C2', 'D2'] on ['webqsp', 'cwq'], first 500

- [2026-11-05 23:23:25] Archived incomplete training C2 -> C2_failed
- [2026-11-05 23:23:25] Training C2 (C2.jsonl.gz, seed 42)
- [2026-11-05 23:40:25] Trained C2 in 17 min, 16103 sequences, validation loss 0.3153 -> 0.3205
- [2026-11-05 23:40:25] Training D2 (D2.jsonl.gz, seed 42)
- [2026-11-05 23:59:42] Trained D2 in 19 min, 16656 sequences, validation loss 0.3153 -> 0.3202
- [2026-11-05 23:59:42] Starting webqsp/C2
- [2026-11-06 00:16:31] Completed webqsp/C2
- [2026-11-06 00:16:31] Starting webqsp/D2
- [2026-11-06 00:33:03] Completed webqsp/D2
```
run             n    hit     f1  f.hit unf.hit  faith
A_multi       500  0.724  0.454  0.626   0.098  0.588
C             500  0.690  0.424  0.588   0.102  0.556
D             500  0.694  0.425  0.598   0.096  0.566
C2            500  0.700  0.434  0.616   0.084  0.595
D2            500  0.686  0.426  0.606   0.080  0.591
```

- [2026-11-06 00:33:05] Starting cwq/C2
- [2026-11-06 00:50:11] Completed cwq/C2
- [2026-11-06 00:50:11] Starting cwq/D2
- [2026-11-06 01:07:30] Completed cwq/D2
```
run             n    hit     f1  f.hit unf.hit  faith
A_multi       500  0.454  0.334  0.074   0.380  0.130
C             500  0.456  0.330  0.202   0.254  0.291
D             500  0.452  0.325  0.200   0.252  0.288
C2            500  0.462  0.327  0.160   0.302  0.248
D2            500  0.452  0.315  0.148   0.304  0.239
```

```
webqsp_500
paired vs 11-04 A_multi (gained/lost, exact McNemar p)
C2            hit: +17/-29 p=0.1  faithful_hit: +21/-26 p=0.56
D2            hit: +17/-36 p=0.013  faithful_hit: +19/-29 p=0.19
paired vs 11-04 C (gained/lost, exact McNemar p)
C2            hit: +26/-21 p=0.56  faithful_hit: +33/-19 p=0.07
D2            hit: +24/-26 p=0.89  faithful_hit: +30/-21 p=0.26
```

```
cwq_500
paired vs 11-04 A_multi (gained/lost, exact McNemar p)
C2            hit: +35/-31 p=0.71  faithful_hit: +52/-9 p=1.8e-08
D2            hit: +34/-35 p=1  faithful_hit: +48/-11 p=1.2e-06
paired vs 11-04 C (gained/lost, exact McNemar p)
C2            hit: +37/-34 p=0.81  faithful_hit: +30/-51 p=0.026
D2            hit: +33/-35 p=0.9  faithful_hit: +27/-54 p=0.0036
```

- [2026-11-06 01:07:33] Stage 1 done in 104 min, 0 failed
