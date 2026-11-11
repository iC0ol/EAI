# B0 status

Status: **COMPLETED** (2026-11-11, Asia/Shanghai).

The 2026-11-10 block was the NVIDIA kernel/userspace mismatch. After the
authorized reboot, the kernel module and userspace are both 580.178.04, CUDA
initializes, and the formal baseline was run on the RTX 3090.

## Formal B0 result

| Item | Value |
|---|---|
| Run directory | `runs/b0_gpu3090_20261111T1230/` |
| Episodes | 100 (seeds 100000–100099, complete and unique) |
| Horizon / max steps | 8 / 500 |
| Device | `cuda:0`, RTX 3090 |
| Successes / failures | **84 / 16** |
| Success rate | **0.84 (84 %)** |
| Wilson 95 % CI | 0.7558–0.8990 |
| Clopper–Pearson 95 % CI | 0.7532–0.9057 |
| Mean wall time | 112.71 s per episode; 3.13 h total |
| Failed seeds | 100000, 100004, 100018, 100026, 100033, 100035, 100038, 100040, 100048, 100059, 100067, 100070, 100077, 100080, 100091, 100094 |

All 100 records have 500 steps, 63 policy calls, unique initial states, no
`success_error`, and no NaN/Inf/CUDA error. Full report:
`reports/B0_REPORT.md`; machine-readable evidence:
`reports/b0_baseline_episodes.jsonl`, `reports/b0_analysis.json`,
`reports/b0_episodes.csv`.

## Interpretation limits

- The checkpoint is the **10-D absolute-action** variant; this is a
  checkpoint-native-action B0, not the 7-D delta-action experiment described
  in the written protocol.
- The checkpoint's own `test_mean_score=1.000` was measured with
  `test_start_seed=4,500,000`, not the Gate B seeds 100000–100099. The 0.84 is
  a new measurement on the protocol seeds.
- `success_threshold=0.99` is an internal per-episode field, not the B0 GO
  threshold. The written protocol's continuation threshold is ≥0.70; 0.84
  exceeds it. No Gate C decision is made here.

## B1 and B2

- **B1: not started.** B0 now passes, but H=16 with To=2 leaves only 15 future
  actions, so `h=16` remains invalid. A researcher-approved horizon amendment
  is still required.
- **B2: not started.** The insertion-stage window is not frozen and no
  snapshot/restore replay was run. No B2 state was collected.

## Historical record

The 2026-11-10 CPU-only checks remain in `reports/B0_SMOKE_GPU.md` (GPU smoke,
2026-11-11) and in the earlier execution-log rows. The first GPU-smoke attempt
failed on missing unversioned `libcuda.so`; a workspace-local compatibility
symlink fixed it without modifying the system driver. The failed directory was
preserved and not reused.
