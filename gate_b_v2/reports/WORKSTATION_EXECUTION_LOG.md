# Workstation execution log

Append dated entries here after actual workstation actions. Do not pre-fill success claims.

| Date/time (Asia/Shanghai) | Commit | Command/action | Result | Evidence paths | Decision |
|---|---|---|---|---|---|
| 2026-11-10 18:03 | 7a8d7de | `git switch codex/gate-b-v2`; inspected working tree | No tracked modifications; 95 untracked KYC experiment files preserved untouched | `git status` | Proceed |
| 2026-11-10 18:04 | 7a8d7de | `sha256sum gate_b_v2_source.tar.xz`; extract to isolated staging dir | SHA256 matched `5a4a43e0…aaa7b`; 26 source files | `.gate_b_v2_unpack/` | Organize into `gate_b_v2/` |
| 2026-11-10 18:06 | 7a8d7de | Downloaded Square-MH checkpoint and low-dim dataset | 4,627,773,609 B; 123,863,240 B | `reports/ASSETS.md` | Continue |
| 2026-11-10 18:13 | 7a8d7de | Checkpoint SHA256 / zip check | `adaf1785…27c6d`; `7e589063…42887` | `reports/ASSETS.md` | Continue |
| 2026-11-10 18:14 | 7a8d7de | Created isolated venv; pinned torch 1.12.1+cu116 | Aliyun mirror stalled; restarted against official PyPI | `reports/ENVIRONMENT.md`, `reports/requirements.lock` | Continue |
| 2026-11-10 18:25 | 3edc36b | Installed robomimic 0.2.0 / robosuite 1.2.0 fork / MuJoCo 2.1 | Imports OK | `reports/runtime_versions.json` | Continue |
| 2026-11-10 18:28 | 3edc36b | Built headless MuJoCo (OSMesa 23.2.1, no sudo) | `mujoco_py 2.0.2.13` imports; free-mujoco-py GPU autodetect not usable on this layout | `reports/ENVIRONMENT.md` | Continue |
| 2026-11-10 18:29 | 3edc36b | Audited the actual checkpoint payload | H=16, To=2, 15 future actions, **10-D absolute action**, EMA, normalizer in state dict | `reports/checkpoint_audit.json` | Fix action semantics |
| 2026-11-10 18:31 | 3edc36b | CPU checkpoint load and forward | EMA policy; chunk `(15, 10)`; 6.87 s | console log | Continue |
| 2026-11-10 18:32 | 3edc36b | Created live NutAssemblySquare env; one step; geometry | 2×84×84 RGB, 7-D OSC `control_delta=false`, aperture 0.02275 m | console log | Continue |
| 2026-11-10 18:33 | 3edc36b | 16-step end-to-end rollout (CPU) | 2 policy calls, 15.15 s, JSONL written | `runs/cpu_pipeline_smoke/` | Pipeline works |
| 2026-11-10 18:34 | — | `nvidia-smi` / torch CUDA check | **BLOCKED**: kernel 550.144.03 vs userspace 580.178.04; CUDA error 804 | `reports/B0_STATUS.md` | Official B0 cannot start |
| 2026-11-10 18:32→18:52 | — | 5×500-step CPU-only smoke (pipeline validation) | Stopped after 2 episodes: 0/2, 63 calls each | `runs/cpu_smoke_full5/` | Investigate |
| 2026-11-10 18:53→19:05 | — | 500-step failure-mode diagnostic, seed 100000 | Approaches nut but hovers 3–5 cm off; gripper never closes | `runs/diag500/`, `runs/diag100000/` | Compare against official images |
| 2026-11-10 19:07→19:35 | — | Downloaded official `image.hdf5` (6.96 GB) with resume | Complete; SHA256 `d675c4a9…ff403`; single task, not the 84.8 GB bundle | `assets/square_mh/image.hdf5` | Compare |
| 2026-11-10 19:37 | — | Rendered 3 official states and compared with stored frames | Direct orientation corr 0.998/0.9998; mean diff 1.2–1.6/255; flips decisively worse | `reports/render_comparison.json` | Renderer is faithful |
| 2026-11-10 19:38 | — | Policy query on official stored observations | Predicted pose 0.8–2.5 cm from next demo pose; gripper sign matches | `reports/policy_replay_check.json` | Policy/action path correct |
| 2026-11-10 19:40 | — | Closed loop from official `demo_0` start state | **Success** at ~120 steps (200 cap) | console log | Harness validated |
| 2026-11-10 19:41 | — | Read checkpoint `task.env_runner` | `test_start_seed=4,500,000`, `n_test=50` — not the protocol's 100000 | checkpoint payload | B0 is a new measurement |
| 2026-11-10 19:43→20:01 | — | CPU smoke on checkpoint's own seeds 4,500,000/4,500,001 | **2/2 success** (500 steps, 63 calls each, max_reward 1.0); not an official B0 result | `reports/cpu_official_seeds2_*` | Harness validated |
| 2026-11-10 18:40 | 3edc36b | `pytest -q`; `compileall`; `bash -n` | 25 passed; clean; clean | `tests/`, `reports/CODE_REVIEW.md` | Commit |
| 2026-11-11 12:01 | — | Post-reboot CUDA check | Driver 580.178.04 both sides; RTX 3090, sm_86, matmul OK | console | Proceed |
| 2026-11-11 12:03 | 0559e16 | First GPU smoke attempt | Aborted: cuDNN could not dlopen unversioned `libcuda.so` | `runs/b0_smoke_gpu_20261111/` (preserved) | Fix loader path |
| 2026-11-11 12:04 | 0559e16 | Added workspace-local `.cuda_compat/libcuda.so` symlink; cuDNN conv test | Conv OK; no system file changed | `reports/B0_SMOKE_GPU.md` | Retry |
| 2026-11-11 12:03→12:23 | 0559e16 | GPU smoke, independent seeds 4,600,000–4,600,009, h=8 | **10/10 success**, 500 steps, 63 calls, 113 s each; max util 90 %, max mem 3,567 MiB | `reports/b0_smoke_gpu_*` | Proceed to B0 |
| 2026-11-11 12:23→15:32 | — | **Formal B0, original config, seeds 100000–100099, h=8, 500 steps, cuda:0** | **84/100 success (0.84)**; Wilson CI 0.7558–0.8990; no errors; 16 failures retained | `runs/b0_gpu3090_20261111T1230/` | Complete |
| 2026-11-11 15:34 | 09e9ca6 | Integrity and statistics analysis | 100 unique seeds/states, h=8, 500 steps, 63 calls, no `success_error` | `reports/b0_analysis.json`, `reports/B0_REPORT.md` | B0 complete |
| 2026-11-11 (post-B0) | — | Static protocol amendment and B1 preparation; no simulator/GPU run | h∈{1,2,4,8,15}; B1 seeds 200000+; Pilot/Full separate; 38 tests pass | `reports/B1_PROTOCOL_AMENDMENT.md`, `reports/B1_READINESS_REPORT.md` | Await independent acceptance |
| 2026-11-12 (second revision) | — | Static code/doc revision: disjoint Pilot/Full seeds, strict completeness gate, B2 isolation, CI audit fix; no simulator/GPU run | 56 tests pass; 12/12 B0 artifacts unchanged; archive audit reproduced and fixed | `reports/B1_SECOND_REVISION_REPORT.md` | Await independent review and B1 authorization |
| 2026-11-12 (final pre-launch) | — | Runtime parameter lock: B0 fingerprint, CLI/config/runner gates, Manifest and analysis environment checks; static only | 114 tests pass; real checkpoint/dataset/DP-tree hashes match B0; 12/12 B0 artifacts unchanged | `reports/B1_FINAL_READINESS_REPORT.md` | Await independent review and B1 Pilot authorization |
| 2026-11-12 12:01–18:24 | 83c3528 | Formal B1 Pilot: 20 seeds × 5 horizons, seeds 200000–200019, h∈{1,2,4,8,15}, 500 steps, cuda:0 | 100/100 episodes complete; 82 success / 18 retained failures; pairing and environment lock verified; h=15 stable; Cochran Q p=0.1586, no Holm-significant contrast | `runs/gateb_20261112T040110Z/`; `reports/b1_pilot_*` | GO to request separate B1 Full approval |

## Current decision

Formal B0 is **COMPLETED** at 84/100 under checkpoint-native 10-D absolute
action semantics. The written ≥0.70 continuation threshold is met. B1 remains
blocked by the invalid h=16 (15 future actions) and has not started; B2
remains blocked by the unfrozen stage window. No Gate C decision is made.
See `reports/B0_REPORT.md` and `reports/B0_STATUS.md`.

