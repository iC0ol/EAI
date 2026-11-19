# Workstation execution log

Append dated entries here after actual workstation actions. Do not pre-fill success claims.

| Date/time (Asia/Shanghai) | Commit | Command/action | Result | Evidence paths | Decision |
|---|---|---|---|---|---|
| 2026-11-10 18:03 | 7a8d7de | `git switch codex/gate-b-v2`; inspected working tree | No tracked modifications; 95 untracked KYC experiment files preserved untouched | `git status` | Proceed |
| 2026-11-10 18:04 | 7a8d7de | `sha256sum gate_b_v2_source.tar.xz`; extract to isolated staging dir | Archive hash matched the historical README; 26 source files | `.gate_b_v2_unpack/` | Organize into `gate_b_v2/` |
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
| 2026-11-13 12:02–2026-11-14 19:55 | 2fe5cc9 | Formal B1 Full: 100 seeds × 5 horizons, seeds 200020–200119, h∈{1,2,4,8,15}, 500 steps, cuda:0 | 500/500 episodes complete; 399 success / 101 retained failures; pairing and environment lock verified; Cochran Q=34.2, p=6.78e-7; h=1/h=2 significantly below h=8 after Holm; h=15 non-inferior and cheaper | `runs/gateb_b1_full_20261113T0400Z/`; `reports/B1_FULL_REPORT.md`, `reports/b1_full_*` | CONDITIONAL GO for B2 preparation; B2 not started |
| 2026-11-16 (post-Full) | — | GitHub Actions: `ubuntu-latest` migrated to Ubuntu 26.04 and setup-python could not supply Python 3.9 | Pinned both audit jobs to `ubuntu-24.04`; no experiment or data change | `.github/workflows/gate-b-v2-source-audit.yml` | Rerun CI |
| 2026-11-16 18:00+ | `4e7fcd5` | `git fetch origin`; checked out `codex/b2-protocol-20261116`; verified HEAD equals the protocol commit | Branch/commit correct; no tracked modifications; 96 pre-existing untracked KYC files preserved | `git status`, `git rev-parse HEAD` | Implement B2 v1.1 |
| 2026-11-16 | — | Implemented B2 geometry, harvest, snapshot, branch, analysis, config/CLI; added B2 tests | 149 tests pass; no simulator branch episode run | `gate_b_v2/src`, `gate_b_v2/tests` | Continue |
| 2026-11-16 | — | Live collision-geometry audit on RTX 3090, reset seed 299999 | **PASS**: four bars 46–49, handle 50 excluded, peg geom 13, c_xy and z_gap signs/frame/tilt/finite checks pass | `runs/b2_geometry_audit_preflight/b2_geometry_audit.json` | Continue |
| 2026-11-16 | — | Snapshot/replay PREFLIGHT, reserved seed 299999 | Gate reached at source step 124; state/obs/geometry restore and deterministic replay errors all 0; controller/gripper capture audit complete | `runs/b2_preflight_299999/`, `runs/b2_preflight_det_c/`, `runs/b2_preflight_det_d/` | PASS |
| 2026-11-16 | — | Two independent seed-299999 PREFLIGHT runs after deterministic gzip/tensor RNG serialization | Identical snapshot SHA256 `c52aaa5c2b5c83374da376891d521b28baeaa0f8790ee6435dfb33316f9cb5b3` | `runs/b2_preflight_det_c/`, `runs/b2_preflight_det_d/` | Deterministic |
| 2026-11-16 | — | Throwaway state-harvest smoke with non-formal seeds 299990, 299991 | 2/2 first-entry captures; both records explicitly `PREFLIGHT`, `scientific_data=false` | `runs/b2_preflight_smoke/state_smoke/` | Smoke only |
| 2026-11-16 | — | Final comprehensive PREFLIGHT with frozen code: seed 299999 plus smoke seeds 299990,299991 | Geometry PASS; gate at step 124; snapshot SHA `c52aaa5c…a37b2d`; all restore/replay errors 0; 2/2 PREFLIGHT smoke records | `runs/b2_preflight_final/` | PASS |
| 2026-11-16 | — | Rebuilt `gate_b_v2_source.tar.xz`; extracted to clean `/tmp` directory; source archive audit | Code/tests/config/scripts byte-identical; 148 passed, 1 skipped (vendored DP source not packaged). Authoritative archive hash is recorded only in the independent acceptance report and CI configuration. | `gate_b_v2_source.tar.xz` | Audit PASS |
| 2026-11-17 | `b6dcf00` | Synced `codex/b2-protocol-20261116`; verified baseline and clean tracked tree | Baseline matched; pre-existing untracked KYC files preserved | `git status`, `git rev-parse HEAD` | Second revision |
| 2026-11-17 | `b23a65d` | Implemented second-revision fixes: authorization gates, preflight seed/fallback, fixed-config analysis, permutation tests, B1 lock, policy reset, harvest overwrite protection | **210 tests pass**; no formal discovery/confirmation/branch run | `gate_b_v2/src`, `gate_b_v2/tests` | Continue |
| 2026-11-17 | `e8f4f4a` | Live geometry audit + seed-299999 PREFLIGHT with final revised code | Geometry PASS; gate at source step 124; snapshot SHA `c52aaa5c…a37b2d`; all restore/replay errors 0; non-formal state smoke 2/2 marked PREFLIGHT | `runs/b2_preflight_second_revision_final/` | PASS |
| 2026-11-17 | `b23a65d` | Exported public PREFLIGHT JSON evidence | Small JSON only; marker PREFLIGHT; scientific_data=false; no snapshot binary | `gate_b_v2/reports/preflight/` | Evidence |
| 2026-11-17 | — | Source archive rebuilt, clean extraction and audit | Code/tests/config/scripts/PREFLIGHT evidence byte-identical; 209 passed, 1 skipped; archive hash recorded in independent report/CI, not in this log | `gate_b_v2_source.tar.xz` | Audit PASS |

