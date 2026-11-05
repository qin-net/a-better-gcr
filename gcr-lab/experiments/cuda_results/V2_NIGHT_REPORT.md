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
- [2026-11-06 01:07:34] Committed
- [2026-11-06 01:07:40] Pushed
- [2026-11-06 01:07:40] Stage 2: train ['C_wq', 'C_fwd'], eval ['C_wq', 'C_fwd'] on ['webqsp', 'cwq'], first 500

- [2026-11-06 01:07:40] Training C_wq (C_wq.jsonl.gz, seed 42)
- [2026-11-06 01:25:46] Trained C_wq in 18 min, 16103 sequences, validation loss 0.3153 -> 0.3286
- [2026-11-06 01:25:46] Training C_fwd (C_fwd.jsonl.gz, seed 42)
- [2026-11-06 01:43:58] Trained C_fwd in 18 min, 16103 sequences, validation loss 0.3153 -> 0.3167
- [2026-11-06 01:43:58] Starting webqsp/C_wq
- [2026-11-06 01:59:38] Completed webqsp/C_wq
- [2026-11-06 01:59:38] Starting webqsp/C_fwd
- [2026-11-06 02:15:29] Completed webqsp/C_fwd
```
run             n    hit     f1  f.hit unf.hit  faith
A_multi       500  0.724  0.454  0.626   0.098  0.588
C             500  0.690  0.424  0.588   0.102  0.556
D             500  0.694  0.425  0.598   0.096  0.566
C2            500  0.700  0.434  0.616   0.084  0.595
D2            500  0.686  0.426  0.606   0.080  0.591
C_wq          500  0.672  0.410  0.586   0.086  0.584
C_fwd         500  0.680  0.423  0.600   0.080  0.590
```

- [2026-11-06 02:15:31] Starting cwq/C_wq
- [2026-11-06 02:31:44] Completed cwq/C_wq
- [2026-11-06 02:31:44] Starting cwq/C_fwd
- [2026-11-06 02:48:17] Completed cwq/C_fwd
```
run             n    hit     f1  f.hit unf.hit  faith
A_multi       500  0.454  0.334  0.074   0.380  0.130
C             500  0.456  0.330  0.202   0.254  0.291
D             500  0.452  0.325  0.200   0.252  0.288
C2            500  0.462  0.327  0.160   0.302  0.248
D2            500  0.452  0.315  0.148   0.304  0.239
C_wq          500  0.466  0.336  0.224   0.242  0.310
C_fwd         500  0.458  0.321  0.148   0.310  0.242
```

```
webqsp_500
paired vs 11-04 A_multi (gained/lost, exact McNemar p)
C2            hit: +17/-29 p=0.1  faithful_hit: +21/-26 p=0.56
D2            hit: +17/-36 p=0.013  faithful_hit: +19/-29 p=0.19
C_wq          hit: +12/-38 p=0.00031  faithful_hit: +18/-38 p=0.01
C_fwd         hit: +10/-32 p=0.00094  faithful_hit: +14/-27 p=0.06
paired vs 11-04 C (gained/lost, exact McNemar p)
C2            hit: +26/-21 p=0.56  faithful_hit: +33/-19 p=0.07
D2            hit: +24/-26 p=0.89  faithful_hit: +30/-21 p=0.26
C_wq          hit: +11/-20 p=0.15  faithful_hit: +14/-15 p=1
C_fwd         hit: +19/-24 p=0.54  faithful_hit: +26/-20 p=0.46
```

```
cwq_500
paired vs 11-04 A_multi (gained/lost, exact McNemar p)
C2            hit: +35/-31 p=0.71  faithful_hit: +52/-9 p=1.8e-08
D2            hit: +34/-35 p=1  faithful_hit: +48/-11 p=1.2e-06
C_wq          hit: +40/-34 p=0.56  faithful_hit: +86/-11 p=1.4e-15
C_fwd         hit: +35/-33 p=0.9  faithful_hit: +47/-10 p=7.5e-07
paired vs 11-04 C (gained/lost, exact McNemar p)
C2            hit: +37/-34 p=0.81  faithful_hit: +30/-51 p=0.026
D2            hit: +33/-35 p=0.9  faithful_hit: +27/-54 p=0.0036
C_wq          hit: +13/-8 p=0.38  faithful_hit: +19/-8 p=0.052
C_fwd         hit: +38/-37 p=1  faithful_hit: +28/-55 p=0.004
```

