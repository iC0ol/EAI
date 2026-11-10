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
| 2026-11-10 19:43→ | — | CPU smoke on checkpoint's own seeds 4,500,000/4,500,001 | Running; not an official B0 result | `runs/cpu_official_seeds2/` | Await |
| 2026-11-10 18:40 | 3edc36b | `pytest -q`; `compileall`; `bash -n` | 25 passed; clean; clean | `tests/`, `reports/CODE_REVIEW.md` | Commit |

## Current decision

Official B0 is blocked by the GPU driver mismatch; B1 is additionally blocked
by the invalid h=16 and by B0; B2 is blocked by the unfrozen stage window and
by B0/B1. The CPU runs validate the pipeline only. No official success rate is
claimed. See `reports/B0_STATUS.md`.