## Historical decision snapshot (as of 2026-11-17, before Discovery completion)

Formal B0 is **COMPLETED** at 84/100 under checkpoint-native 10-D absolute
action semantics. B1 Pilot and B1 Full are **COMPLETED**; B1 Full is
independently reviewed. The B2 v1.1 protocol is frozen. The B2 code has a
first implementation and a second revision, with a passing live geometry audit
and seed-299999 PREFLIGHT, but it has **not yet passed the second independent
review**. No Discovery or Confirmation authorization file exists; neither split
is authorized. No B2 state or branch episode has been collected, and no Gate C
decision is made. See `reports/B2_SECOND_REVISION_REPORT.md`.

| 2026-11-17 14:34–14:52 CST | `a58278f` / schema 3 development | Reserved seed 299999 local restore diagnostics on the existing RTX 3090 environment | Schema 2 hashes reproduced. `mj_forward()` changes four quaternion components by at most `2.22e-16`. Legacy observation/geometry mismatches trace to the last Euler substep timing. XML-reload render residual measured with an in-place native model control. | `reports/preflight_third_revision/b2_preflight_restore_diagnostics.json` | Capture pre-integration pose and independently verify live observation |
| 2026-11-17 14:57–14:58 CST | `2f1a495` | `source scripts/gateb_env.sh`, `python -m compileall -q src tests`, `python -m pytest -q`, `python -m gate_b_v2.cli b2-preflight --run-dir runs/b2_preflight_third_revision --seed 299999` | **271 passed** with the prior SciPy constant-input warning. Live geometry audit **PASS**. Stage Gate at step 124. Independent restore **PASS** with state and geometry error 0 and worst fresh-observation MAE `9.893e-5`. Replay A/B errors 0. | `reports/preflight_third_revision/` | PREFLIGHT only |
| 2026-11-17 | `2f1a495` | `python -m gate_b_v2.cli b2-export-preflight-evidence --run-dir runs/b2_preflight_third_revision --output-dir reports/preflight_third_revision` | Public JSON only, marked `PREFLIGHT` and `scientific_data=false`. Driver 580.178.04, Python 3.9.13, PyTorch 1.12.1+cu116, CUDA 11.6, MuJoCo offscreen OSMesa. | `reports/B2_SNAPSHOT_INDEPENDENT_VALIDATION_REPORT.md` | Prepare source archive |
| 2026-11-17 | `2f1a495` | Clean extraction under `runs/b2_third_revision_archive_audit/` and audit using `PYTHONPATH=$PWD/src`, `python -m compileall -q src tests`, `python -m pytest -q` | 72 packaged files checked against the workstation tree and all five PREFLIGHT evidence hashes matched. **270 passed, 1 skipped** because the packaged source excludes the vendored DP tree. | `reports/B2_THIRD_REVISION_REPORT.md` | Source Archive Audit PASS |

## B2 v1.1 Discovery

