# B2 Protocol Amendment v1.1 — CAC matched-state intervention

- Date: 2026-11-16
- Repository: `iC0ol/EAI`
- Base protocol: `research_spatial_action_round4_20261109/reports/GATE_B_PROTOCOL.md`
- Status: **PROTOCOL FROZEN FOR IMPLEMENTATION; B2 CODE NOT YET ACCEPTED; NO B2 DATA COLLECTION OR BRANCH EXPERIMENT IS AUTHORIZED.**
- This amendment supersedes the earlier B2 design in sections 6–9 of `GATE_B_PROTOCOL.md` wherever they conflict. B0/B1 definitions, records, manifests, and conclusions remain unchanged.

---

## 1. Purpose and research question

B1 Full established that fixed execution horizon matters on Square-MH:

- `h ∈ {1,2,4,8,15}`
- Success rates: 0.66, 0.72, 0.81, 0.87, 0.93.
- The overall paired horizon effect was significant.
- `h=1` and `h=2` were significantly below `h=8` after Holm correction.
- `h=15` had the highest observed success rate and lowest policy-call count, but was **not statistically significantly better than h=8**. It is therefore the strongest observed fixed-horizon comparator, not a proven statistically superior horizon.

B2 asks a narrower, causal question:

> At the same reachable pre-insertion physical state, does signed task-space geometric clearance predict when a short first action commitment (h=1 or 2) is better or worse than the strongest observed fixed baseline (h=15)?

B2 is a **one-commitment counterfactual intervention**, not a complete online CAC evaluation. Each branch changes only the first commitment length; all subsequent commitments use `h=15`. This makes the `h=15` branch the fixed-h=15 continuation baseline from the branch state.

B2 does not train CAC, change the policy weights, modify the checkpoint, or establish a deployment-time visual clearance estimator.

## 2. Locked assets and invariant experiment settings

The following must remain identical to the B0/B1-verified setup:

| Item | Locked value |
|---|---|
| Task | robomimic Square-MH, image Diffusion Policy CNN |
| Checkpoint | B0/B1-verified official EMA checkpoint; exact SHA256 from the B1 Full manifest |
| Dataset | B0/B1-verified dataset; exact SHA256 from the B1 Full manifest |
| Diffusion Policy source tree | B0/B1-verified source tree; exact SHA256 from the B1 Full manifest |
| Hardware | NVIDIA RTX 3090, single GPU |
| Device | `cuda:0` |
| Torch / CUDA | `1.12.1+cu116` / CUDA 11.6 |
| Prediction horizon | `H=16` |
| Observation steps | `To=2` |
| Available future actions | `H-(To-1)=15` |
| Max episode steps | 500 |
| Execution horizons | `h ∈ {1,2,4,8,15}` |
| Source rollout horizon | `h_source=8` |
| Branch continuation horizon | `h_continue=15` |
| Repeats | 3 policy-sampling repeats per state × horizon |
| Success | Final robomimic task predicate; never sticky `success_seen` |

The B2 runner must read and verify the exact asset fingerprints and runtime lock from the B1 Full manifest. B2 must fail closed on any mismatch. The B2 CLI must not expose checkpoint, dataset, DP-root, max-step, device, or config overrides. Only the run directory and requested split may be supplied. Do not edit B0/B1 result files or reinterpret B1 data.

The horizon list is exact. `h=16` must be rejected; do not truncate, pad, or repeat actions.

## 3. Geometry definitions and pre-insertion stage gate

### 3.1 Signed projected clearance

Use the live MuJoCo **collision geometry**, not visual meshes, hand-entered nominal dimensions, or center-distance-only approximations.

Express the SquareNut aperture and Square peg collision geometry in the nut-local frame. Let the four aperture half-space gaps be:

```
g_x+ = hole_half_x - max(peg_xy[:, x])
g_x- = hole_half_x + min(peg_xy[:, x])
g_y+ = hole_half_y - max(peg_xy[:, y])
g_y- = hole_half_y + min(peg_xy[:, y])
c_xy = min(g_x+, g_x-, g_y+, g_y-)
```

- `c_xy > 0`: the peg's projected collision rectangle fits inside the aperture with positive margin.
- `c_xy = 0`: projected boundary contact.
- `c_xy < 0`: at least one projected aperture half-space is violated.

Record all four directional gaps, `dx_m`, `dy_m`, `relative_yaw_rad`, hole dimensions, peg dimensions, and `c_xy`. Do not collapse axial separation into `c_xy`.