- [2026-11-06 02:48:20] Stage 2 done in 101 min, 0 failed
- [2026-11-06 02:48:21] Committed
- [2026-11-06 02:48:27] Pushed
- [2026-11-06 02:48:27] Stage 3: train ['C2_s43', 'C2_s44', 'A_s43', 'A_s44'], eval ['C2_s43', 'C2_s44', 'A_multi_s43', 'A_multi_s44'] on ['webqsp', 'cwq'], first 500

- [2026-11-06 02:48:27] Training C2_s43 (C2.jsonl.gz, seed 43)
- [2026-11-06 03:06:21] Trained C2_s43 in 18 min, 16103 sequences, validation loss 0.3153 -> 0.3213
- [2026-11-06 03:06:21] Training C2_s44 (C2.jsonl.gz, seed 44)
- [2026-11-06 03:24:18] Trained C2_s44 in 18 min, 16103 sequences, validation loss 0.3153 -> 0.3179
- [2026-11-06 03:24:18] Training A_s43 (A.jsonl.gz, seed 43)
- [2026-11-06 03:42:08] Trained A_s43 in 18 min, 16102 sequences, validation loss 0.3153 -> 0.3081
- [2026-11-06 03:42:08] Training A_s44 (A.jsonl.gz, seed 44)
- [2026-11-06 03:59:58] Trained A_s44 in 18 min, 16102 sequences, validation loss 0.3153 -> 0.3086
- [2026-11-06 03:59:58] Starting webqsp/C2_s43
- [2026-11-06 04:15:49] Completed webqsp/C2_s43
- [2026-11-06 04:15:49] Starting webqsp/C2_s44
- [2026-11-06 04:31:31] Completed webqsp/C2_s44
- [2026-11-06 04:31:31] Starting webqsp/A_multi_s43
- [2026-11-06 04:47:18] Completed webqsp/A_multi_s43
- [2026-11-06 04:47:18] Starting webqsp/A_multi_s44
- [2026-11-06 05:03:06] Completed webqsp/A_multi_s44
```
run             n    hit     f1  f.hit unf.hit  faith
A_multi       500  0.724  0.454  0.626   0.098  0.588
C             500  0.690  0.424  0.588   0.102  0.556
D             500  0.694  0.425  0.598   0.096  0.566
C2            500  0.700  0.434  0.616   0.084  0.595
D2            500  0.686  0.426  0.606   0.080  0.591
C_wq          500  0.672  0.410  0.586   0.086  0.584
C_fwd         500  0.680  0.423  0.600   0.080  0.590
C2_s43        500  0.688  0.426  0.612   0.076  0.589
C2_s44        500  0.694  0.432  0.616   0.078  0.602
A_multi_s43   500  0.722  0.455  0.622   0.100  0.579
A_multi_s44   500  0.720  0.451  0.624   0.096  0.590
```

- [2026-11-06 05:03:08] Starting cwq/C2_s43
- [2026-11-06 05:19:51] Completed cwq/C2_s43
- [2026-11-06 05:19:51] Starting cwq/C2_s44
- [2026-11-06 05:36:36] Completed cwq/C2_s44
- [2026-11-06 05:36:36] Starting cwq/A_multi_s43
- [2026-11-06 05:52:52] Completed cwq/A_multi_s43
- [2026-11-06 05:52:52] Starting cwq/A_multi_s44
- [2026-11-06 06:09:26] Completed cwq/A_multi_s44
```
run             n    hit     f1  f.hit unf.hit  faith
A_multi       500  0.454  0.334  0.074   0.380  0.130
C             500  0.456  0.330  0.202   0.254  0.291
D             500  0.452  0.325  0.200   0.252  0.288
C2            500  0.462  0.327  0.160   0.302  0.248
D2            500  0.452  0.315  0.148   0.304  0.239
C_wq          500  0.466  0.336  0.224   0.242  0.310
C_fwd         500  0.458  0.321  0.148   0.310  0.242
C2_s43        500  0.460  0.328  0.162   0.298  0.245
C2_s44        500  0.458  0.320  0.170   0.288  0.248
A_multi_s43   500  0.464  0.342  0.082   0.382  0.141
A_multi_s44   500  0.460  0.336  0.080   0.380  0.131
```