| Date/time (Asia/Shanghai) | Commit | Command/action | Result | Evidence |
|---|---|---|---|---|
| 2026-11-17 15:36:16 to 2026-11-18 00:42:41 | `f1e63c5` (`2f1a495` implementation) | Discovery launcher ran `b2-harvest` followed by `b2`, both with `--split discovery` and the same run directory | RTX 3090, Python 3.9.13, PyTorch 1.12.1+cu116 and CUDA 11.6. Harvest selected 30 of 90 eligible states from the primary pool. Snapshot validation passed for all 30 states. 450 Branch records passed integrity checks. Launcher exited 0 after 9 h 06 min 25 s. | `runs/b2_discovery_20261117T153523/b2_discovery_launcher.log` |
| 2026-11-18 | `f1e63c5` | Verified the raw run and executed `python -u -m gate_b_v2.cli analyze --run-dir runs/b2_discovery_20261117T153523` | All 109 originals passed post-analysis SHA256 verification. Independent recomputation matched E = 0.055707 and its 95% CI [-0.015805, 0.156406]. `DISCOVERY_UNCERTAIN_CONFIRMATION_JUSTIFIED` permits separate Confirmation review. | [Published results and closeout](b2_discovery_20261117/README.md) |
| 2026-11-18 | `d0da736` reviewed baseline | `sha256sum` for the local run and public bundle, read-only `analyze_b2_split()` on the published records, live asset fingerprint check, `validate_formal_authorization()`, B2 CLI help, and `python -m pytest -q` | 116 local and 16 public checksums verified before the documentation update. The frozen analysis and all 450 records matched. Clearance coverage, ceiling and geometric associations were derived from raw data. Runtime and PREFLIGHT locks passed. The Confirmation gate refused the missing authorization. 271 tests passed. | [Discovery closeout](b2_discovery_20261117/B2_DISCOVERY_CLOSEOUT.md) · [Confirmation execution plan](B2_CONFIRMATION_EXECUTION_PLAN.md) |

## Discovery closeout decision (2026-11-18, before Confirmation authorization)

| Item | Current status |
|---|---|
| B0 | COMPLETED |
| B1 Pilot | COMPLETED |
| B1 Full | COMPLETED |
| B2 v1.1 Protocol | FROZEN |
| B2 Discovery | COMPLETED |
| Discovery data integrity | 30/30 snapshots PASS, 450/450 branches PASS |
| Discovery documentation closeout | COMPLETED |
| Confirmation preparation | COMPLETED |
| Confirmation independent review | 待最终验收 |
| Confirmation Authorization | NOT AUTHORIZED |
| Confirmation Harvest | NOT STARTED |
| Confirmation Branch | NOT STARTED |
| Gate C | NOT AUTHORIZED |

- E = 0.055707
- 95% CI = [-0.015805, 0.156406]
- permutation p = 0.343857
- Decision = `DISCOVERY_UNCERTAIN_CONFIRMATION_JUSTIFIED`

The Discovery decision meets the preregistered continuation condition. Confirmation requires separate authorization after final independent review. The RTX 3090 workstation rechecked all 116 entries in the original `B2_DISCOVERY_SHA256SUMS.txt` with `sha256sum --check`. [Discovery closeout](b2_discovery_20261117/B2_DISCOVERY_CLOSEOUT.md)

## B2 v1.1 Confirmation launch

| Date/time (Asia/Shanghai) | Command/action | Workstation readback |
|---|---|---|
| 2026-11-18 10:59–11:03 | `git fetch origin`, `source scripts/gateb_env.sh`, `nvidia-smi`, Python runtime and asset checks, `df -h .` | Local and remote `codex/b2-protocol-20261116` at `684f2cc89fd96c52d00a005d16c3c001650eb94b`. Clean tracked tree at launch. RTX 3090 on `cuda:0`, driver 580.178.04, Python 3.9.13, PyTorch 1.12.1+cu116, CUDA 11.6, robomimic 0.2.0, robosuite 1.2.0 and mujoco_py 2.0.2.13. Disk available 151 GiB. |
| 2026-11-18 11:03:31 | `sha256sum --check --quiet B2_DISCOVERY_SHA256SUMS.txt`, live `validate_preflight_gate()`, `cmp` and `sha256sum` of all three PREFLIGHT copies, independent `validate_formal_authorization()` | All 116 original Discovery checksums passed. 450 records and the `DISCOVERY_UNCERTAIN_CONFIRMATION_JUSTIFIED` decision were verified. PREFLIGHT and Confirmation authorization passed. Authorization SHA256 `a32ddfb43f73f628ea07e32b127cc7d396dfbfb56bd5e7f2093bdb33f63f99e5`. |
| 2026-11-18 11:07:24 | Existing unit tests, `bash -n`, execution-plan section 4 code comparison, then `nohup setsid bash "$RUN_DIR/launch_b2_confirmation.sh" > "$RUN_DIR/b2_confirmation_launcher.log" 2>&1 < /dev/null &` | 271 tests passed with the existing SciPy constant-input warning. Launcher 2282469 began `b2-harvest --split confirmation` as PID 2282486 under `runs/b2_confirmation_20261118T110331/`. |
| 2026-11-18 11:08:08 and 11:09:15 | `ps`, launcher status and log readback, `nvidia-smi` and `nvidia-smi pmon` | `HARVEST_RUNNING`. The launcher leads an independent session under the user systemd process with no TTY. The 44-second check confirmed process and log activity during initialization. The GPU follow-up matched Harvest PID 2282486 to 2992 MiB and sampled 45% SM utilization. Candidate snapshots began appearing. Startup log showed the torchvision deprecation warnings and no authorization, CUDA or environment errors. |