### 3.2 Axial gap sign and frame

The current implementation computes `z_gap_m` in world z. B2 must audit and, if needed, correct this definition before using it.

The authoritative definition is the signed axial separation along the nut-local +z axis:

- Transform the four SquareNut aperture-bar collision boxes and the peg collision box into the nut-local frame.
- `nut_bottom_local_z` is the minimum local-z coordinate of the aperture-bar collision corners.
- `peg_top_local_z` is the maximum local-z coordinate of the peg collision corners.
- `z_gap_m = nut_bottom_local_z - peg_top_local_z`.

Interpretation: positive means the peg tip is still below and separated from the nut's lower aperture plane; zero is axial contact; negative means axial overlap. Record the local-frame convention and all source dimensions in the geometry audit. If the task model's geometry cannot support this interpretation, stop and report BLOCKED rather than silently retaining an ambiguous world-z quantity.

### 3.3 Geometry-derived stage gate (frozen; no hand-tuned thresholds)

Define the pre-contact approach envelope from the actual collision geometry:

- `t_nut_m`: full thickness of the SquareNut aperture frame along nut-local z, measured as the max-minus-min local-z extent of its four aperture-bar collision boxes. Validate that the four bars are consistent; fail closed if not.
- `r_hole = sqrt(hole_half_x² + hole_half_y²)`: aperture circumscribed radius.
- `r_peg = sqrt(peg_half_x² + peg_half_y²)`: peg cross-section circumscribed radius.
- `d_xy = sqrt(dx_m² + dy_m²)`.

A source state is eligible at the first time step satisfying all of:

```
0 < z_gap_m <= t_nut_m
d_xy <= r_hole + r_peg
z_gap_current < z_gap_previous
```

The final condition requires the nut to be approaching the peg, not retreating. This gate defines a broad pre-contact envelope in which the projected peg and aperture may geometrically interact; it is **not** a success label and does not require `c_xy` to be positive. Negative and positive clearances must both remain eligible.

This geometry-derived rule replaces the previous un-frozen numeric `z_gap_min_m`, `z_gap_max_m`, and `max_xy_center_distance_m` values. Store the actual derived values and collision-geometry fingerprints in the run manifest. Do not tune the gate after inspecting branch outcomes.

### 3.4 Live geometry audit is a hard preflight gate

Before collecting any B2 state, produce `b2_geometry_audit.json` containing:

1. MuJoCo model/version and environment metadata.
2. Nut and peg body IDs, collision geom IDs, geom types, collision masks, sizes, and transforms.
3. Confirmation that the aperture is inferred from exactly four live collision bars and that the peg collision geom is correctly identified.
4. Symmetry and dimension checks for the four aperture bars.
5. Local-frame axis convention and positive/zero/negative sign checks for both `c_xy` and `z_gap_m`.
6. Finite-value checks over reset and several real rollout states.
7. A video or compact diagnostic record showing the measured geometry on representative states.

The existing fake-environment unit tests are necessary but insufficient. The live MuJoCo audit must pass. If visual and collision geometry differ, use collision geometry and report the difference. Any ambiguous geom identification, frame convention, or sign test means B2 is BLOCKED.

## 4. State harvesting and split isolation

### 4.1 Source rollouts

Use fixed-`h=8` Square-MH source rollouts to obtain reachable pre-insertion states. This is a **state-distribution choice** retained from the earlier protocol; it is not the B2 comparator. The B2 branch comparator is `h=15`.

Evaluate the geometry gate after **every environment control step**, not only at policy-call boundaries, so the short pre-contact window is not skipped by an eight-step chunk. At the first eligible step:

1. Stop the source rollout immediately.
2. Capture the full episode snapshot.
3. Record the state and geometry metadata.
4. Do not continue the source episode and do not use its eventual success/reward to select the state.

At most one state may be selected from each source seed. State selection must never depend on branch outcomes, source reward, source success, or the observed clearance value beyond the frozen gate eligibility rule.

### 4.2 Fixed, disjoint seed pools

| Split | Primary source seeds | Pre-registered extension seeds |
|---|---:|---:|
| Discovery | 300000–300099 | 300100–300199 |
| Confirmation | 310000–310099 | 310100–310199 |

These ranges are disjoint from B0 (100000–100099), B1 Pilot (200000–200019), and B1 Full (200020–200119).

For each split:

- Source environment reset seed is the source seed itself.
- Source policy sampling seed is `900000 + source_seed`.
- Discovery candidate-selection seed is `20261116`; confirmation candidate-selection seed is `20261117`.
- These seeds are fixed protocol constants; do not draw them from wall-clock time or an unrecorded RNG.

1. Process the full primary 100-seed block.
2. If at least 30 eligible candidate states exist, select exactly 30 by a deterministic, split-specific pseudorandom sample from eligible states. Save the selection seed and the complete candidate list.
3. If fewer than 30 eligible states exist, process the pre-registered 100-seed extension block. If the combined pool still has fewer than 30, mark that split BLOCKED for insufficient stage coverage. Do not widen or retune the stage gate.
4. Never select or balance states by source success/failure, reward, clearance rank, or any branch outcome.

Discovery and confirmation must have separate seed pools, state manifests, snapshot directories, and branch-result files. No source seed, state ID, snapshot, or branch record may appear in both splits.

### 4.3 Required state manifest fields

At minimum:

- `state_id`, `split`, `source_seed`, `source_step`, `source_horizon=8`
- `stage_gate_version` and the actual geometry-derived gate values
- `clearance_m`, four directional clearances, `dx_m`, `dy_m`, `d_xy_m`, `relative_yaw_rad`, `z_gap_m`
- `t_nut_m`, `r_hole_m`, `r_peg_m`, hole and peg collision dimensions
- `snapshot_file`, `snapshot_sha256`, simulator-state hash, per-observation-key hash
- checkpoint/dataset/DP-source/runtime fingerprints
- snapshot schema version and controller/gripper capture audit

## 5. Snapshot/restore validation

Snapshot/restore is a hard scientific-validity gate, not merely a utility test.

The snapshot must preserve:

- MuJoCo simulator state and model XML;
- robosuite timestep, time, done flag, task-specific mutable state;
- robot controller and gripper state;
- observation history for all `To=2` frames;
- environment RNG, NumPy RNG, Python RNG, PyTorch CPU RNG, and CUDA RNG;
- episode step/reward/success diagnostics and last info.

The current snapshot helper silently skips fields that cannot be copied. The implementation must enumerate skipped controller/gripper fields and establish whether each is immutable/irrelevant. Any omitted mutable field that can affect subsequent actions or dynamics is a BLOCKER; do not silently accept a partial snapshot.

Validate **every selected snapshot**, not only the first snapshot in a split:

1. Capture pre-restore simulator state, policy observation, and geometry.
2. Restore the snapshot and compare state (max absolute error ≤ `1e-7`), each observation (mean absolute error ≤ `1e-3`), and geometry (absolute error ≤ `1e-6 m` for metric values).
3. Restore twice, execute the same fixed probe action from the same RNG state, and compare resulting simulator states and observations using the same tolerances.
4. Confirm snapshot SHA256 before every branch.
5. Restore the snapshot anew before every horizon × repeat branch.

If any selected snapshot fails, the split is BLOCKED. Do not drop the failed state and replace it after looking at branch outcomes. Fix the implementation, rerun the preflight, and recollect the entire affected split using the same pre-registered seed rule in a new run directory.

## 6. Matched-state branch experiment

For each of the 30 selected states in each split:

- Horizons: `{1,2,4,8,15}`.
- Repeats per state × horizon: 3.
- Total: 30 × 5 × 3 = **450 branch episodes per split**.
- At the branch point, restore the same snapshot and reset policy-local state.
- Predict the full `H=16` action chunk; execute only the first `h` future actions.
- Thereafter, use `h_continue=15` for the rest of the episode. Therefore the `h=15` branch is the fixed-h=15 baseline from that branch state; shorter branches differ only in their first commitment.
- Continue until environment termination or 500 total episode steps.
- Use the final task predicate for success.

### 6.1 Randomization and common random numbers

- Randomize horizon execution order within each state × repeat using `branch_order_seed = 20261118 + source_seed * 5 + repeat_index` and `numpy.random.default_rng(branch_order_seed).permutation([1,2,4,8,15])`. Record the seed and realized order. Do not always run h=1,2,4,8,15 in the same order; this reduces horizon confounding with GPU thermal drift and wall-clock order.
- For a given state and repeat index, use `repeat_seed = 1000000 + source_seed * 17 + repeat_index` as the common policy-noise seed schedule across all five horizons (matching policy-call indices). Subsequent trajectories are expected to diverge; do not claim identical full-trajectory randomness.
- Every branch must restore the same snapshot and reset the policy before execution.
- Record branch order, repeat seed, policy-noise seed schedule, and environment fingerprints.

