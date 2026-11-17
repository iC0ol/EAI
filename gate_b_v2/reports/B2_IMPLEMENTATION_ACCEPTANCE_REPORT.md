# B2 v1.1 implementation acceptance report

Date: 2026-11-16 (Asia/Shanghai)
Repository: `iC0ol/EAI`
Branch: `codex/b2-protocol-20261116`
Protocol commit: `4e7fcd5f856a8fae4d0d7844569c4c2c17a1c957`
Protocol: `research_spatial_action_round4_20261109/reports/B2_PROTOCOL_REVISION_20261116.md`
Status: **B2 v1.1 FIRST IMPLEMENTATION + SECOND REVISION; LIVE GEOMETRY AUDIT
PASS; SEED-299999 SNAPSHOT PREFLIGHT PASS; NOT YET ACCEPTED BY THE SECOND
INDEPENDENT REVIEW. NO B2 DISCOVERY OR CONFIRMATION STATE WAS COLLECTED, NO
BRANCH EPISODE WAS RUN, AND NEITHER SPLIT IS AUTHORIZED.**

## 1. Scope and boundaries

This round implemented the frozen B2 v1.1 protocol only. It did not:

- collect the 30 discovery states;
- run any B2 branch episode;
- collect confirmation states;
- train or fine-tune the model;
- modify the frozen protocol, stage gate, horizons, repeats, seed pools or
  statistical threshold;
- modify B0/B1 result files or reinterpret B1 data;
- modify ROS 2, system Python/CUDA, drivers or other experiments.

All preflight artifacts are marked `PREFLIGHT` and `scientific_data=false`.

## 1.1 Second-revision fixes (2026-11-17)

The second revision addresses the independent-review findings without changing
the frozen research question, horizons, seed pools, `E` definition, 0.08
threshold, or B0/B1 history:

- added a fail-closed authorization module; formal discovery/confirmation
  harvesting and branch execution require the same run directory's PASS
  PREFLIGHT plus a researcher-created authorization JSON;
- confirmation additionally requires completed, integrity-checked discovery
  data, discovery analysis and `B2_REPORT.md`, a non-STOP decision, and the
  discovery analysis SHA256 in the confirmation authorization;
- fixed preflight seed handling (only `299999`) and made the fallback snapshot
  diagnostic-only; PASS requires the real stage gate;
- B2 analysis now always uses the fixed project config and requires a complete
  B2 run manifest with protocol/split/config/B1-manifest/runtime fingerprint
  checks;
- replaced invalid bootstrap p-values with 100,000-draw state-level permutation
  tests (paired sign-flip for horizon differences, clearance permutation for
  slopes), while retaining 5,000 state-cluster bootstrap confidence intervals;
- strengthened `load_b1_full_manifest()` by validating the accepted B1 Full
  manifest itself against the full B0/B1 environment lock;
- made policy reset failure a hard blocker;
- made interrupted harvest artifacts block reuse of a run directory;
- added public PREFLIGHT JSON evidence and a second-revision report.

The code is still awaiting the second independent review. No authorization file
was created by this work.

## 2. Modified and added files

Modified:

- `gate_b_v2/configs/gate_b.yaml`
- `gate_b_v2/src/gate_b_v2/geometry.py`
- `gate_b_v2/src/gate_b_v2/snapshot.py`
- `gate_b_v2/src/gate_b_v2/runner.py`
- `gate_b_v2/src/gate_b_v2/analysis.py`
- `gate_b_v2/src/gate_b_v2/cli.py`
- `gate_b_v2/src/gate_b_v2/locks.py`
- `gate_b_v2/src/gate_b_v2/policy.py`
- `gate_b_v2/src/gate_b_v2/env.py`
- `gate_b_v2/scripts/run_b2_discovery.sh`
- `gate_b_v2/scripts/run_b2_confirmation.sh`
- `gate_b_v2/README.md`
- `gate_b_v2/reports/IMPLEMENTATION_STATUS.md`
- `gate_b_v2/reports/WORKSTATION_EXECUTION_LOG.md`

Added:

