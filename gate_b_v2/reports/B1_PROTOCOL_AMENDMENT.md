# B1 protocol amendment (after B0 acceptance)

Date: 2026-11-11 (Asia/Shanghai).
Branch: `codex/gate-b-v2`.
Base commit: `09e9ca63b89349c3905a7dc2bca9fd8e2b99844b`.
Status: **PROTOCOL_REVISION_COMPLETE** — awaiting independent acceptance and
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
| B1 seeds | **200000–200099** |
| Pilot seeds | 200000–200019 |
| Full seeds | 200000–200099 |
| Policy seed | 700000 + environment seed |

`runner.run_b1` now reads `evaluation.b1_seed_start` and refuses to run if it
equals the B0 `evaluation.seed_start`. The runner records `b1_phase` and
`b1_seed_start` in every episode row and writes a pre-registration file
`b1_{phase}_run.json` before the first episode.

### 2.4 Pilot and Full separation

| | Pilot | Full |
|---|---|---|
| Initial states | 20 | 100 |
| Horizons | 5 | 5 |
| Episodes | 100 | 500 |
| Seed range | 200000–200019 | 200000–200099 |
| Record file | `b1_pilot_episodes.jsonl` | `b1_full_episodes.jsonl` |
| Analysis file | `b1_pilot_analysis.json` | `b1_full_analysis.json` |

The Full run repeats the Pilot seed range first and then extends by 80 states.
Pilot is used only for execution/environment feasibility, pairing and record
completeness; it must not select horizons or tune thresholds. If any model,
action or horizon parameter changes after Pilot, a new independent Full
dataset must be created. Pilot and Full statistics are never pooled.

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
| `gate_b_v2/configs/gate_b.yaml` | `horizons: [1,2,4,8,15]`; `b1_seed_start: 200000`; reference/alpha/practical/ceiling/floor settings |
| `gate_b_v2/src/gate_b_v2/core.py` | `B1_PHASES`, `b1_records_filename`, `ensure_new_records_path` |
| `gate_b_v2/src/gate_b_v2/runner.py` | B1 phase argument, independent B1 seed, separate records, pre-registration, no-overwrite guard, B1 fields |
| `gate_b_v2/src/gate_b_v2/cli.py` | `b1 --b1-phase {pilot,full}`; `analyze --b1-phase`; passes config statistics |
| `gate_b_v2/src/gate_b_v2/analysis.py` | Wilson CI, Cochran's Q, exact McNemar, Holm, ceiling/floor, separate Pilot/Full analysis output |
| `gate_b_v2/scripts/run_b1_pilot.sh`, `run_b1_full.sh` | Explicit phase; Full no longer auto-collects B2 states |
| `gate_b_v2/scripts/analyze.sh` | Passes extra analyze arguments through |
| `gate_b_v2/tests/test_b1_protocol.py`, `test_b1_analysis.py` | New protocol/horizon/seed/record/statistics tests |
| `gate_b_v2/README.md`, `reports/IMPLEMENTATION_STATUS.md` | Updated B1 status and boundaries |
| `reports/B1_READINESS_REPORT.md` | Readiness checklist and remaining approvals |
| `reports/WORKSTATION_EXECUTION_LOG.md` | Static-work log entry |

No B0 data file, checkpoint, environment, cache or unrelated experiment was
modified.

## 4. Code/protocol consistency

| Requirement | Implementation | Verified |
|---|---|---|
| h=15 accepted | `validate_horizons(...,16,2)` returns 15 | unit test |
| h=16 rejected | `validate_horizons` raises; no silent truncation | unit test |
| B1 seeds independent | `evaluation.b1_seed_start=200000`; runner rejects equality with B0 seed | config test + code review |
| Pilot/Full separate | distinct record filenames; `b1_{phase}_run.json`; no-overwrite guard | unit tests |
| Pairing verified | same `initial_state_sha256` required across five h | existing runner + analysis tests |
| Policy seed recorded | `policy_seed = 700000 + seed` in each row | existing B0/runs + code review |
| Final-state success | `is_success()["task"]` on final state; sticky flag diagnostic only | existing implementation/test |
| Raw JSONL preserved | append-only; refuses existing non-empty file | unit test |
| Statistics | Cochran Q, cluster bootstrap, exact McNemar, Holm, Wilson, ceiling/floor | synthetic-data tests |
| B2 not started | no B2 state collection in this round; Full script no longer auto-collects | code/script review |

## 5. Static verification performed

```text
pytest -q                        38 passed
python -m compileall -q src tests  clean
config horizons                  [1, 2, 4, 8, 15]
available future actions         15
validate_horizons([...15])       accepted
validate_horizons([...16])       rejected
B0 evidence SHA256 vs 09e9ca6    12/12 match
grep old horizon list            no occurrences in active code/config/docs
bash -n scripts/*.sh             clean
```

No simulator, GPU, B1 Pilot/Full, B2, or training command was executed.

## 6. Open items for the research lead

1. Accept or revise the pre-registered B1 thresholds: alpha 0.05, practical
   difference 8 pp, Holm family of four comparisons, ceiling 0.95 / floor 0.05.
2. Confirm that the first 20 Pilot states may be included in the Full run on
   the stated condition that Pilot is feasibility-only.
3. Authorize B1 Pilot execution separately; this round deliberately did not
   start it.
4. B2 still requires a frozen insertion-stage window and deterministic
   snapshot/restore replay; neither is part of this round.

**Final status: PROTOCOL_REVISION_COMPLETE. Awaiting independent acceptance and
B1 launch authorization.**