```
webqsp_500
paired vs 11-04 A_multi (gained/lost, exact McNemar p)
C2            hit: +17/-29 p=0.1  faithful_hit: +21/-26 p=0.56
D2            hit: +17/-36 p=0.013  faithful_hit: +19/-29 p=0.19
C_wq          hit: +12/-38 p=0.00031  faithful_hit: +18/-38 p=0.01
C_fwd         hit: +10/-32 p=0.00094  faithful_hit: +14/-27 p=0.06
C2_s43        hit: +15/-33 p=0.013  faithful_hit: +21/-28 p=0.39
C2_s44        hit: +17/-32 p=0.044  faithful_hit: +20/-25 p=0.55
A_multi_s43   hit: +4/-5 p=1  faithful_hit: +2/-4 p=0.69
A_multi_s44   hit: +3/-5 p=0.73  faithful_hit: +2/-3 p=1
paired vs 11-04 C (gained/lost, exact McNemar p)
C2            hit: +26/-21 p=0.56  faithful_hit: +33/-19 p=0.07
D2            hit: +24/-26 p=0.89  faithful_hit: +30/-21 p=0.26
C_wq          hit: +11/-20 p=0.15  faithful_hit: +14/-15 p=1
C_fwd         hit: +19/-24 p=0.54  faithful_hit: +26/-20 p=0.46
C2_s43        hit: +25/-26 p=1  faithful_hit: +33/-21 p=0.13
C2_s44        hit: +25/-23 p=0.89  faithful_hit: +32/-18 p=0.065
A_multi_s43   hit: +38/-22 p=0.052  faithful_hit: +40/-23 p=0.043
A_multi_s44   hit: +38/-23 p=0.072  faithful_hit: +40/-22 p=0.03
```

```
cwq_500
paired vs 11-04 A_multi (gained/lost, exact McNemar p)
C2            hit: +35/-31 p=0.71  faithful_hit: +52/-9 p=1.8e-08
D2            hit: +34/-35 p=1  faithful_hit: +48/-11 p=1.2e-06
C_wq          hit: +40/-34 p=0.56  faithful_hit: +86/-11 p=1.4e-15
C_fwd         hit: +35/-33 p=0.9  faithful_hit: +47/-10 p=7.5e-07
C2_s43        hit: +34/-31 p=0.8  faithful_hit: +53/-9 p=1.1e-08
C2_s44        hit: +35/-33 p=0.9  faithful_hit: +57/-9 p=1.2e-09
A_multi_s43   hit: +7/-2 p=0.18  faithful_hit: +4/-0 p=0.12
A_multi_s44   hit: +8/-5 p=0.58  faithful_hit: +4/-1 p=0.38
paired vs 11-04 C (gained/lost, exact McNemar p)
C2            hit: +37/-34 p=0.81  faithful_hit: +30/-51 p=0.026
D2            hit: +33/-35 p=0.9  faithful_hit: +27/-54 p=0.0036
C_wq          hit: +13/-8 p=0.38  faithful_hit: +19/-8 p=0.052
C_fwd         hit: +38/-37 p=1  faithful_hit: +28/-55 p=0.004
C2_s43        hit: +36/-34 p=0.9  faithful_hit: +32/-52 p=0.038
C2_s44        hit: +38/-37 p=1  faithful_hit: +36/-52 p=0.11
A_multi_s43   hit: +41/-37 p=0.73  faithful_hit: +13/-73 p=2.7e-11
A_multi_s44   hit: +38/-36 p=0.91  faithful_hit: +11/-72 p=3.9e-12
```

- [2026-11-06 06:09:31] Stage 3 done in 201 min, 0 failed
- [2026-11-06 06:09:33] Committed
- [2026-11-06 06:09:40] Pushed
- [2026-11-06 06:09:40] Stage 4: train nothing, eval ['A_multi', 'C2'] on ['webqsp'], first 1628

- [2026-11-06 06:09:40] Starting webqsp/A_multi
- [2026-11-06 07:00:38] Completed webqsp/A_multi
- [2026-11-06 07:00:38] Starting webqsp/C2
- [2026-11-06 07:52:23] Completed webqsp/C2
```
run             n    hit     f1  f.hit unf.hit  faith
A_multi      1628  0.695  0.427  0.592   0.103  0.569
C2           1628  0.693  0.420  0.611   0.082  0.602
```

```
webqsp_1628
paired vs A_multi (gained/lost, exact McNemar p)
C2            hit: +78/-81 p=0.87  faithful_hit: +107/-76 p=0.026
```

- [2026-11-06 07:52:25] Stage 4 done in 103 min, 0 failed
- [2026-11-06 07:52:26] Committed
- [2026-11-06 07:52:31] Pushed
- [2026-11-06 07:52:31] All done, 0 failures
