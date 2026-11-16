# Gate B v2 — Formal B0 baseline on RTX 3090

Status: **COMPLETED** (2026-11-11, Asia/Shanghai).

Branch `codex/gate-b-v2`, base commit `043d189b53f8ddd3bbfeb30f3d78e22f37f6a416`.
Run directory: `runs/b0_gpu3090_20261111T1230/`.

This is the formal 100-episode B0 baseline. It uses the original formal
`configs/gate_b.yaml`, the protocol seeds 100000–100099 and the official
Square-MH checkpoint. No seed, horizon, step limit or success predicate was
changed. No episode was skipped or replaced.

## Environment

| Item | Value |
|---|---|
| GPU | NVIDIA GeForce RTX 3090, 24,576 MiB, capability (8, 6) |
| Driver | 580.178.04 (kernel module and userspace) |
| PyTorch / CUDA runtime | 1.12.1+cu116 / 11.6 |
| cuDNN | 8302 |
| Python | 3.9.13 (isolated venv) |
| robomimic / robosuite | 0.2.0 / 1.2.0 (cheng-chi `277ab958…`) |
| MuJoCo | 2.1.0 (mujoco_py 2.0.2.13) |
| Renderer | OSMesa 23.2.1 (validated against official frames) |
| Checkpoint | `epoch=1950-test_mean_score=1.000.ckpt`, SHA256 `adaf1785…27c6d`, 4,627,773,609 B |
| Dataset metadata | `square/mh/low_dim.hdf5`, SHA256 `7e589063…42887` |
| Environment | `NutAssemblySquare` |

CUDA was verified with a real 1024×1024 matrix product and
`torch.cuda.synchronize()` before any formal episode.

## Formal parameters

| Parameter | Value |
|---|---|
| Episodes | 100 |
| Seeds | 100000–100099 (complete, unique) |
| Horizon h | 8 |
| Max steps | 500 |
| Policy seed | 700000 + evaluation seed |
| Device | `cuda:0` |
| Action semantics | checkpoint-native 10-D absolute (3 pos + 6-D rot + 1 gripper) → 7-D OSC_POSE, `control_delta=false` |
| Observations | 2×84×84 RGB + eef_pos[3] + eef_quat[4] + gripper_qpos[2] |
| Checkpoint horizon / To | H=16, To=2 (15 future actions; h=8 used) |
| Success | final-state robomimic `is_success()["task"]` |

## Integrity checks

| Check | Result |
|---|---|
| Episode count | 100 |
| Seed coverage | exactly 100000–100099, no duplicates, no gaps |
| Horizon | all 8 |
| Steps | all 500 |
| Policy calls | all 63 |
| `success_error` | none |
| Unique initial states | 100 of 100 |
| NaN / Inf / CUDA error / traceback | none |
| Terminations | all `max_steps` |

## Results

| Metric | Value |
|---|---|
| Total episodes | 100 |
| Successful | **84** |
| Failed | **16** |
| Success rate | **0.84 (84 %)** |
| Wilson 95 % CI | [0.7558, 0.8990] |
| Clopper–Pearson 95 % CI | [0.7532, 0.9057] |
| Mean steps | 500.0 |
| Mean policy calls | 63.0 |
| Mean wall time per episode | 112.71 s |
| Median wall time per episode | 112.73 s |
| Min / max wall time | 108.43 / 118.01 s |
| Total policy wall time | 3.1308 h |
| Wall clock | 12:23:49–15:32 (approx. 3 h 08 min) |

Failed seeds (16): `100000`, `100004`, `100018`, `100026`, `100033`, `100035`, `100038`, `100040`, `100048`, `100059`, `100067`, `100070`, `100077`, `100080`, `100091`, `100094`

All 16 failures terminated at 500 steps with `max_reward=0.0` and
`success=false`; none had a success-predicate error. There were no
early terminations and no missing records.

## GPU and resource use

| Metric | Value |
|---|---|
| GPU utilization max / mean | 90.0 % / 42.28 % |
| GPU memory max / mean | 3570 MiB / 3523.4 MiB |
| GPU temperature max / mean | 82.0 °C / 76.6 °C |
| RAM used max | 12862 MiB |
| RAM available min | 18566 MiB |
| Disk available (last sample) | 151G |