- `gate_b_v2/src/gate_b_v2/b2_protocol.py`
- `gate_b_v2/src/gate_b_v2/authorization.py` (second revision)
- `gate_b_v2/src/gate_b_v2/evidence.py` (second revision)
- `gate_b_v2/src/gate_b_v2/harvest.py`
- `gate_b_v2/scripts/run_b2_geometry_audit.sh`
- `gate_b_v2/scripts/run_b2_harvest_discovery.sh`
- `gate_b_v2/scripts/run_b2_harvest_confirmation.sh`
- `gate_b_v2/scripts/run_b2_preflight.sh`
- `gate_b_v2/tests/test_b2_geometry.py`
- `gate_b_v2/tests/test_b2_snapshot.py`
- `gate_b_v2/tests/test_b2_protocol.py`
- `gate_b_v2/tests/test_b2_harvest.py`
- `gate_b_v2/tests/test_b2_branch.py`
- `gate_b_v2/tests/test_b2_analysis.py`
- `gate_b_v2/tests/test_b2_authorization.py` (second revision)
- `gate_b_v2/tests/test_b2_cli.py`
- `gate_b_v2/reports/preflight/b2_geometry_audit.json`
- `gate_b_v2/reports/preflight/b2_preflight_summary.json`
- `gate_b_v2/reports/preflight/b2_preflight_snapshot_validation.json`
- `gate_b_v2/reports/preflight/b2_preflight_environment.json`
- `gate_b_v2/reports/preflight/PREFLIGHT_EVIDENCE_MANIFEST.json`
- `gate_b_v2/reports/B2_IMPLEMENTATION_ACCEPTANCE_REPORT.md`
- `gate_b_v2/reports/B2_SECOND_REVISION_REPORT.md` (second revision)
- repository-root `gate_b_v2_source.tar.xz` (rebuilt)

No B0/B1 source behavior was intentionally changed. Existing B0/B1 tests remain
in the suite and pass.

## 3. Implementation content

### 3.1 Geometry and stage gate

- Uses live MuJoCo collision geometry, not visual meshes or center distance.
- Identifies exactly four SquareNut aperture bars as two mirror-paired collision
  boxes; the handle box is excluded because it has no mirror partner.
- Identifies the Square peg collision box on `peg1`; visual and collision sizes
  are recorded and compared.
- Expresses all quantities in the nut body frame.
- Implements the four directional signed gaps, `c_xy`, `dx_m`, `dy_m`,
  `d_xy_m`, `relative_yaw_rad`, nut-local `z_gap_m`, `t_nut_m`, `r_hole_m`,
  `r_peg_m`, hole/peg dimensions and a collision-geometry fingerprint.
- Implements the frozen gate:
  `0 < z_gap <= t_nut`, `d_xy <= r_hole + r_peg`, `z_gap_current < previous`.
- The old world-z quantity is retained only as `world_z_gap_naive_m` in the
  audit; it is not used by the gate.
- Ambiguous bar/peg identification, asymmetric bars or non-box geometry produce
  `BLOCKED` rather than an approximate clearance.

### 3.2 State harvesting

- New independent `b2-harvest --split {discovery,confirmation}` command.
- Fixed `h_source=8`; gate checked after every environment control step.
- First eligible step immediately stops the source rollout and captures one
  snapshot; no source reward, success, branch outcome or clearance rank is used.
- At most one state per source seed.
- Exact frozen seed blocks and selection seeds; full primary block is processed
  before the pre-registered extension block.
- Deterministic `numpy.random.default_rng(selection_seed).choice(...)` selection
  of exactly 30 states; the complete candidate list and realized selection are
  recorded.
- Discovery and confirmation have separate run directories, seed pools, state
  manifests, snapshot directories and result files.
- Insufficient coverage marks the split `BLOCKED`; the gate is not widened.

### 3.3 Snapshot / restore

- Snapshot schema v2 stores MuJoCo state and model XML, robosuite counters/task
  state, controller and gripper state, observation history, environment RNG and
  Python/NumPy/PyTorch CPU/CUDA RNG.
