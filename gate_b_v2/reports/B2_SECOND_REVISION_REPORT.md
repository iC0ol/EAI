# B2 v1.1 second-revision report

Date: 2026-11-17 (Asia/Shanghai)
Repository: `iC0ol/EAI`
Branch: `codex/b2-protocol-20261116`
Baseline commit: `b6dcf00a54fda5141e452c3d2a3b16b881198efe`
Second-revision code commits: `b23a65dda8b3cc2eb0b6cde36afc0b7ed0ce4cad`
(main fixes) and `e8f4f4aa4e143c3a288701b2fc4a8e929254e6d6` (policy-reset
record check; the preflight implementation commit).
Protocol: `research_spatial_action_round4_20261109/reports/B2_PROTOCOL_REVISION_20261116.md`

Status: **SECOND-REVISION CODE AND PREFLIGHT EVIDENCE SUBMITTED FOR INDEPENDENT
REVIEW. B2 CODE IS NOT YET ACCEPTED. DISCOVERY AND CONFIRMATION ARE BOTH
UNAUTHORIZED. NO FORMAL B2 STATE OR BRANCH EPISODE WAS COLLECTED.**

## 1. Fixed issues

| Review finding | Fix |
|---|---|
| No formal authorization gate | Added `gate_b_v2/src/gate_b_v2/authorization.py`. Formal discovery/confirmation harvesting and branch execution require the same run directory's PASS PREFLIGHT plus a researcher-created `B2_DISCOVERY_AUTHORIZATION.json` or `B2_CONFIRMATION_AUTHORIZATION.json`. The code never creates these files. |
| Preflight could accept arbitrary seeds / fallback | Preflight seed is frozen at `299999` and other seeds are rejected before loading the model. `gate_reached=false` or `fallback_used=true` forces `BLOCKED`; a fallback snapshot is diagnostic only. |
| B2 analysis config bypass | `analyze_b2_split()` now runs `validate_b2_config()`, requires `b2_{split}_run.json`, validates protocol/split/config/B1-manifest/runtime fingerprints, and always uses the fixed project config. B2 ignores `--config` and `--bootstrap-samples`; missing run manifests are rejected. |
| Invalid bootstrap p-values | Removed bootstrap-distribution p-values. Horizon differences use a paired state-level sign-flip permutation test; clearance slopes use a state-level clearance permutation test. Both use 100,000 permutations with recorded seeds and actual counts. The 5,000 state-cluster bootstrap is retained for confidence intervals only. |
| Weak B1 Full environment lock | `load_b1_full_manifest()` now validates the accepted B1 Full manifest itself with `validate_b1_environment()`, covering checkpoint/dataset/DP-tree, GPU, PyTorch/CUDA, device, H/To, action dimensions, EMA, policy seed offset, config fingerprint, phase, seed interval and episode count. |
| Policy reset silently ignored | `try/except Exception: pass` was replaced by `reset_policy_or_block()` in source harvesting and branch execution. A missing or failing reset is BLOCKED. Branch records now carry `policy_reset_verified=true`. |
| Harvest interruption could overwrite data | `harvest_split()` refuses to continue if any harvest manifest, candidate file, state manifest, summary, status/episode/run file, or split snapshot directory already exists. A rerun must use a brand-new run directory; old data is never deleted. |

Additional engineering fixes:

- Public PREFLIGHT JSON evidence export (`b2-export-preflight-evidence`) with
  `marker=PREFLIGHT`, `scientific_data=false`, and no snapshot binaries.
- Preflight PASS now requires geometry audit PASS, a real stage-gate snapshot,
  snapshot restore and deterministic replay validation, and forbids fallback.
- Source-tree fingerprint in the preflight summary lets documentation/evidence
  commits preserve a valid preflight while still blocking changed code.
- Confirmation authorization must reference a completed, integrity-checked
  discovery run and the SHA256 of `b2_discovery_analysis.json`; discovery must
  have a complete 450-row dataset, passing snapshot validation, `B2_REPORT.md`,
  and a non-STOP decision.

## 2. Unresolved issues / limitations

- The B2 code has **not yet passed the second independent review**.
- No `B2_DISCOVERY_AUTHORIZATION.json` or `B2_CONFIRMATION_AUTHORIZATION.json`
  exists. Discovery and Confirmation are both unauthorized.
- No formal discovery or confirmation state was collected; no branch episode
  was run; no training or fine-tuning was performed.
- The branch execution path remains unit-tested but has not been run on the
  simulator in this round.
- The confirmation split must not start until discovery results are separately
  reviewed and explicitly authorized.
- Wall-clock remains secondary because B1 Full showed GPU thermal/power
  throttling.
- B2 does not train CAC or establish a deployment-time visual clearance
  estimator.

## 3. Tests

Commands:

```bash
cd gate_b_v2
source scripts/gateb_env.sh
python -m compileall -q src tests
python -m pytest -q
```

Result: **210 passed** (one harmless SciPy constant-input warning in a synthetic
analysis test). The suite includes the required new tests:

1. unauthorized Discovery rejected;
2. unauthorized Confirmation rejected;
3. Confirmation without discovery results rejected;
4. preflight without the stage gate cannot PASS;
5. non-299999 formal preflight seed rejected;
6. analysis without a B2 run manifest rejected;
7. bootstrap parameter override rejected;
8. practical-threshold override rejected;
9. B1 Full manifest key tampering rejected;
10. permutation-test reproducibility and correctness;
11. policy-reset failure blocked;
12. partial-harvest overwrite protection;
13. all existing B0/B1 regression tests.

No old test was deleted or weakened.

## 4. Real workstation validation

### 4.1 Live geometry audit

The second-revision preflight ran the live MuJoCo audit on the RTX 3090:

- status **PASS**;
- nut collision bars `46,47,48,49`; handle `50` excluded; peg collision geom
  `13`;
- `c_xy` positive/zero/negative checks pass;
- `z_gap` positive/zero/negative checks pass in the nut-local frame;
- 30-degree tilt confirms the old world-z value differs from the authoritative
  nut-local value;
- finite-value checks pass.

Public evidence: `reports/preflight/b2_geometry_audit.json`.

### 4.2 Snapshot/replay preflight (seed 299999)

- stage gate reached at source step **124**;
- snapshot SHA256:
  `c52aaa5c2b5c83374da376891d521b28baeaa0f8790ee6435dfb33316f9cb5b3`;
- state, observation and geometry restore errors: **0.0**;
- deterministic double replay state/observation/geometry errors: **0.0**;
- all validation checks pass;
- `fallback_used=false`;
- non-formal state-harvest smoke seeds `299990,299991` captured 2/2 states and
  are explicitly `PREFLIGHT` / `scientific_data=false`.

Public evidence:

- `reports/preflight/b2_preflight_summary.json`
- `reports/preflight/b2_preflight_snapshot_validation.json`
- `reports/preflight/b2_preflight_environment.json`
- `reports/preflight/PREFLIGHT_EVIDENCE_MANIFEST.json`

The snapshot binary itself is not committed.

### 4.3 Environment fingerprint

| Item | Value |
|---|---|
| GPU | NVIDIA GeForce RTX 3090 |
| PyTorch / CUDA | 1.12.1+cu116 / 11.6 |
| Device | `cuda:0` |
| Python | 3.9.13 |
| robomimic / robosuite | 0.2.0 / 1.2.0 |
| mujoco_py | 2.0.2.13 |
| H / To / max_steps | 16 / 2 / 500 |
| B2 config fingerprint | `ea97483ae300a74c1b4390270e8578bbd5f17896540d3e086fa1797bb0ca242c` |
| Preflight implementation commit | `e8f4f4aa4e143c3a288701b2fc4a8e929254e6d6` |
| Source-tree SHA256 | `3a06883b65bbfd40e80a3cff35b534f0c6b514af3a47a4d06d3f153ee6e10d15` |
| Preflight environment SHA256 | `84647b606c8cf107cb73e44491a351ee93a119fede8e51734911a2373e33f276` |
| Checkpoint SHA256 | `adaf17854fb8ff8acaccc56adbf6af321c7bec7fecb22de5257772ec81927c6d` |
| Dataset SHA256 | `7e58906366d79996f13785ff2dd0fe346230373532addc2afc7c92611ae42887` |
| DP source-tree SHA256 | `aec43e20abb0902b606e61fc4a391605ab755e59233ecb5f6bdbfbe8df372f21` |

## 5. Source archive

Repository-root archive: `gate_b_v2_source.tar.xz`.

Archive SHA256:

```text
befdd3bcf84ee5c7c27afdf775f86803bc3f51f4fa6f58dc79d48d7297e44848
```

The archive is rebuilt after the second revision. It contains the source, tests,
configs, scripts, README, required B1 Full lock manifest, implementation/execution
logs and small public PREFLIGHT JSON evidence. It excludes snapshot binaries,
run data, checkpoints, datasets, virtual environments, caches, credentials, this
report and the acceptance report (repository copies are authoritative; embedding
the archive's own hash in packaged reports would be self-referential).

Source Archive Audit (clean extraction under `/tmp/gate_b_v2_archive_audit`):

- archive SHA256 matches the recorded value;
- `src/`, `tests/`, `configs/`, `scripts/`, `tools/`, `reports/preflight/`,
  `pyproject.toml`, `AGENTS.md`, B1 Full manifest and execution logs are
  byte-identical to the workstation source;
- `python -m compileall` is clean;
- extracted-archive test run: **209 passed, 1 skipped** (the existing B1 lock
  test that needs the vendored DP source, which is not packaged);
- workstation test run: **210 passed**.

## 6. GitHub CI

GitHub Actions (`Gate B v2 source audit`) for commit
`ae4a973bc6e381ba75f87f7c86c826aff79c148a`:

| Trigger | Run ID | Result |
|---|---:|---|
| Push to `codex/b2-protocol-20261116` | `44017383378` | **success** |
| Pull request event for the same commit | `44017391408` | **success** |

Both jobs passed in the push run:

- `current-harness-tests` — success (37 s);
- `source-archive-audit` — success (41 s), including archive SHA check,
  clean extraction, source compilation and extracted-archive tests.

The only annotation was the GitHub Actions Node.js 20 deprecation notice; it
does not affect the test or archive audit result.

The CI result above is for the code/evidence commit. Any later documentation-only
commit (including this report's CI-result update) does not change
`src/gate_b_v2`, the source tree fingerprint or `gate_b_v2_source.tar.xz`.

## 7. Authorization status

| Split | Authorization file | Status |
|---|---|---|
| Discovery | `B2_DISCOVERY_AUTHORIZATION.json` | **NOT PRESENT — NOT AUTHORIZED** |
| Confirmation | `B2_CONFIRMATION_AUTHORIZATION.json` | **NOT PRESENT — NOT AUTHORIZED** |

No authorization file was created by the implementation. Formal discovery and
confirmation remain blocked by code until the research lead creates the required
file after independent review.

## 8. Boundaries observed

This round did not collect Discovery or Confirmation states, run any formal B2
branch episode, train or fine-tune a model, modify the frozen research question,
horizons, seed pools, `E` definition or 0.08 threshold, modify B0/B1 historical
results, create authorization files, force-push, merge a PR, or modify system
components. All new preflight evidence is marked `PREFLIGHT` and
`scientific_data=false`.
