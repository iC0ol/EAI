# B1 final readiness report

Date: 2026-11-12 (Asia/Shanghai).
Branch: `codex/gate-b-v2`.
Base commit: `55a23073b5b4dc49e5e80516d60d46969c8f75ea`.
B0 commit: `09e9ca63b89349c3905a7dc2bca9fd8e2b99844b`.
Status: **CODE_REVISION_COMPLETE — AWAITING INDEPENDENT REVIEW AND B1 PILOT
AUTHORIZATION.**

This round locked the formal B1 runtime and added the corresponding manifest
and analysis gates. **No B0, B1 Pilot, B1 Full, B2, simulator, GPU inference or
training was executed.**

## 1. Changes

| File | Change | Reason |
|---|---|---|
| `src/gate_b_v2/locks.py` | New B1 lock: B0-derived checkpoint/dataset/DP-tree hashes, 500 steps, H=16/To=2, horizons, GPU/versions, device, policy offset, canonical config fingerprint; pure validators and manifest builder | Make the formal environment non-negotiable and testable without starting the simulator |
| `src/gate_b_v2/cli.py` | B1 parser now has only `--b1-phase` and `--run-dir`; `_cmd_b1` loads the fixed project config and passes no path/step overrides | Prevent `--checkpoint`, `--dataset`, `--dp-root`, `--max-steps` and `--config` from changing formal B1 |
| `src/gate_b_v2/runner.py` | `run_b1` builds and validates the actual run manifest via `build_b1_run_manifest` before writing it or any episode; every row carries the environment fields | Reject wrong hashes/versions/steps/GPU/device/offset before data collection; make each record auditable |
| `src/gate_b_v2/analysis.py` | Validates the full environment lock on the manifest and every record, and checks `policy_seed = policy_seed_offset + seed` | Prevent a wrong-parameter run from producing a plausible formal statistic |
| `tests/test_b1_locks.py` | New lock, manifest, CLI and real DP-tree tests | Cover acceptance and every required rejection path |
| `tests/test_b1_analysis.py` | Synthetic records/manifests now carry the environment fingerprint | Exercise the new analysis gate |
| `README.md`, `IMPLEMENTATION_STATUS.md`, `B1_PROTOCOL_AMENDMENT.md`, `B1_READINESS_REPORT.md`, `GATE_B_PROTOCOL.md` | Document the runtime lock and CLI restrictions | Keep the protocol and implementation consistent |
| `reports/WORKSTATION_EXECUTION_LOG.md` | Static-work entry | Preserve execution evidence |
| `reports/B1_FINAL_READINESS_REPORT.md` | This report | Final acceptance record |

No B0 file, checkpoint, dataset, environment, cache or unrelated experiment was
modified.

## 2. Parameter-lock result

| Layer | Control |
|---|---|
| **CLI** | B1 accepts only `--b1-phase {pilot,full}` and `--run-dir`. Parser tests confirm `--dp-root`, `--checkpoint`, `--dataset`, `--max-steps` and `--config` are rejected. |
| **Config** | `_cmd_b1` loads only the fixed project `configs/gate_b.yaml`. `validate_b1_config` compares all critical values to hard-coded lock values, so replacing the file with changed horizons, seeds, counts, reference, alpha, practical/ceiling/floor thresholds, policy offset, device, task/dataset identity, expected H or max steps fails closed. A canonical critical-parameter fingerprint is recorded. |
| **Runner** | `run_b1` re-resolves the phase seed range, validates complete-interval disjointness, then calls `build_b1_run_manifest` with the actual runtime manifest. It verifies file hashes, versions, GPU, device, steps, H/To, horizons, policy offset and config fingerprint before writing `b1_{phase}_run.json` or any episode. |
| **Manifest** | `b1_{phase}_run.json` contains the actual checkpoint/dataset/DP-tree hashes, max steps, H/To, horizon list, GPU, torch/CUDA, robomimic/robosuite/mujoco_py, device, policy offset, phase, seed start/end, episode count, records file and critical config fingerprint. |
| **Analysis** | Formal analysis validates the manifest against the lock, validates every row's environment fields against the manifest, and validates every policy seed. Any mismatch aborts before statistics are written. |

There is no remaining CLI or ordinary-config path that can silently change the
checkpoint, dataset, source tree, step limit, horizon list, device, GPU
requirement, policy offset or seed range. `--run-dir` only selects where the
locked run is written.

## 3. Environment fingerprint

| Item | B0 baseline / B1 lock | Local verification |
|---|---|---|
| Checkpoint SHA256 | `adaf17854fb8ff8acaccc56adbf6af321c7bec7fecb22de5257772ec81927c6d` | **MATCH** |
| Dataset SHA256 | `7e58906366d79996f13785ff2dd0fe346230373532addc2afc7c92611ae42887` | **MATCH** |
| DP source tree SHA256 | `aec43e20abb0902b606e61fc4a391605ab755e59233ecb5f6bdbfbe8df372f21` | **MATCH** (same `sha256_tree` definition as B0) |
| Max steps | 500 | locked |
| Prediction horizon H | 16 | locked |
| Observation steps To | 2 | locked |
| Execution horizons | `[1,2,4,8,15]` | locked |
| GPU | NVIDIA GeForce RTX 3090 | locked |
| torch / CUDA | 1.12.1+cu116 / 11.6 | locked |
| robomimic / robosuite / mujoco_py | 0.2.0 / 1.2.0 / 2.0.2.13 | locked |
| Device | `cuda:0` | locked |
| Action interface | 10-D absolute → 7-D OSC_POSE, `control_delta=false`, EMA | locked |
| Policy seed offset | 700000 | locked |
| Critical config fingerprint | `b34de158b416d6cbcc84dfc6bd0a3eb826461f5a7a9d662d236c1b210cd1bcec` | computed from locked values |

