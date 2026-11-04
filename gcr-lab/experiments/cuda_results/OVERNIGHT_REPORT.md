# 过夜评测记录

- 开始：2026-11-04 22:49:26，GPU：NVIDIA GeForce RTX 4060 Laptop GPU，commit：12e7197
- 命令：`D:\desktop\vs\a-better-gcr\.venv\overnight-2026-11-04\launch.py --push --hours 8`

- [2026-11-04 22:49:26] Stage 1: ae_full, first 100, runs ['official', 'A', 'A_multi', 'B', 'C', 'D', 'E']

- [2026-11-04 22:49:26] Starting webqsp/official
- [2026-11-04 22:52:58] Completed webqsp/official
- [2026-11-04 22:52:58] Starting webqsp/A
- [2026-11-04 22:56:21] Completed webqsp/A
- [2026-11-04 22:56:21] Starting webqsp/A_multi
- [2026-11-04 22:59:52] Completed webqsp/A_multi
- [2026-11-04 22:59:52] Starting webqsp/B
- [2026-11-04 23:08:13] Completed webqsp/B
- [2026-11-04 23:08:13] Starting webqsp/C
- [2026-11-04 23:16:52] Completed webqsp/C
- [2026-11-04 23:16:52] Starting webqsp/D
- [2026-11-04 23:20:48] Completed webqsp/D
- [2026-11-04 23:20:48] Starting webqsp/E
- [2026-11-04 23:24:09] Completed webqsp/E
```
run           n    hit     f1  f.hit unf.hit  faith
official    100  0.630  0.380  0.530   0.100  0.520
A           100  0.670  0.423  0.580   0.090  0.555
A_multi     100  0.670  0.419  0.600   0.070  0.575
B           100  0.600  0.358  0.440   0.160  0.465
C           100  0.560  0.330  0.480   0.080  0.510
D           100  0.560  0.323  0.480   0.080  0.510
E           100  0.590  0.340  0.490   0.100  0.515
```

- [2026-11-04 23:24:09] Starting cwq/official
- [2026-11-04 23:28:42] Completed cwq/official
- [2026-11-04 23:28:42] Starting cwq/A
- [2026-11-04 23:37:23] Completed cwq/A
- [2026-11-04 23:37:23] Starting cwq/A_multi
- [2026-11-04 23:41:09] Completed cwq/A_multi
- [2026-11-04 23:41:09] Starting cwq/B
- [2026-11-04 23:45:14] Completed cwq/B
- [2026-11-04 23:45:14] Starting cwq/C
- [2026-11-04 23:48:39] Completed cwq/C
- [2026-11-04 23:48:39] Starting cwq/D
- [2026-11-05 00:13:38] Completed cwq/D
- [2026-11-05 00:13:38] Starting cwq/E
- [2026-11-05 00:17:22] Completed cwq/E
```
run           n    hit     f1  f.hit unf.hit  faith
official    100  0.390  0.284  0.050   0.340  0.105
A           100  0.450  0.327  0.040   0.410  0.090
A_multi     100  0.430  0.338  0.030   0.400  0.085
B           100  0.410  0.315  0.100   0.310  0.180
C           100  0.450  0.337  0.210   0.240  0.285
D           100  0.420  0.316  0.170   0.250  0.265
E           100  0.450  0.337  0.180   0.270  0.280
```

- [2026-11-05 00:17:23] Stage 1 done in 88 min, 0 failed
- [2026-11-05 00:17:24] Committed
- [2026-11-05 00:17:29] Pushed
- [2026-11-05 00:17:29] Stage 2: ae_full, first 500, runs ['official', 'A', 'A_multi', 'B', 'C', 'D']

- [2026-11-05 00:17:29] Starting webqsp/official
- [2026-11-05 00:33:20] FAILED webqsp/official: exit code 1; kept as official_failed
- [2026-11-05 00:33:20] Starting webqsp/A
- [2026-11-05 00:48:46] FAILED webqsp/A: exit code 1; kept as A_failed
- [2026-11-05 00:48:46] Starting webqsp/A_multi
- [2026-11-05 01:05:28] Completed webqsp/A_multi
- [2026-11-05 01:05:28] Starting webqsp/B
- [2026-11-05 01:22:39] Completed webqsp/B
- [2026-11-05 01:22:39] Starting webqsp/C
- [2026-11-05 01:39:10] Completed webqsp/C
- [2026-11-05 01:39:10] Starting webqsp/D
- [2026-11-05 01:56:04] Completed webqsp/D
```
run           n    hit     f1  f.hit unf.hit  faith
A_multi     500  0.724  0.454  0.626   0.098  0.588
B           500  0.664  0.399  0.452   0.212  0.422
C           500  0.690  0.424  0.588   0.102  0.556
D           500  0.694  0.425  0.598   0.096  0.566
```

- [2026-11-05 01:56:05] Starting cwq/official
- [2026-11-05 02:12:59] Completed cwq/official
- [2026-11-05 02:12:59] Starting cwq/A
- [2026-11-05 02:29:21] Completed cwq/A
- [2026-11-05 02:29:21] Starting cwq/A_multi
- [2026-11-05 02:46:46] Completed cwq/A_multi
- [2026-11-05 02:46:46] Starting cwq/B
- [2026-11-05 03:04:10] Completed cwq/B
- [2026-11-05 03:04:10] Starting cwq/C
- [2026-11-05 03:21:47] Completed cwq/C
- [2026-11-05 03:21:47] Starting cwq/D
- [2026-11-05 03:38:58] Completed cwq/D
```
run           n    hit     f1  f.hit unf.hit  faith
official    500  0.382  0.270  0.064   0.318  0.127
A           500  0.438  0.309  0.076   0.362  0.132
A_multi     500  0.454  0.334  0.074   0.380  0.130
B           500  0.440  0.315  0.124   0.316  0.185
C           500  0.456  0.330  0.202   0.254  0.291
D           500  0.452  0.325  0.200   0.252  0.288
```

- [2026-11-05 03:38:58] Stage 2 done in 201 min, 2 failed: [{"dataset": "webqsp", "limit": 500, "run": "official", "reason": "exit code 1", "log": "D:\\desktop\\vs\\a-better-gcr\\gcr-lab\\experiments\\cuda_results\\ae_full\\webqsp_500\\official_failed.log"}, {"dataset": "webqsp", "limit": 500, "run": "A", "reason": "exit code 1", "log": "D:\\desktop\\vs\\a-better-gcr\\gcr-lab\\experiments\\cuda_results\\ae_full\\webqsp_500\\A_failed.log"}]