- Every controller/gripper field is either captured or explicitly classified.
  The live audit shows only `sim` (object reference) and immutable XML metadata
  are skipped; no mutable field is silently dropped.
- Every selected snapshot is validated for state ≤1e-7, observation MAE ≤1e-3,
  geometry ≤1e-6 m, model-XML identity, and deterministic double replay.
- Snapshot SHA256 is checked before every branch and again immediately before
  each horizon × repeat branch.
- Snapshot gzip uses `mtime=0` and PyTorch RNG state is serialized as NumPy
  bytes, making the file SHA a deterministic content identity.

### 3.4 Branch execution

- `H=16`, `To=2`, `horizons=[1,2,4,8,15]`, `repeats=3`, `h_continue=15`.
- Each branch restores the same snapshot, resets the policy, predicts the full
  chunk and executes the first `h` actions, then uses `h=15` until termination.
- `h=15` is the fixed-h=15 continuation comparator.
- Horizon order within each state × repeat uses
  `branch_order_seed = 20261118 + source_seed*5 + repeat_index` and
  `default_rng(seed).permutation([1,2,4,8,15])`; the realized order is recorded.
- Common policy-noise seeds use
  `repeat_seed = 1000000 + source_seed*17 + repeat_index` and the same
  `policy_noise_seed(repeat_seed, call_index)` schedule across horizons. The
  report does not claim identical full-trajectory randomness.
- Strict completeness requires exactly 450 unique rows per split
  (`30 × 5 × 3`), rejects duplicates, missing/extra rows, mixed splits,
  mismatched snapshots/geometry and mismatched environment fingerprints.

### 3.5 Analysis and CLI

- State is the independent unit; repeats are nested within state × horizon.
- `p_s(h) = mean(success over 3 repeats)`.
- `Delta_s = 0.5*(p_s(1)+p_s(2)) - p_s(15)`.
- OLS slope of `Delta_s` on clearance, reported per metre and per millimetre.
- `E = predicted_Delta(c_10) - predicted_Delta(c_90)` with 5,000 state-cluster
  bootstrap resamples for confidence intervals; practical threshold `E >= 0.08`.
- Hypothesis tests use explicit state-level permutation nulls with 100,000
  draws: paired sign-flip for horizon differences and clearance permutation for
  slopes. Bootstrap distributions are no longer used as p-values.
- Secondary analyses: per-horizon rates with state-cluster CIs, h-vs-15
  differences and slopes, Holm correction over the four comparisons using the
  permutation p-values, categorical h×clearance linear probability interaction,
  Spearman robustness, clearance bins, policy calls and wall-clock.
- Discovery and confirmation are analyzed independently; decision rules are
  pre-registered in code and reported without pooling.
- B2 analysis always loads the fixed project config, requires
  `b2_{split}_run.json`, validates protocol/split/config/B1-manifest/runtime
  fingerprints, and rejects missing manifests or bootstrap/threshold overrides.
- B2 commands expose only the run directory and split (plus PREFLIGHT-only
  arguments). Checkpoint, dataset, DP root, max-steps, device and config
  overrides are absent.
- B2 reads the real B1 Full manifest from `reports/b1_full_run.json`; abbreviated
  hashes from prose are not used.

## 4. Tests

Command:

```bash
cd gate_b_v2
source scripts/gateb_env.sh
python -m compileall -q src tests
python -m pytest -q
```

Result: **210 passed** (one harmless SciPy constant-input warning in a synthetic
analysis test). Coverage includes:

1. geometry sign and nut-local frame tests for positive/zero/negative `c_xy` and
   `z_gap`;
2. live-audit fail-closed behavior for ambiguous geometry;
3. stage-gate boundary, approach-direction and first-entry tests;
4. snapshot round-trip, skipped-field audit, RNG round-trip and deterministic
   replay tests;