The DP tree hash uses `core.sha256_tree` unchanged: sorted relative paths,
file SHA256 values, `__pycache__`/`.pyc` excluded — identical to the B0
manifest definition.

## 4. Test results

| Check | Result |
|---|---|
| `pytest -q` (local, vendored DP present) | **114 passed, 0 failed** |
| `python -m compileall -q src tests` | clean |
| `bash -n scripts/*.sh` | clean |
| YAML parse (config + workflow) | clean |
| `git diff --check` | clean |
| Real checkpoint hash vs lock | MATCH |
| Real dataset hash vs lock | MATCH |
| Real DP tree hash vs lock | MATCH |
| B0 artifact SHA256 vs `09e9ca6` | **12/12 unchanged** |
| B1 CLI options | only `--b1-phase`, `--run-dir` |
| GitHub Actions current harness | **113 passed, 1 skipped** |
| GitHub Actions archive audit | **8 passed** |

New lock tests cover: correct fingerprint acceptance; checkpoint, dataset and
DP-tree hash rejection; max_steps 100/1000 rejection; H/To change rejection;
horizon change rejection; policy offset change rejection; GPU/torch/CUDA/
robomimic/robosuite/mujoco_py change rejection; device change rejection;
config fingerprint change rejection; manifest/record mismatch rejection; CLI
override rejection; normal Pilot and Full manifest construction; and the real
DP-tree hash definition when the vendored source is present.

### GitHub Actions

The workflow at `.github/workflows/gate-b-v2-source-audit.yml` runs the
archive audit and the current harness tests. Post-push result for commit
`412e0db`:

| Trigger | Run | Result |
|---|---|---|
| push | [43146004714](https://github.com/iC0ol/EAI/actions/runs/43146004714) | **success** |
| `pull_request` (Draft #1) | [43146013642](https://github.com/iC0ol/EAI/actions/runs/43146013642) | **success** |

Job logs:

- `source-archive-audit`: **8 passed in 0.12 s**.
- `current-harness-tests`: **113 passed, 1 skipped in 0.93 s**. The skipped
  test is the real DP-tree hash check because the vendored `third_party`
  source is Git-excluded and therefore absent on the CI runner; the same test
  passes locally (114 passed).

The earlier source-audit runs on `1de8287` and `55a2307` also passed. No
unexecuted check is reported as successful.

## 5. B0 historical data protection

The 12 accepted B0 artifacts were compared by SHA256 with the B0 commit
`09e9ca6`:

```text
b0_baseline_episodes.jsonl
b0_analysis.json
b0_baseline_summary.json
b0_episodes.csv
b0_environment_manifest.json
gpu_monitor_b0_summary.json
B0_REPORT.md
B0_STATUS.md
b0_smoke_gpu_episodes.jsonl
b0_smoke_gpu_summary.json
b0_smoke_gpu_manifest.json
gpu_monitor_smoke_summary.json
```

Result: **12/12 unchanged.** B0 was not rerun; failures were not deleted,
replaced or mixed with B1.

## 6. B1 launch readiness

| Question | Answer |
|---|---|
| Is Pilot ready for formal execution? | **Code/config: yes.** It will validate the B0 fingerprint and the locked 20×5 design before any episode. It has not been executed. |
| Is Full ready for formal execution? | **Code/config: yes.** It uses the separate 200020–200119 range and the same environment lock. It has not been executed. |
| Can any parameter entry still change the experiment? | **No ordinary CLI/config path.** B1 has no path/config/step overrides; critical config changes and actual runtime mismatches fail closed. `--run-dir` only changes output location. |
| Any unresolved engineering risk? | Actual h=15 runtime behaviour and cost remain unmeasured until the authorized Pilot; B2 state collection is intentionally separate and still unstarted. |
| May the research lead approve B1 Pilot? | **Yes, after independent review of this commit and acceptance of the locked values/thresholds.** |

## 7. Experiment execution status

- B0: **COMPLETED** — 84/100 = 0.84, Wilson 95% CI 0.7558–0.8990.
- B1 Pilot: **NOT EXECUTED.**
- B1 Full: **NOT EXECUTED.**
- B2: **NOT EXECUTED.**
- No simulator, GPU, MuJoCo/robosuite episode or training command was run in
  this round.
- No `runs/b1_*` directory exists.

**Final status: CODE_REVISION_COMPLETE — AWAITING INDEPENDENT REVIEW AND B1
PILOT AUTHORIZATION.**