### 6.2 Required branch record fields

At minimum:

- split, state_id, source_seed, source_step, horizon, continuation_horizon=15
- repeat_index, repeat_seed, randomized_order_index
- success, success_error, success_seen (diagnostic only), max_reward, steps
- policy_calls_after_branch, wall_time_s, termination
- all geometry values copied from the immutable state manifest
- snapshot SHA256 and runtime fingerprints

Do not append to an existing branch-results file. A rerun must use a new run directory; partial output must never be silently mixed with a new run.

## 7. Statistical analysis (pre-registered)

### 7.1 Statistical unit

The independent unit is the **matched physical state (`state_id`)**, not the 450 branch episodes. The three stochastic repeats are nested within each state × horizon. All bootstrap resampling must resample whole state IDs and preserve all horizons/repeats within a sampled state.

### 7.2 Primary hypothesis and contrast

For state `s` and horizon `h`, let:

```
p_s(h) = mean(success over the 3 repeats for state s and horizon h)
Delta_s = 0.5 * (p_s(1) + p_s(2)) - p_s(15)
```

Let `c_s = clearance_m` at the shared branch state.

Primary hypothesis: **as clearance becomes tighter (smaller `c_s`), the short-first-commitment advantage over h=15 increases**. Equivalently, the slope of `Delta_s` against `c_s` is expected to be negative.

Fit the pre-specified state-level linear contrast:

```
Delta_s = beta_0 + beta_1 * c_s + error_s
```

Use 5,000 state-cluster bootstrap resamples for the 95% CI. Report the slope per millimetre as well as per metre.

Define the practical interaction effect as:

```
E = predicted_Delta(c_10) - predicted_Delta(c_90)
```

where `c_10` and `c_90` are the 10th and 90th percentiles of clearance in the relevant split. Positive E means short commitments gain relative advantage in tighter states. The pre-registered practical-effect threshold is **E ≥ 0.08 (8 percentage points)**, carried forward from the B1 practical-difference scale and frozen before B2 outcomes.

### 7.3 Discovery and confirmation decision

- Discovery: 30 states, 450 branches. Report the primary effect, CI, data coverage, and all secondary metrics.
- Proceed to confirmation only if the discovery data pass all integrity gates and the 95% CI upper bound for E is **not below 0.08**. If the upper bound is below 0.08, stop CAC as lacking a plausible pre-registered practically meaningful interaction. If the interval still includes 0.08, the result is uncertain and the independent confirmation split is justified.
- Confirmation: 30 entirely new states, 450 branches. Do not change the stage gate, contrast, threshold, or model after seeing confirmation outcomes.
- Confirmation supports the B2 mechanism only if the point estimate of E is ≥0.08 and its 95% CI lower bound is >0. A 95% CI upper bound below 0.08 indicates no practically meaningful effect. Otherwise classify as inconclusive; do not promote to Gate C on the basis of discovery alone.

### 7.4 Secondary analyses

1. Per-horizon success rates and state-cluster bootstrap CIs.
2. Per-horizon success difference and clearance slope versus h=15 for h=1,2,4,8. Apply Holm correction to these four secondary comparisons.
3. Full categorical `h × clearance` interaction across all five horizons, with state-cluster bootstrap uncertainty.
4. Policy calls and wall-clock time per branch; wall-clock is secondary because the B1 run showed GPU thermal/power throttling.
5. Spearman correlation and descriptive clearance-bin plots as robustness/visualization only.

Do not use oracle-horizon labels, per-state winner counts, AUROC, or a post-hoc clearance threshold as the primary result. Ambiguous/tied states remain in the analysis. Do not treat non-significance as proof of no effect.

## 8. Implementation and acceptance checklist

DeepSeek must implement the frozen protocol, not redesign it.

Required code work:

