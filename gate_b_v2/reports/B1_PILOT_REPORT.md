# B1 Pilot report — fixed execution-horizon scan

Date: 2026-11-12, 12:01:10–18:24 (Asia/Shanghai).
Branch/commit at execution: `codex/gate-b-v2`, `83c3528ecdae336b9b82646bca55a03f7e8949c8`.
Run directory: `runs/gateb_20261112T040110Z/`.
Status: **PILOT COMPLETED — GO for a separate B1 Full request; awaiting
research-lead approval.**

## 1. Purpose

Measure whether a fixed Diffusion Policy checkpoint behaves differently when
the number of predicted actions executed before re-observation is varied,
under one locked checkpoint, environment and protocol.

This is a 20-state pilot. It checks engineering feasibility and produces a
preliminary paired estimate; it is not the final B1 result and cannot by itself
establish a statistically significant horizon effect.

## 2. Protocol

| Item | Value |
|---|---|
| Phase | B1 Pilot |
| Initial states | 20 |
| Seeds | 200000–200019 |
| Horizons | `[1, 2, 4, 8, 15]` |
| Episodes | 100 (20 × 5) |
| Max steps | 500 |
| Reference horizon | h=8 |
| Policy seed | 700000 + environment seed (900000–900019) |
| Device | `cuda:0` |
| Success | final-state robomimic `is_success()["task"]` |
| Action interface | checkpoint-native 10-D absolute → 7-D OSC_POSE, `control_delta=false` |
| H / To | 16 / 2 (15 executable future actions) |

The formal B1 lock validated the actual environment before the run manifest
was written. No B1 Full, B2, B0, simulator smoke or training was run.

## 3. Environment and assets

| Item | Value |
|---|---|
| GPU | NVIDIA GeForce RTX 3090, 24,576 MiB |
| Driver | 580.178.04 |
| PyTorch / CUDA | 1.12.1+cu116 / 11.6 |
| robomimic / robosuite | 0.2.0 / 1.2.0 |
| mujoco_py | 2.0.2.13 |
| Python | 3.9.13 |
| Renderer | OSMesa 23.2.1 |
| Checkpoint SHA256 | `adaf17854fb8ff8acaccc56adbf6af321c7bec7fecb22de5257772ec81927c6d` |
| Dataset SHA256 | `7e58906366d79996f13785ff2dd0fe346230373532addc2afc7c92611ae42887` |
| DP source tree SHA256 | `aec43e20abb0902b606e61fc4a391605ab755e59233ecb5f6bdbfbe8df372f21` |
| Critical config fingerprint | `b34de158b416d6cbcc84dfc6bd0a3eb826461f5a7a9d662d236c1b210cd1bcec` |
| Environment | `NutAssemblySquare` |

## 4. Completion and integrity

| Check | Result |
|---|---|
| Episodes completed | **100/100** |
| Seeds | 200000–200019, unique, no gaps |
| Horizons per seed | exactly `[1,2,4,8,15]` |
| Steps | all 500 |
| Policy calls per episode | exactly `{1:500, 2:250, 4:125, 8:63, 15:34}` |
| Duplicate `(seed, horizon)` | none |
| Initial-state pairing | 20 unique state hashes; all five horizons equal per seed |
| `paired_initial_state_verified` | true for all 100 rows |
| Environment fields vs manifest | match for all 100 rows |
| Policy seed formula | true for all rows |
| `success_error` | none |
| Sticky/final success difference | none |
| Terminations | all `max_steps` |
| NaN/Inf/CUDA/OOM errors | none |
| Completeness gate in analysis | passed (`completeness_verified=true`) |

Three run files were produced: `b1_pilot_run.json` (locked manifest),
`b1_pilot_episodes.jsonl` (100 rows), and `environment_manifest.json`.

## 5. Results by horizon

| h | Successes / N | Rate | Wilson 95% CI | Mean policy calls | Mean wall time |
|---:|---:|---:|---|---:|---:|
| 1 | 15/20 | 0.750 | [0.531, 0.888] | 500.00 | 501.36 s |
| 2 | 14/20 | 0.700 | [0.481, 0.855] | 250.00 | 279.19 s |
| 4 | 17/20 | 0.850 | [0.640, 0.948] | 125.00 | 167.41 s |
| 8 | 18/20 | 0.900 | [0.699, 0.972] | 63.00 | 112.74 s |
| 15 | 18/20 | 0.900 | [0.699, 0.972] | 34.00 | 87.88 s |

Failure seeds by horizon:

- h=1: 200002, 200003, 200008, 200011, 200019
- h=2: 200005, 200008, 200009, 200011, 200017, 200019
- h=4: 200005, 200017, 200019
- h=8: 200011, 200019
- h=15: 200005, 200017

All failures terminated at 500 steps with `success=false`, `max_reward=0.0`;
none had a success-predicate error or was removed.

## 6. Pre-registered paired analysis

**Overall Cochran's Q:** Q=6.6000, df=4, p=0.1586. The five horizons are not
significantly different at alpha 0.05 in this pilot.

**Paired risk differences vs h=8** (cluster bootstrap over initial-state
seeds, exact McNemar, Holm correction over four comparisons):

