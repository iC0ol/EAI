# Gate B v2 — Square-MH experiment harness

The source package is uploaded atomically as the repository-root archive `gate_b_v2_source.tar.xz`.
From the repository root, unpack it with:

```bash
tar -xJf gate_b_v2_source.tar.xz -C .
cd gate_b_v2
```

Archive SHA256: `909086eedbdc9f71ca0e6bf232ae00d8011d8c0f1dff882eb0b41d566e9f1f0e`.
(The packaged copy inside the archive omits this value because embedding the archive's own hash
would change the archive hash.)

Then read `reports/IMPLEMENTATION_STATUS.md`, `configs/gate_b.yaml`, and this directory's
`AGENTS.md`. The code is an evaluation harness only: it does not train CAC or modify the official
checkpoint. Run `python -m pytest -q` before simulator work.

## Frozen research and protocol boundaries

B2 follows `research_spatial_action_round4_20261109/reports/B2_PROTOCOL_REVISION_20261116.md`
(B2 v1.1). The earlier B2 design in sections 6–9 of `GATE_B_PROTOCOL.md` is superseded. This
repository does **not** re-open the research question, change the frozen stage gate, or modify
B0/B1 data.

Locked B2 values:

| Item | Value |
|---|---|
| Source rollout horizon | `h_source=8` |
| Branch horizons | `[1, 2, 4, 8, 15]` |
| Continuation horizon | `h_continue=15` |
| Repeats per state × horizon | 3 |
| States per split | 30 |
| Branch episodes per split | 450 (`30 × 5 × 3`) |
| Discovery seeds | 300000–300099, extension 300100–300199 |
| Confirmation seeds | 310000–310099, extension 310100–310199 |
| Discovery selection seed | 20261116 |
| Confirmation selection seed | 20261117 |
| Primary contrast | `Delta_s = 0.5*(p_s(1)+p_s(2)) - p_s(15)` |
| Primary effect | `E = predicted_Delta(c_10) - predicted_Delta(c_90)` |
| Practical threshold | `E >= 0.08` |
| Confidence intervals | 5,000 state-cluster bootstrap resamples |
| Hypothesis tests | 100,000 state-level permutation draws |

The B2 runner reads the real accepted B1 Full manifest (`reports/b1_full_run.json`) and verifies
the complete checkpoint/dataset/DP-tree/runtime/config fingerprint against the frozen B0/B1 lock.
It fails closed on any mismatch. The B2 CLI exposes only `--run-dir` and `--split` (plus
PREFLIGHT-only arguments for the `b2-preflight` command); it exposes no checkpoint, dataset,
DP-root, max-steps, device or config override.

## Formal authorization gates

Formal discovery/confirmation harvesting and branch execution are blocked unless the **same run
directory** contains a passing PREFLIGHT and the researcher has created the relevant authorization
file. Code never creates these files.

Discovery requires all of:

- `b2_preflight_summary.json` with `marker=PREFLIGHT`, `scientific_data=false`, `status=PASS`,
  seed `299999`, `gate_reached=true`, `fallback_used=false`, and
  `snapshot_validation_all_passed=true`;
- `b2_geometry_audit.json` with `status=PASS`;
- matching preflight environment and source-tree fingerprints;
- `B2_DISCOVERY_AUTHORIZATION.json` with `approved=true`, `protocol_version`,
  `implementation_commit`, `preflight_summary_sha256`, `authorized_by`, `authorized_at`, and
  `authorized_scope` containing `discovery`.

Confirmation additionally requires `B2_CONFIRMATION_AUTHORIZATION.json`, which must reference the
completed discovery run and the SHA256 of `b2_discovery_analysis.json`. Discovery must have a
complete 450-row dataset, passing snapshot validation, an existing `B2_REPORT.md`, and a decision
that is not STOP/BLOCKED.

Preflight seed is frozen at `299999`; any other seed is rejected before simulation. A fallback
snapshot taken without reaching the stage gate is diagnostic only and can never produce PASS.

The PREFLIGHT summary locks the implementation source-tree fingerprint and the SHA256 of the
geometry audit and snapshot validation. The gate resolves the authorization JSON and its matching
PREFLIGHT from the workstation run directory.

## Collision geometry and stage gate

The geometry module uses live MuJoCo collision geoms only. The four SquareNut aperture bars are
identified as two mirror-paired collision boxes; the handle box is excluded because it has no
mirror partner. The peg collision box is identified on `peg1`. All quantities are expressed in
the nut body frame:

- `c_xy = min(hole_half_x - max(peg_x), hole_half_x + min(peg_x), hole_half_y - max(peg_y), hole_half_y + min(peg_y))`
- `z_gap = nut_bottom_local_z - peg_top_local_z`
- `t_nut_m = max(local_z of four aperture bars) - min(local_z of four aperture bars)`
- `r_hole = hypot(hole_half_x, hole_half_y)`, `r_peg = hypot(peg_half_x, peg_half_y)`, `d_xy = hypot(dx, dy)`