1. Add a separate B2 state-harvesting command; the current code has a B2 branch runner but no complete state-collection CLI path.
2. Add geometry-derived stage-gate computation and live geometry audit; correct/verify the axial frame and sign.
3. Capture at most one snapshot per source episode at the first eligible control step.
4. Implement deterministic candidate selection and disjoint discovery/confirmation seed pools exactly as above.
5. Strengthen snapshot capture/restore and validate every selected snapshot.
6. Change B2 continuation to h=15 and use h=15 as the primary comparator.
7. Randomize branch order deterministically while retaining common policy-noise seeds across horizons within each state/repeat.
8. Add strict manifest/result completeness validation: exactly 30 states × 5 horizons × 3 repeats = 450 unique rows per split; reject missing, duplicate, extra, mixed-split, mismatched-snapshot, or mismatched-environment rows.
9. Implement the pre-registered primary state-level contrast, cluster bootstrap, secondary analyses, and a complete `B2_REPORT.md`.
10. Lock B2 assets/runtime to B1 Full; remove B2 CLI asset/config overrides.
11. Preserve all B0/B1 code behavior and historical artifacts. Add regression tests.
12. Rebuild `gate_b_v2_source.tar.xz`, update its SHA256 in the README/implementation metadata, and ensure the archive contains the exact source used by the workstation.

### Required tests

- Geometry sign and frame tests for positive/zero/negative `c_xy` and `z_gap`.
- Live geometry audit tests and fail-closed behavior for ambiguous collision geoms.
- Stage-gate boundary, first-entry, approach-direction, and one-state-per-source-episode tests.
- Seed-pool disjointness and deterministic selection tests.
- Snapshot round-trip tests for every relevant state component and controller/gripper capture audit.
- One-step deterministic replay test.
- Exact B2 30 × 5 × 3 completeness and duplicate/missing row rejection.
- Branch-order reproducibility and common-noise-seed tests.
- Primary contrast and state-cluster bootstrap tests.
- CLI tests proving B2 cannot override locked assets or runtime.
- Full existing test suite and source-archive audit.

## 9. Preflight versus experiment authorization

The implementation stage may run only:

- the full unit/regression test suite;
- a non-scientific live geometry audit;
- one reserved snapshot/replay preflight using seed **299999** (never included in discovery/confirmation);
- a small throwaway source-state smoke test if required to validate the first-entry capture path, with all artifacts clearly marked PREFLIGHT and excluded from B2 manifests/results.

The implementation stage must **not**:

- collect the 30 discovery states;
- run any B2 branch episodes;
- collect confirmation states;
- train or fine-tune any model;
- change the frozen stage gate, horizons, repeats, thresholds, or seed pools;
- claim B2 has started or passed.

After code, tests, live geometry audit, snapshot preflight, and source-archive audit are pushed, stop and wait for independent review. Only after explicit researcher authorization may the discovery split begin. Confirmation requires a separate review of discovery results and explicit authorization.

## 10. Current status

| Item | Status |
|---|---|
| B0 | COMPLETED |
| B1 Pilot | COMPLETED |
| B1 Full | COMPLETED and independently reviewed |
| B2 protocol | **FROZEN FOR IMPLEMENTATION — this v1.1 amendment** |
| B2 code | NOT ACCEPTED; DeepSeek implementation pending |
| B2 geometry audit | NOT RUN |
| B2 snapshot preflight | NOT RUN |
| B2 discovery/confirmation states | NOT COLLECTED |
| B2 branch experiment | NOT AUTHORIZED |
| Gate C | NOT AUTHORIZED |

**No B2 scientific result exists yet. Protocol completion is not experiment completion.**

## 11. Status update (2026-11-18)

| Item | Current status |
|---|---|
| B1 Full | **COMPLETED** |
| B2 Discovery | **COMPLETED** at 00:42:41 Asia/Shanghai |
| Discovery documentation and data readback | **COMPLETED** |
| Confirmation preparation | **COMPLETED**, pending independent review |
| Confirmation authorization | **NOT AUTHORIZED** |
| Confirmation Harvest | **NOT STARTED** |
| Confirmation Branch | **NOT STARTED** |
| Gate C | **NOT AUTHORIZED** |

Discovery contains 30 independently validated physical states and 450 protocol-valid branches. Raw-data readback reproduced `E = 0.055707`, 95% state-cluster CI `[−0.015805, 0.156406]` and permutation `p = 0.343857`. The result remains uncertain and satisfies §7.3's Discovery continuation condition. The decision is `DISCOVERY_UNCERTAIN_CONFIRMATION_JUSTIFIED`. The observed clearance coverage and other scientific limitations are documented in the Discovery report. The original sections above contain the frozen design and decision rules. [Discovery report](../../gate_b_v2/reports/b2_discovery_20261117/B2_REPORT.md) · [Confirmation authorization template](../../gate_b_v2/reports/B2_CONFIRMATION_AUTHORIZATION.md) · [Execution plan](../../gate_b_v2/reports/B2_CONFIRMATION_EXECUTION_PLAN.md)