The other user process PID 2371 (`app.container role --role trainer`)
remained at 298 MiB GPU memory with 0 % GPU utilization; it did not
conflict with this run and was not modified.

## Protocol differences

1. **Action space.** The written protocol describes 7-D delta actions.
   The archived checkpoint is the 10-D absolute-action variant
   (`abs_action=true`, `rotation_6d`, `image_abs.hdf5`). The harness runs
   the checkpoint-native semantics with `control_delta=false`. This B0 is
   therefore a checkpoint-native-action B0, not a 7-D delta-action B0.
2. **Seed provenance.** The checkpoint filename `test_mean_score=1.000`
   was produced with `test_start_seed=4,500,000` in its own env_runner,
   not with the Gate B seeds 100000–100099. The B0 rate of 0.84 is a new
   measurement on the protocol seeds; it neither reproduces nor contradicts
   the checkpoint file name, because the seed sets differ.
3. **B1 horizon.** H=16 and To=2 leave 15 future actions, so h=16 is
   invalid. B1 and B2 were not started in this round.
4. **Threshold semantics.** `success_threshold=0.99` is an internal
   per-episode record field, not the B0 GO threshold. The written protocol
   uses ≥0.70 as the continuation threshold; 0.84 exceeds it. This report
   does not make a Gate C or other downstream GO decision.

## Anomalies and incident record

- The first GPU-smoke attempt aborted before any episode because cuDNN
  dlopens `libcuda.so` while the 580 driver only installs `libcuda.so.1`.
  A workspace-local symlink (`.cuda_compat/libcuda.so`) was added to the
  launcher; no system driver or CUDA file was changed. The failed run
  directory was preserved and not reused.
- No CUDA error, NaN/Inf action, OOM, or early termination occurred in B0.
- The first formal seed (100000) failed; this is a real measured failure,
  consistent with the earlier CPU diagnostic. No seed was replaced.

## Per-episode results