A source state is eligible at the first control step satisfying all of:

```text
0 < z_gap_m <= t_nut_m
d_xy_m <= r_hole_m + r_peg_m
z_gap_current < z_gap_previous
```

There are no hand-tuned numeric `z_gap_min_m`, `z_gap_max_m` or `max_xy_center_distance_m`
thresholds in the B2 config. The live audit is written to `b2_geometry_audit.json` and must pass
before any B2 state collection.

## Snapshot / restore

B2 schema 3 stores two reads of the live source at the first eligible control step. The restore
payload includes the MuJoCo state, XML, integration inputs, observable sampling state,
controller/gripper fields, `To=2` history and environment/global RNG states. The separate
validation reference captures source values and hashes before any restore, including a forced
RGB and low-dimensional observation. Schema 1 and 2 snapshots remain readable by the legacy
restore API. Formal B2 validation requires schema 3.

MuJoCo's Euler step computes the camera and collision transforms before integrating `qpos`.
Schema 3 retains the pose used for those transforms, recomputes them on restore and reapplies the
integration endpoint. The validator independently compares the source and restored simulator
state (max absolute error ≤ `1e-7`), model XML and controller/gripper fields. It checks both the
restored observation history and a fresh read of each sensor (MAE ≤ `1e-3`). Geometry uses
`1e-6 m` for lengths and `1e-6 rad` for wrapped relative yaw. Two independent restores with the
same probe action also have to agree. Every selected state must pass before branches start, and
the runner checks the snapshot file SHA256 before each branch.

The branch command refuses an existing formal output, including empty files, before writing
results or starting rollouts. It reads the completed Harvest and PREFLIGHT from the run directory.
Invalid execution or a failed snapshot validation sets the Split status to `BLOCKED`. A row
enters the episodes file only after it passes validation, and analysis requires a `COMPLETE`
Split with exactly 450 validated records.

## Commands

PREFLIGHT entry points for reserved-seed engineering checks:

```bash
python -m gate_b_v2.cli b2-geometry-audit --run-dir runs/b2_geometry_audit
python -m gate_b_v2.cli b2-preflight --run-dir runs/b2_preflight --seed 299999
python -m gate_b_v2.cli b2-export-preflight-evidence \
  --run-dir runs/b2_preflight --output-dir reports/preflight_third_revision
```

The exported evidence contains only small JSON records marked `PREFLIGHT` and
`scientific_data=false`; it never contains snapshot binaries, checkpoints, datasets or environments.

Formal B2 entry points for individually authorized runs:

```bash
# One split at a time; these are separate commands by protocol design.
python -m gate_b_v2.cli b2-harvest --split discovery --run-dir runs/b2_discovery
python -m gate_b_v2.cli b2 --split discovery --run-dir runs/b2_discovery

python -m gate_b_v2.cli b2-harvest --split confirmation --run-dir runs/b2_confirmation
python -m gate_b_v2.cli b2 --split confirmation --run-dir runs/b2_confirmation

python -m gate_b_v2.cli analyze --run-dir runs/b2_discovery
python -m gate_b_v2.cli analyze --run-dir runs/b2_confirmation
```

Discovery and Confirmation use separate seed pools, state manifests, snapshot directories and
branch-result files. For Confirmation, review the cross-directory inventory check and execution
sequence in the [execution plan](reports/B2_CONFIRMATION_EXECUTION_PLAN.md).

## Current status (2026-11-18)

- B0: completed at 84/100 (`reports/B0_REPORT.md`).
- B1 Pilot: completed (`reports/B1_PILOT_REPORT.md`).
- B1 Full: completed and independently reviewed; 399/500 (`reports/B1_FULL_REPORT.md`).
- B2 protocol: frozen v1.1.
- B2 Discovery: **COMPLETED**. All 30 selected snapshots passed independent validation and all
  450 Branch records passed the integrity gate. The decision is
  `DISCOVERY_UNCERTAIN_CONFIRMATION_JUSTIFIED`. [Results and scientific limits](reports/b2_discovery_20261117/B2_DISCOVERY_CLOSEOUT.md)
- Discovery documentation and Confirmation preparation: **COMPLETED**. Discovery met the
  preregistered continuation condition. [Pending authorization template](reports/B2_CONFIRMATION_AUTHORIZATION.md)
- Confirmation authorization: **NOT AUTHORIZED**. Confirmation Harvest and Branch: **NOT STARTED**.
- Gate C: **NOT AUTHORIZED**.

The third revision's public PREFLIGHT evidence is in `reports/preflight_third_revision/`.
See the [independent Snapshot report](reports/B2_SNAPSHOT_INDEPENDENT_VALIDATION_REPORT.md)
and the [third-revision report](reports/B2_THIRD_REVISION_REPORT.md).