| h | Risk difference | Bootstrap 95% CI | Raw McNemar p | Holm-adjusted p | Practical (≥0.08) |
|---:|---:|---|---:|---:|---|
| 1 | -0.150 | [-0.300, 0.000] | 0.250 | 0.750 | yes |
| 2 | -0.200 | [-0.400, -0.050] | 0.125 | 0.500 | yes |
| 4 | -0.050 | [-0.250, 0.100] | 1.000 | 1.000 | no |
| 15 | 0.000 | [-0.200, 0.200] | 1.000 | 1.000 | no |

`max_abs_pairwise_rate_difference=0.20`, so the pre-registered practical-signal
flag is true; however, **no Holm-adjusted comparison is significant**, and the
overall Q test is not significant. The h=2 unadjusted bootstrap interval
excludes zero, but this does not survive the pre-registered multiplicity
correction; it must not be reported as a confirmed effect.

Ceiling effect: false. Floor effect: false. Rates span 0.70–0.90, so the task
is neither saturated nor uniformly failing.

## 7. Execution efficiency

| h | Total policy calls | Total wall time (h) |
|---:|---:|---:|
| 1 | 10,000 | 2.785 |
| 2 | 5,000 | 1.551 |
| 4 | 2,500 | 0.930 |
| 8 | 1,260 | 0.626 |
| 15 | 680 | 0.488 |

Policy calls scale approximately as `ceil(500/h)` per episode. In this pilot,
h=15 reached the same 18/20 success as h=8 while using 680 versus 1,260 total
policy calls and 0.49 versus 0.63 h of policy wall time. h=1 and h=2 used far
more calls and had lower success in this sample. These are descriptive Pilot
observations, not confirmed horizon effects.

Pilot totals: 100 episodes, 22,971 s (6.38 h) summed episode wall time;
wall-clock run 12:01–18:24 (6 h 23 min).

## 8. GPU and runtime monitoring

| Metric | Value |
|---|---|
| GPU utilization max / mean | 90.0 % / 68.01 % |
| GPU memory max / mean | 3,550 / 3,549.1 MiB |
| GPU temperature max / mean | 86 °C / 82 °C |
| Samples | 1,800 (10 s interval) |

No CUDA error, OOM, NaN/Inf action, renderer failure or unhandled exception
occurred. The process exited normally after writing all 100 records.

## 9. Anomalies

- No protocol, environment, manifest or pairing violation.
- No missing, duplicate or out-of-range record.
- All 18 failures are ordinary task failures at the 500-step limit and are
  retained in the raw JSONL.
- h=15 executed successfully on all 20 states, confirming that the amended
  maximum horizon is operational.

## 10. Answers to the research questions

### Q1: Was the Pilot completed successfully?

Yes. 100/100 records, complete seed/horizon coverage, paired initial states,
one consistent environment fingerprint, no unresolved errors.

### Q2: Do horizons show preliminary differences?

In this 20-state pilot: h=1 0.75, h=2 0.70, h=4 0.85, h=8 0.90, h=15 0.90.
The overall Cochran Q p=0.1586 and no Holm-adjusted comparison is significant.
h=1/h=2 are numerically lower than h=8 by 15/20 pp, and h=2's unadjusted
bootstrap CI excludes zero, but the pre-registered corrected analysis does not
confirm this. h=15 is numerically identical to h=8. These are preliminary and
do not establish superiority or inferiority.

### Q3: Did execution efficiency change?

Yes descriptively: policy calls fall from 500 (h=1) to 34 (h=15) per episode,
and mean wall time falls from 501 s to 88 s. The Pilot cannot separate this
efficiency change from the unconfirmed success-rate differences.

### Q4: Is B1 Full ready to be requested?

**GO for a separate Full request.** The pipeline is stable, h=15 runs, the
data are complete and the locked environment is consistent. The Full run must
use its own reserved states 200020–200119 and the same pre-registered analysis;
no parameter should be changed based on Pilot outcomes. This is not an
automatic authorization: the research lead must approve Full separately.

## 11. Limitations

- Only 20 initial states; confidence intervals are wide and the study is
  underpowered for the 8 pp practical threshold.
- The Pilot cannot establish statistical significance or select a best
  horizon; no horizon should be chosen from these results.
- The h=2 unadjusted interval and the practical-signal flag are descriptive
  and do not override the non-significant Q test and Holm correction.
- Full remains a separate experiment with disjoint seeds and its own analysis;
  Pilot data are not pooled with Full.
- This report does not train CAC, validate clearance, or start B2.

## 12. Evidence

- `reports/b1_pilot_run.json`
- `reports/b1_pilot_episodes.jsonl`
- `reports/b1_pilot_analysis.json`
- `reports/b1_pilot_ANALYSIS.md`
- `reports/b1_pilot_environment_manifest.json`
- `reports/b1_pilot_run.log.txt`
- `reports/gpu_monitor_b1_pilot_summary.json`
- raw run directory `runs/gateb_20261112T040110Z/` (Git-excluded)

**Decision: Pilot PASSED engineering and data-integrity checks; request
separate approval for B1 Full.**
