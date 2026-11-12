# B1 protocol amendment (after B0 acceptance)

Date: 2026-11-11 (Asia/Shanghai).
Branch: `codex/gate-b-v2`.
Base commit: `09e9ca63b89349c3905a7dc2bca9fd8e2b99844b`.
Status: **CODE_REVISION_COMPLETE** — awaiting independent acceptance and
explicit B1 authorization.

This amendment changes the written experiment protocol and the minimal code
needed to execute it. **No B1, B2, simulator, GPU experiment or training was
run in this round.**

## 1. B0 history is unchanged

All B0 evidence files were compared byte-for-byte with the blob at the base
commit `09e9ca6`:

| File | SHA256 vs base |
|---|---|
| `b0_baseline_episodes.jsonl` | match |
| `b0_analysis.json` | match |
| `b0_baseline_summary.json` | match |
| `b0_episodes.csv` | match |
| `b0_environment_manifest.json` | match |
| `gpu_monitor_b0_summary.json` | match |
| `B0_REPORT.md` | match |
| `B0_STATUS.md` | match |
| `b0_smoke_gpu_episodes.jsonl` | match |
| `b0_smoke_gpu_summary.json` | match |
| `b0_smoke_gpu_manifest.json` | match |
| `gpu_monitor_smoke_summary.json` | match |

The 100 B0 episodes, 16 failures and the 0.84 result are untouched. No B0
seed, horizon, step limit or success predicate was reinterpreted.

## 2. Changes

### 2.1 Action space: 7-D delta → 10-D absolute

| | Old protocol text | Amended protocol |
|---|---|---|
| Policy output | 7-D OSC pose delta + gripper | **10-D absolute**: 3-D position + 6-D rotation + 1-D gripper |
| Environment input | 7-D OSC_POSE delta | **7-D OSC_POSE absolute**: 3 position + 3 axis-angle + 1 gripper |
| Controller | `control_delta=true` (implicit in delta text) | **`control_delta=false`** |
| Conversion | none | `rotation_6d → rotation matrix → axis-angle` in `src/gate_b_v2/actions.py`; same convention as DP/pytorch3d |

The actual checkpoint payload declares `shape_meta.action.shape=[10]`,
`abs_action=true`, `rotation_rep=rotation_6d` and the `image_abs.hdf5` dataset.
B0, B1 and B2 must use the same checkpoint and the same conversion; no
retraining and no checkpoint replacement. This experiment is **not** described
as a 7-D delta-action experiment.

### 2.2 Horizon: `[1,2,4,8,16]` → `[1,2,4,8,15]`

- Prediction horizon `H=16` is fixed by the checkpoint and is unchanged.
- `To=2`, so executable future actions = `16 − (2−1) = 15`.
- Execution horizon `h` is the number of predicted actions actually executed
  before re-observing/re-predicting.
- `h=16` remains forbidden. `core.validate_horizons` still raises instead of
  truncating, padding or repeating actions.
- The B2 branch horizon list was updated to `{1,2,4,8,15}` in the protocol.

### 2.3 B1 seed independence

| | Value |
|---|---|
| B0 seeds (historical) | 100000–100099, unchanged |
| B1 Pilot seeds | **200000–200019** |
| B1 Full seeds | **200020–200119** |
| B1 distinct initial states | 120 |
| Policy seed | 700000 + environment seed |

`runner.run_b1` reads `evaluation.b1_pilot_seed_start` and
`evaluation.b1_full_seed_start`, and validates the **complete intervals** of
B0, Pilot and Full with `core.validate_seed_ranges` before the first episode.
Any overlap raises `RuntimeError`; comparing only the start values is not
sufficient. Every episode row records `b1_phase`, `b1_seed_start` and
`b1_seed_end`; `b1_{phase}_run.json` records the actual range and all three
ranges.

### 2.4 Pilot and Full separation

| | Pilot | Full |
|---|---|---|
| Initial states | 20 | 100 |
| Horizons | 5 | 5 |
| Episodes | 100 | 500 |
| Seed range | 200000–200019 | 200020–200119 |
| Record file | `b1_pilot_episodes.jsonl` | `b1_full_episodes.jsonl` |
| Manifest | `b1_pilot_run.json` | `b1_full_run.json` |
| Analysis file | `b1_pilot_analysis.json` | `b1_full_analysis.json` |

Full uses 100 **new** initial states and never reuses a Pilot state. Pilot is
used only for execution/environment feasibility, pairing and record
completeness; it must not select horizons or tune thresholds. If any model,
action or horizon parameter changes after Pilot, a new independent Full
dataset must be created. Pilot and Full statistics are never pooled.

### 2.4.1 Formal completeness gate

Formal B1 analysis refuses to produce statistics unless:

- Pilot has exactly 20 seeds × 5 horizons = 100 records;
- Full has exactly 100 seeds × 5 horizons = 500 records;
- the JSONL seed set exactly equals the phase's declared interval;
- no duplicate `(seed, horizon)` or missing horizon exists;
- the Manifest exists and its phase, horizons, episode count, seed start/end
  and record filename match both the protocol and the JSONL;
- every row has the expected `b1_phase`;
- all five rows of a seed share the same initial-state SHA256 and
  `paired_initial_state_verified=true`.

If both Pilot and Full records exist in one directory, `--b1-phase` must be
given explicitly; the analyzer no longer silently prefers Pilot. The formal
counts are locked by config: the B1 CLI has no `--episodes` override.

### 2.4.2 B1/B2 isolation

`b1` no longer exposes `--collect-b2-states`, and `GateBExperiment.run_b1` has
no state-collection parameter. B1 does not save B2 snapshots or state
manifests. The independent B2 runner and snapshot implementation remain in the
codebase but B2 is unstarted and requires its own authorization, frozen
stage window and snapshot/restore validation.

### 2.4.3 Formal runtime environment lock

`locks.py` pins the B0-verified environment and the pre-registered B1
parameters:

| Item | Locked value |
|---|---|
| Checkpoint SHA256 | `adaf17854fb8ff8acaccc56adbf6af321c7bec7fecb22de5257772ec81927c6d` |
| Dataset SHA256 | `7e58906366d79996f13785ff2dd0fe346230373532addc2afc7c92611ae42887` |
| DP source tree SHA256 | `aec43e20abb0902b606e61fc4a391605ab755e59233ecb5f6bdbfbe8df372f21` |
| Max steps | 500 |
| Prediction horizon / To | 16 / 2 |
| Execution horizons | `[1,2,4,8,15]` |
| GPU / CUDA / torch | RTX 3090 / 11.6 / 1.12.1+cu116 |
| Device | `cuda:0` |
| robomimic / robosuite / mujoco_py | 0.2.0 / 1.2.0 / 2.0.2.13 |
| Policy seed offset | 700000 |
| Config fingerprint | canonical critical-parameter SHA256 |

The B1 CLI exposes only `--b1-phase` and `--run-dir`; it has no
`--checkpoint`, `--dataset`, `--dp-root`, `--max-steps` or `--config`.
`_cmd_b1` loads only the fixed project config, and `run_b1()` re-validates all
critical config values and the **actual** runtime manifest (file hashes,
versions, GPU, device, steps, horizons, seed range) before writing the run
manifest or any episode. Every episode row carries the environment fields;
`analyze_b1()` rejects a manifest or row that does not match the lock.

### 2.5 Statistical analysis (pre-registered)

- Unit: initial-state seed; five horizons are paired conditions.
- Per-horizon success count/rate and Wilson 95 % interval.
- Overall five-level test: Cochran's Q; paired cluster bootstrap by seed.
- Reference: **h=8 only**.
- Risk differences for h=1, 2, 4, 15 vs h=8, with paired cluster-bootstrap
  95 % CI and exact McNemar p-values.
- Holm step-down correction over the four comparisons.
- Pre-registered practical threshold: **8 percentage points**.
- Ceiling: all horizon rates ≥0.95; floor: all rates ≤0.05.
- No “highest observed rate wins” claim; all horizons and uncertainties are
  reported. The 500 episodes are never treated as independent samples.

### 2.6 Stage boundaries

- **B0**: platform, checkpoint, action interface and basic execution.
- **B1**: effect of fixed execution horizon on success and execution cost.
- **B2**: whether local geometric clearance moderates horizon effects on the
  same physical state.
- B1 does not prove CAC, does not train an error model and must not start B2
  branch collection. B0 passing does not imply Gate B passing.

## 3. Files changed in this round