The frozen implementation is `2f1a495e495d926a91a317948c80184eccfc464d` with source tree SHA256 `e52aeb4a25a4f94e4684f622a0b806164caf20d339c05e8de114b3b261175378`. The workstation recomputed the B1 Full manifest SHA256 `1619fa873df00628cc7ec0d414ee5f8d029ae30e0808ab1e00a2905ef41c4175` and PREFLIGHT environment fingerprint SHA256 `84647b606c8cf107cb73e44491a351ee93a119fede8e51734911a2373e33f276`.

At handoff the launcher was collecting Confirmation source states. It checks Harvest completion and deterministic cross-split isolation before invoking the frozen Branch runner, which validates all 30 snapshots before the first Branch.

## B2 v1.1 Confirmation closeout

| Date/time (Asia/Shanghai) | Command/action | Workstation readback |
|---|---|---|
| 2026-11-18 19:53:35 | Launcher Branch readback and shutdown | `COMPLETE`, exit 0. Total 8 h 46 min 11 s. Primary Harvest produced 91 candidates and selected 30 states. Cross-split isolation and all 30 independent snapshot checks passed. |
| 2026-11-19 | `sha256sum --check --quiet`, live `validate_formal_authorization()`, execution plan section 4, `_b2_inputs()` | 116 Discovery checksums and 111 Confirmation checksums passed. Live asset, runtime, source and authorization fingerprints matched. The 450 Branch keys, serialized order, deterministic selection, and common policy-noise seeds matched the protocol. All 91 candidate snapshot hashes matched. |
| 2026-11-19 | `python -u -B -m gate_b_v2.cli analyze --run-dir runs/b2_confirmation_20261118T110331` and independent raw-data recomputation | E = 0.00 percentage points with a 95% state-cluster bootstrap interval of [0.00, 0.00] percentage points and permutation p = 1. The primary state contrast was constant. SciPy reported the corresponding undefined Spearman statistic. Decision `CONFIRMATION_NO_PRACTICALLY_MEANINGFUL_EFFECT`. All 111 original checksums were rechecked after analysis. |
| 2026-11-19 | Recomputed frozen analysis from the prepared publication inputs | All statistics matched the workstation results. The published analysis binds the public run manifest and uses JSON null for the undefined Spearman values. |

Gate C status is **NOT AUTHORIZED**. [Closeout and interpretation limits](b2_confirmation_20261118/B2_CONFIRMATION_CLOSEOUT.md) · [Published evidence](b2_confirmation_20261118/README.md)

## B2 Confirmation Continuation-h4 engineering checks

| Date (Asia/Shanghai) | Command/action | Workstation readback |
|---|---|---|
| 2026-11-19 | `git fetch origin`, checkout of `codex/b2-continuation-h4-20261119` | Started from the accepted Confirmation closeout `6d2165418c84b5300eb9a041df56ebf39218da4a`. The tracked tree was clean. |
| 2026-11-19 | `source scripts/gateb_env.sh`, diagnostic `--check-source`, and `nvidia-smi` | All 111 original checksums passed. Original authorization, 30 snapshot references, and 450 baseline pairs verified. The frozen B2 source fingerprint matched. Python 3.9.13, PyTorch 1.12.1+cu116, CUDA 11.6 and RTX 3090 driver 580.178.04 matched the workstation record. |
| 2026-11-19 | Full pytest suite with `tests` and `diagnostics/continuation_h4`, then `bash -n` on the launcher | 299 passed. The original constant-input SciPy warning recurred in the frozen analysis test. Launcher syntax passed. |

The diagnostic uses the existing Confirmation snapshots and the original seed order. Live snapshot recheck, Branch progress, GPU telemetry and terminal exit status are recorded in the dedicated run directory. [Diagnostic commands and outputs](../diagnostics/continuation_h4/README.md)