| Seed | Success | Steps | Policy calls | Wall time (s) |
|---:|---|---:|---:|---:|
| 100000 | no | 500 | 63 | 118.01 |
| 100001 | yes | 500 | 63 | 114.03 |
| 100002 | yes | 500 | 63 | 112.48 |
| 100003 | yes | 500 | 63 | 113.61 |
| 100004 | no | 500 | 63 | 116.36 |
| 100005 | yes | 500 | 63 | 113.97 |
| 100006 | yes | 500 | 63 | 110.46 |
| 100007 | yes | 500 | 63 | 113.59 |
| 100008 | yes | 500 | 63 | 112.19 |
| 100009 | yes | 500 | 63 | 113.47 |
| 100010 | yes | 500 | 63 | 112.23 |
| 100011 | yes | 500 | 63 | 111.69 |
| 100012 | yes | 500 | 63 | 109.97 |
| 100013 | yes | 500 | 63 | 110.89 |
| 100014 | yes | 500 | 63 | 114.01 |
| 100015 | yes | 500 | 63 | 114.13 |
| 100016 | yes | 500 | 63 | 113.53 |
| 100017 | yes | 500 | 63 | 112.66 |
| 100018 | no | 500 | 63 | 113.97 |
| 100019 | yes | 500 | 63 | 113.29 |
| 100020 | yes | 500 | 63 | 112.33 |
| 100021 | yes | 500 | 63 | 112.71 |
| 100022 | yes | 500 | 63 | 112.27 |
| 100023 | yes | 500 | 63 | 114.31 |
| 100024 | yes | 500 | 63 | 113.67 |
| 100025 | yes | 500 | 63 | 111.87 |
| 100026 | no | 500 | 63 | 111.18 |
| 100027 | yes | 500 | 63 | 110.33 |
| 100028 | yes | 500 | 63 | 112.38 |
| 100029 | yes | 500 | 63 | 113.01 |
| 100030 | yes | 500 | 63 | 112.62 |
| 100031 | yes | 500 | 63 | 111.15 |
| 100032 | yes | 500 | 63 | 111.15 |
| 100033 | no | 500 | 63 | 111.79 |
| 100034 | yes | 500 | 63 | 111.70 |
| 100035 | no | 500 | 63 | 116.68 |
| 100036 | yes | 500 | 63 | 112.79 |
| 100037 | yes | 500 | 63 | 112.18 |
| 100038 | no | 500 | 63 | 112.87 |
| 100039 | yes | 500 | 63 | 112.00 |
| 100040 | no | 500 | 63 | 112.75 |
| 100041 | yes | 500 | 63 | 114.30 |
| 100042 | yes | 500 | 63 | 112.05 |
| 100043 | yes | 500 | 63 | 110.37 |
| 100044 | yes | 500 | 63 | 111.03 |
| 100045 | yes | 500 | 63 | 111.06 |
| 100046 | yes | 500 | 63 | 113.25 |
| 100047 | yes | 500 | 63 | 114.59 |
| 100048 | no | 500 | 63 | 109.51 |
| 100049 | yes | 500 | 63 | 112.11 |
| 100050 | yes | 500 | 63 | 112.31 |
| 100051 | yes | 500 | 63 | 113.92 |
| 100052 | yes | 500 | 63 | 112.03 |
| 100053 | yes | 500 | 63 | 113.49 |
| 100054 | yes | 500 | 63 | 110.51 |
| 100055 | yes | 500 | 63 | 112.40 |
| 100056 | yes | 500 | 63 | 113.40 |
| 100057 | yes | 500 | 63 | 113.99 |
| 100058 | yes | 500 | 63 | 112.30 |
| 100059 | no | 500 | 63 | 108.43 |
| 100060 | yes | 500 | 63 | 109.74 |
| 100061 | yes | 500 | 63 | 110.98 |
| 100062 | yes | 500 | 63 | 111.07 |
| 100063 | yes | 500 | 63 | 113.44 |
| 100064 | yes | 500 | 63 | 112.44 |
| 100065 | yes | 500 | 63 | 111.45 |
| 100066 | yes | 500 | 63 | 114.63 |
| 100067 | no | 500 | 63 | 112.16 |
| 100068 | yes | 500 | 63 | 110.70 |
| 100069 | yes | 500 | 63 | 113.61 |
| 100070 | no | 500 | 63 | 114.82 |
| 100071 | yes | 500 | 63 | 112.80 |
| 100072 | yes | 500 | 63 | 113.77 |
| 100073 | yes | 500 | 63 | 112.44 |
| 100074 | yes | 500 | 63 | 111.39 |
| 100075 | yes | 500 | 63 | 112.76 |
| 100076 | yes | 500 | 63 | 115.11 |
| 100077 | no | 500 | 63 | 113.11 |
| 100078 | yes | 500 | 63 | 112.75 |
| 100079 | yes | 500 | 63 | 112.01 |
| 100080 | no | 500 | 63 | 111.13 |
| 100081 | yes | 500 | 63 | 113.82 |
| 100082 | yes | 500 | 63 | 113.64 |
| 100083 | yes | 500 | 63 | 116.13 |
| 100084 | yes | 500 | 63 | 112.85 |
| 100085 | yes | 500 | 63 | 114.81 |
| 100086 | yes | 500 | 63 | 114.24 |
| 100087 | yes | 500 | 63 | 112.75 |
| 100088 | yes | 500 | 63 | 114.19 |
| 100089 | yes | 500 | 63 | 110.86 |
| 100090 | yes | 500 | 63 | 113.45 |
| 100091 | no | 500 | 63 | 114.66 |
| 100092 | yes | 500 | 63 | 112.42 |
| 100093 | yes | 500 | 63 | 112.05 |
| 100094 | no | 500 | 63 | 113.53 |
| 100095 | yes | 500 | 63 | 113.53 |
| 100096 | yes | 500 | 63 | 109.53 |
| 100097 | yes | 500 | 63 | 114.21 |
| 100098 | yes | 500 | 63 | 112.99 |
| 100099 | yes | 500 | 63 | 111.48 |

Machine-readable equivalents: `reports/b0_episodes.csv`,
`reports/b0_baseline_episodes.jsonl`, `reports/b0_analysis.json`.

## Conclusion

Under the checkpoint-native 10-D absolute-action interface, the formal
Gate B v2 B0 baseline on seeds 100000–100099 is **84/100 = 0.84**
(Wilson 95 % CI 0.756–0.899). The run is complete, internally consistent,
and free of unresolved errors. B1 and B2 remain unstarted.