5. seed-pool isolation and deterministic candidate selection tests;
6. B2 30×5×3 completeness, duplicate/missing/extra/mixed-split rejection;
7. horizon-order reproducibility and common policy-noise tests;
8. state-cluster bootstrap and permutation-test correctness/reproducibility;
9. CLI lock tests proving no asset/runtime overrides;
10. unauthorized discovery/confirmation rejection, confirmation missing-discovery
    rejection, preflight seed/fallback rejection, missing-run-manifest rejection,
    B1 Full manifest field-tampering rejection, policy-reset failure and
    interrupted-harvest overwrite protection;
11. existing B0/B1 regression tests.

No old test was deleted or weakened.

## 5. Live geometry audit

Command:

```bash
python -m gate_b_v2.cli b2-preflight \
  --run-dir runs/b2_preflight_second_revision_final --seed 299999
```

Result: **PASS**. Evidence:
`runs/b2_preflight_second_revision_final/b2_geometry_audit.json` and the public copy
`reports/preflight/b2_geometry_audit.json`.

Key live values on the RTX 3090 environment:

| Item | Value |
|---|---|
| Nut body / collision bars | body 24; bars geoms 46–49 |
| Handle geom excluded | geom 50 |
| Peg collision geom | geom 13 on `peg1` |
| Nut collision thickness `t_nut` | 0.020000 m |
| Hole half extents | 0.022750 × 0.022750 m |
| Peg half extents | 0.016 × 0.016 m |
| `r_hole` / `r_peg` | 0.032173 / 0.022627 m |
| `c_xy` sign checks | positive +0.006750, zero 0.0, negative −0.010000 m |
| `z_gap` sign checks | positive +0.010000, zero 0.0, negative −0.010000 m |
| Tilted-frame check | nut-local 0.051282 m vs old world-z 0.049465 m; difference −0.001817 m |
| Finiteness | 5/5 real simulator states finite |

The audit also confirms visual and collision peg dimensions are identical in this
model; collision geometry remains authoritative.

## 6. Snapshot/replay preflight (seed 299999)

Command:

```bash
python -m gate_b_v2.cli b2-preflight \
  --run-dir runs/b2_preflight_second_revision_final --seed 299999
```

The fixed-h=8 source rollout reached the stage gate at source step **124**. The
snapshot was captured at that step and validated:

| Check | Result |
|---|---|
| Stage gate reached | yes |
| Snapshot schema | 2 |
| Controller/gripper capture audit | complete; only `sim` reference and immutable XML metadata skipped |
| State restore max abs error | 0.0 |
| Observation mean abs error | 0.0 |
| Geometry restore max abs error | 0.0 |
| Double-replay state/observation/geometry errors | 0.0 / 0.0 / 0.0 |
| Model XML identity | yes |
| All validation checks | PASS |

Two independent seed-299999 runs after deterministic serialization produced the
identical snapshot SHA256:

```text
c52aaa5c2b5c83374da376891d521b28baeaa0f8790ee6435dfb33316f9cb5b3
```

The second-revision run `runs/b2_preflight_second_revision_final/` reproduced the same
snapshot SHA256 and validation result, and additionally ran the state smoke
test. Public PREFLIGHT evidence is exported under `reports/preflight/`.

A throwaway first-entry state-harvest smoke used non-formal seeds 299990 and
299991 (source steps 208 and 259). Both records are explicitly `PREFLIGHT`,
`scientific_data=false`, and are excluded from all B2 formal manifests and
results:

`runs/b2_preflight_second_revision_final/state_smoke/b2_preflight_state_smoke.jsonl`.

## 7. Environment fingerprint

The B2 lock reads and verifies these values from the accepted B1 Full manifest
(`reports/b1_full_run.json`):

