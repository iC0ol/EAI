# Gate B v2 — Square-MH experiment harness

The source package is uploaded atomically as the repository-root archive `gate_b_v2_source.tar.xz`.
From the repository root, unpack it with:

```bash
tar -xJf gate_b_v2_source.tar.xz -C .
cd gate_b_v2
```

Archive SHA256: `e4e392c94f33fa813872f7a8a89c07f6f1e0d4d9df0d4bdaeaa0d1ab87730c1b`.
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
| Bootstrap | 5,000 state-cluster resamples |

The B2 runner reads the real accepted B1 Full manifest (`reports/b1_full_run.json`) and verifies
the complete checkpoint/dataset/DP-tree/runtime fingerprint. It fails closed on any mismatch.
The B2 CLI exposes only `--run-dir` and `--split` (plus PREFLIGHT-only arguments for the
`b2-preflight` command); it exposes no checkpoint, dataset, DP-root, max-steps, device or config
override.

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

Each snapshot stores the MuJoCo state and model XML, robosuite counters and task state, controller
and gripper fields (with an explicit capture audit), the `To=2` observation history, the
environment/NumPy/Python/PyTorch CPU/CUDA RNG states, and episode diagnostics. Controller/gripper
fields that cannot be serialized are classified; an unknown mutable field is a hard error rather
than a silent omission.

Every selected snapshot is validated, not only the first:

- simulator state max absolute error ≤ `1e-7`;
- observation mean absolute error ≤ `1e-3`;
- geometry absolute error ≤ `1e-6 m`;
- two restores followed by the same fixed probe action are deterministic;
- the snapshot SHA256 is checked before every branch.

If any selected snapshot fails, the split is BLOCKED and the state is not replaced.

## Commands

PREFLIGHT only (this implementation round):

```bash
python -m gate_b_v2.cli b2-geometry-audit --run-dir runs/b2_geometry_audit
python -m gate_b_v2.cli b2-preflight --run-dir runs/b2_preflight --seed 299999
```

Formal B2 commands (not authorized in this round):

```bash
# One split at a time; these are separate commands by protocol design.
python -m gate_b_v2.cli b2-harvest --split discovery --run-dir runs/b2_discovery
python -m gate_b_v2.cli b2 --split discovery --run-dir runs/b2_discovery

python -m gate_b_v2.cli b2-harvest --split confirmation --run-dir runs/b2_confirmation
python -m gate_b_v2.cli b2 --split confirmation --run-dir runs/b2_confirmation

python -m gate_b_v2.cli analyze --run-dir runs/b2_discovery
python -m gate_b_v2.cli analyze --run-dir runs/b2_confirmation
```

Discovery and confirmation use separate seed pools, state manifests, snapshot directories and
branch-result files. A single command never starts both splits.

## Current status

- B0: completed at 84/100 (`reports/B0_REPORT.md`).
- B1 Pilot: completed (`reports/B1_PILOT_REPORT.md`).
- B1 Full: completed and independently reviewed; 399/500 (`reports/B1_FULL_REPORT.md`).
- B2 protocol: frozen v1.1.
- B2 code: implemented, unit-tested, live geometry audit PASS, and seed-299999 snapshot/replay
  PREFLIGHT PASS. Awaiting independent code acceptance.
- B2 discovery/confirmation states: **not collected**.
- B2 branch episodes: **not run**.
- Training/fine-tuning: **none**.
- Gate C: not authorized.

The complete acceptance evidence is in `reports/B2_IMPLEMENTATION_ACCEPTANCE_REPORT.md`. No B2
scientific result exists yet; protocol completion and code acceptance are not experiment
completion.