| File | Change |
|---|---|
| `research_spatial_action_round4_20261109/reports/GATE_B_PROTOCOL.md` | Formal protocol amendment: action space, H vs h, h=15, B1 seeds, Pilot/Full, statistics, stage boundaries, current status |
| `gate_b_v2/configs/gate_b.yaml` | `horizons: [1,2,4,8,15]`; split `b1_pilot_seed_start: 200000` / `b1_full_seed_start: 200020`; reference/alpha/practical/ceiling/floor settings |
| `gate_b_v2/src/gate_b_v2/core.py` | `B1_PHASES`, record/manifest filenames, no-overwrite guard, complete-interval `validate_seed_ranges` |
| `gate_b_v2/src/gate_b_v2/runner.py` | Phase-specific seed start, full-interval overlap check, locked counts, separate records/manifests, no B2 collection; runtime manifest and per-row environment fields validated against `locks.py` |
| `gate_b_v2/src/gate_b_v2/cli.py` | B1 parser only `--b1-phase`/`--run-dir`; fixed config; no checkpoint/dataset/dp-root/max-steps/config overrides |
| `gate_b_v2/src/gate_b_v2/locks.py` | B0-derived checkpoint/dataset/DP-tree/GPU/version/steps/horizon/config-fingerprint lock and validators |
| `gate_b_v2/src/gate_b_v2/analysis.py` | Wilson CI, Cochran's Q, exact McNemar, Holm, ceiling/floor; strict seed/count/manifest/phase/pairing completeness gate; environment-fingerprint gate on manifest and every record; explicit phase when both exist |
| `gate_b_v2/scripts/run_b1_pilot.sh`, `run_b1_full.sh` | Explicit phase; no B2 collection; no custom count |
| `gate_b_v2/scripts/analyze.sh` | Passes extra analyze arguments through |
| `gate_b_v2/tests/test_b1_protocol.py`, `test_b1_analysis.py` | Seed-overlap, completeness, manifest, phase, B2-isolation and statistics tests |
| `gate_b_v2/README.md`, `reports/IMPLEMENTATION_STATUS.md` | Updated B1 status, seed ranges and boundaries |
| `reports/B1_READINESS_REPORT.md` | Readiness checklist and remaining approvals |
| `reports/B1_SECOND_REVISION_REPORT.md` | Second-revision engineering report and final status |
| `reports/WORKSTATION_EXECUTION_LOG.md` | Static-work log entry |

No B0 data file, checkpoint, environment, cache or unrelated experiment was
modified.

## 4. Code/protocol consistency

| Requirement | Implementation | Verified |
|---|---|---|
| h=15 accepted | `validate_horizons(...,16,2)` returns 15 | unit test |
| h=16 rejected | `validate_horizons` raises; no silent truncation | unit test |
| B1 seeds independent | B0 100000–100099, Pilot 200000–200019, Full 200020–200119; complete-interval overlap check | config + unit tests |
| Pilot/Full separate | distinct record and manifest filenames; no-overwrite guard | unit tests |
| Counts locked | no `--episodes` on B1; Pilot 20×5, Full 100×5 | parser + signature tests |
| Completeness gate | exact seed set, count, horizons, manifest, phase and pairing required | synthetic-data tests |
| Environment lock | checkpoint/dataset/DP-tree SHA256, 500 steps, H16/To2, RTX 3090, torch 1.12.1+cu116, CUDA 11.6, `cuda:0`, policy offset 700000 | unit tests + real local hash check |
| CLI lock | B1 accepts only `--b1-phase` and `--run-dir`; no path/config/max-steps override | parser tests |
| Manifest and row fingerprint | actual runtime fingerprint written to `b1_{phase}_run.json` and every episode row | unit tests |
| Analysis lock | rejects wrong hashes, steps, horizons, offset, versions or config fingerprint | synthetic manifest tests |
| Ambiguous phase | both Pilot and Full present requires explicit `--b1-phase` | unit test |
| Pairing verified | same `initial_state_sha256` and verified flag across five h | runner + analysis tests |
| Policy seed recorded | `policy_seed = 700000 + seed` in each row | existing B0/runs + code review |
| Final-state success | `is_success()["task"]` on final state; sticky flag diagnostic only | existing implementation/test |
| Raw JSONL preserved | append-only; refuses existing non-empty file | unit test |
| Statistics | Cochran Q, cluster bootstrap, exact McNemar, Holm, Wilson, ceiling/floor | synthetic-data tests |
| B2 not started | no B1 collection parameter or CLI flag; B2 runner preserved but unstarted | parser/signature tests |

## 5. Static verification performed

```text
pytest -q                        114 passed
python -m compileall -q src tests  clean
config horizons                  [1, 2, 4, 8, 15]
seed intervals                   B0 100000–100099; Pilot 200000–200019; Full 200020–200119
overlap check                    passed for config; shift/overlap tests rejected
available future actions         15
validate_horizons([...15])       accepted
validate_horizons([...16])       rejected
Pilot 20×5 / Full 100×5          completeness gate tests pass
Manifest/phase/pairing gate      failure tests pass
B0 evidence SHA256 vs 09e9ca6    12/12 match
grep old horizon list            no occurrences in active code/config/docs
bash -n scripts/*.sh             clean
```

No simulator, GPU, B1 Pilot/Full, B2, or training command was executed.

## 6. Open items for the research lead

1. Accept or revise the pre-registered B1 thresholds: alpha 0.05, practical
   difference 8 pp, Holm family of four comparisons, ceiling 0.95 / floor 0.05.
2. Confirm the disjoint seed design: Pilot 200000–200019 and Full
   200020–200119 (120 distinct states), with Full never reusing Pilot data.
3. Authorize B1 Pilot execution separately; this round deliberately did not
   start it.
4. B2 still requires a frozen insertion-stage window and deterministic
   snapshot/restore replay; neither is part of this round.

**Final status: CODE_REVISION_COMPLETE — awaiting independent review and B1
Pilot authorization. See `B1_SECOND_REVISION_REPORT.md`.**