| Item | Value |
|---|---|
| Checkpoint SHA256 | `adaf17854fb8ff8acaccc56adbf6af321c7bec7fecb22de5257772ec81927c6d` |
| Dataset SHA256 | `7e58906366d79996f13785ff2dd0fe346230373532addc2afc7c92611ae42887` |
| DP source-tree SHA256 | `aec43e20abb0902b606e61fc4a391605ab755e59233ecb5f6bdbfbe8df372f21` |
| B1 Full manifest SHA256 | `1619fa873df00628cc7ec0d414ee5f8d029ae30e0808ab1e00a2905ef41c4175` |
| B2 config fingerprint | `ea97483ae300a74c1b4390270e8578bbd5f17896540d3e086fa1797bb0ca242c` |
| B2 source-tree SHA256 | `3a06883b65bbfd40e80a3cff35b534f0c6b514af3a47a4d06d3f153ee6e10d15` |
| Preflight environment fingerprint SHA256 | `84647b606c8cf107cb73e44491a351ee93a119fede8e51734911a2373e33f276` |
| Preflight implementation commit | `e8f4f4aa4e143c3a288701b2fc4a8e929254e6d6` |
| GPU | NVIDIA GeForce RTX 3090 |
| PyTorch / CUDA | 1.12.1+cu116 / 11.6 |
| Device | `cuda:0` |
| Python | 3.9.13 |
| robomimic / robosuite | 0.2.0 / 1.2.0 |
| mujoco_py | 2.0.2.13 |
| H / To / max_steps | 16 / 2 / 500 |

Any mismatch makes B2 fail closed.

## 8. Source archive

Repository-root archive: `gate_b_v2_source.tar.xz`.

Archive SHA256:

```text
befdd3bcf84ee5c7c27afdf775f86803bc3f51f4fa6f58dc79d48d7297e44848
```

The archive contains the B2 source, tests, configs, scripts, README, the required
B1 Full lock manifest, implementation/execution logs and the small public
PREFLIGHT JSON evidence. It excludes run data, snapshot binaries, assets,
checkpoints, datasets, virtual environments, caches, credentials, this acceptance
report and the second-revision report (repository copies are authoritative;
embedding the archive hash in packaged reports would be self-referential). The
packaged README also omits the archive's own hash for the same reason.

Source Archive Audit (clean extraction under `/tmp/gate_b_v2_archive_audit`):

- archive SHA256 matches the README value;
- `src/`, `tests/`, `configs/`, `scripts/`, `tools/`, `pyproject.toml`,
  `AGENTS.md`, B1 Full manifest and execution logs are byte-identical to the
  workstation source;
- `python -m compileall` is clean;
- `pytest -q` from the extracted archive: **209 passed, 1 skipped** (the
  existing B1 lock test that requires the vendored DP source, which is not
  packaged);
- the workspace test run is **210 passed** because the vendored DP source is
  present locally.

## 9. Unresolved issues and limitations

- **The B2 code has not passed the second independent review.** This report
  supplies second-revision evidence; it is not an acceptance decision.
- No `B2_DISCOVERY_AUTHORIZATION.json` or `B2_CONFIRMATION_AUTHORIZATION.json`
  exists. Discovery and Confirmation are both unauthorized.
- No formal B2 discovery or confirmation state has been collected. This report
  does not claim that B2 data exist or that B2 passed.
- The live audit and snapshot preflight used only the reserved seed 299999 and
  two throwaway non-formal smoke seeds; they are not scientific data.
- The geometry audit confirms the current installed Square-MH collision model.
  A different robosuite/model version would require a fresh audit and could be
  BLOCKED if bar/peg identification is ambiguous.
- The branch execution path is unit-tested but has not been run on the
  simulator in this round because branch episodes are not authorized.
- The confirmation split must not start until discovery results are separately
  reviewed and explicitly authorized.
- Wall-clock is secondary because the B1 Full run showed GPU thermal/power
  throttling.
- B2 does not train CAC or establish a deployment-time visual clearance
  estimator.

## 10. Acceptance condition

**Second-revision code-level evidence is supplied:** implementation against the
frozen v1.1 protocol, fail-closed authorization gates, 210 passing regression
tests, live geometry audit PASS, seed-299999 snapshot/replay PREFLIGHT PASS,
deterministic snapshot SHA, source archive audit, and no unauthorized formal data
collection.

**This is not an acceptance decision and not B2 scientific acceptance.** The B2
code remains unaccepted until the second independent review passes. No
Discovery or Confirmation authorization file exists; neither split may start
without the researcher-created authorization required by the code. No B2
scientific result exists.
