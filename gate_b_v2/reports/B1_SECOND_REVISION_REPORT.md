# B1 second revision report

Date: 2026-11-12 (Asia/Shanghai).
Branch: `codex/gate-b-v2`.
Base commit: `3f8f88a7e49dfe6abc1929c65572015842caaa6a`.
B0 commit: `09e9ca63b89349c3905a7dc2bca9fd8e2b99844b`.
Status: **CODE_REVISION_COMPLETE — AWAITING INDEPENDENT REVIEW AND B1 PILOT
AUTHORIZATION.**

This round changed code, configuration, tests and documents only. **No B0,
B1 Pilot, B1 Full, B2, simulator, GPU inference, training or checkpoint
operation was started.**

## 1. Revision summary

| # | Problem | Fix |
|---|---|---|
| 1 | `PRIMARY_TOPIC.md` still described 7-D delta actions, `h∈{1,2,4,8,16}` and stale experiment status | Synchronized the whole document with the checkpoint-native 10-D absolute interface, H/h definitions, amended horizons, disjoint B1 seeds and actual B0/B1/B2 status; historical §11 kept with a dated supersession note |
| 2 | Pilot and Full reused the same 20 initial states | Split into Pilot 200000–200019 (20 states) and Full 200020–200119 (100 new states), 120 disjoint states; runner validates complete intervals, not just start values |
| 3 | `analyze_b1()` could report statistics on incomplete data | Added a strict completeness gate: exact counts, seed ranges, horizons, phase, manifests, pairing hashes and verified flags; ambiguous Pilot+Full requires explicit `--b1-phase` |
| 4 | B1 could still collect B2 state snapshots | Removed `--collect-b2-states` and the `run_b1` collection parameter/path; B2 runner and snapshot code remain intact but unstarted |
| 5 | Formal B1 counts could be changed with `--episodes` | Removed the B1 `--episodes` override; Pilot 20×5 and Full 100×5 are locked by config |
| 6 | Historical Source Audit failed | Reproduced the failure: the archive uses a `src` layout and the workflow omitted `PYTHONPATH`; corrected the audit and re-added a verified workflow |

## 2. Main-document consistency

| Document / file | 10-D absolute action | H=16, To=2 | h set `{1,2,4,8,15}` | Disjoint seeds | B2 isolation |
|---|---|---|---|---|---|
| `PRIMARY_TOPIC.md` | yes | yes | yes | yes | yes |
| `GATE_B_PROTOCOL.md` | yes | yes | yes | yes | yes |
| `configs/gate_b.yaml` | checkpoint-native (unchanged) | yes | yes | yes | n/a |
| `actions.py` / `env.py` | conversion + `control_delta=false` (unchanged) | yes | n/a | n/a | n/a |
| `runner.py` / `analysis.py` | n/a | n/a | yes | yes | yes |
| `README.md` / `IMPLEMENTATION_STATUS.md` | yes | yes | yes | yes | yes |

`PRIMARY_TOPIC.md` §11 is a historical 2026-11-10 record and was not rewritten;
a dated note marks its stale local-loading statement and old protocol as
superseded by §12.

## 3. Seed independence

| Phase | Seed start | Seed end | States |
|---|---:|---:|---:|
| B0 (historical) | 100000 | 100099 | 100 |
| B1 Pilot | 200000 | 200019 | 20 |
| B1 Full | 200020 | 200119 | 100 |

- B1 uses 120 distinct initial states.
- Full never reuses a Pilot state; B1 never uses a B0 state.
- `core.validate_seed_ranges` checks the complete intervals before the first
  episode. A Full range starting at 200010 (overlapping Pilot) is rejected
  even though its start differs from Pilot's start.
- Every B1 record carries `b1_phase`, `b1_seed_start` and `b1_seed_end`; each
  phase writes its own `b1_{phase}_run.json` with the actual range and all
  three declared ranges.
- Policy seed remains deterministic: `700000 + environment seed`.

## 4. Data-integrity gate

`analyze_b1()` now refuses to produce statistics unless all of the following
hold for a formal Pilot/Full run:

1. the phase-specific record file exists;
2. the phase-specific Manifest `b1_{phase}_run.json` exists;
3. Manifest `b1_phase` matches the requested phase;
4. Manifest horizons equal the protocol horizons `{1,2,4,8,15}`;
5. Manifest `episodes`, `seed_start`, `seed_end` and `records_file` match the
   config and the actual JSONL;
6. the JSONL seed set is exactly the declared interval (no missing or extra
   seeds);
7. the record count is exactly `episodes × horizons` (100 for Pilot, 500 for
   Full);
8. every seed has all five horizons and no duplicate `(seed, horizon)` exists;
9. all rows carry the expected `b1_phase`;
10. all five horizon rows of a seed share one `initial_state_sha256`;
11. `paired_initial_state_verified` is true for every row.

If both `b1_pilot_episodes.jsonl` and `b1_full_episodes.jsonl` exist,
`--b1-phase` is mandatory; automatic Pilot preference is removed. Formal
counts are locked: the B1 CLI has no `--episodes`, and `run_b1()` accepts only
the phase.

## 5. B2 isolation

- `b1 --collect-b2-states` was removed from the CLI.
- `GateBExperiment.run_b1()` has no `collect_b2_states` parameter and contains
  no snapshot or B2 state-manifest writing.
- B2's independent `run_b2()`, branch runner, snapshot code and stage gate are
  preserved. B2 remains unstarted and still requires a frozen insertion-stage
  window and deterministic snapshot/restore replay in a separate authorized
  round.

## 6. Statistical protocol

The pre-registered design is unchanged:

- unit = initial-state seed; five horizons are paired conditions;
- h=8 is the sole reference;
- Cochran's Q for the five-level overall test;
- paired cluster bootstrap by seed;
- exact McNemar for each h vs h=8;
- Holm step-down over the four comparisons;
- Wilson 95 % intervals per horizon;
- alpha 0.05, practical difference 0.08, ceiling 0.95, floor 0.05;
- statistical significance and practical significance are reported separately;
- ceiling/floor are not interpreted as method success;
- no “highest observed rate wins” claim.

Synthetic-data tests verify these paths and the completeness failures.

## 7. B0 data integrity

The following 12 files were compared by SHA256 against the B0 commit
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

Result: **12/12 B0 historical artifacts unchanged.** No B0 episode was rerun,
deleted, replaced or mixed with B1 data.

## 8. Test and static-check results

| Check | Result |
|---|---|
| `pytest -q` (without PYTHONPATH after `pythonpath=["src"]`) | **56 passed** |
| `python -m compileall -q src tests` | clean |
| `bash -n scripts/*.sh` | clean |
| YAML parse of config and workflow | clean |
| `git diff --check` | clean |
| Config horizons | `[1, 2, 4, 8, 15]` |
| Seed intervals | B0 100000–100099; Pilot 200000–200019; Full 200020–200119; overlap-free |
| `available_future_actions(16,2)` | 15 |
| h=15 / h=16 | accepted / rejected |
| B0 artifact SHA256 | 12/12 unchanged |
| Archive audit, original command | reproduced failure: `ModuleNotFoundError: No module named 'gate_b_v2.geometry'` (3 collection errors) |
| Archive audit with `PYTHONPATH=<archive>/gate_b_v2/src` | **8 passed** |

### GitHub Actions

The historical `Gate B v2 source audit` failure at
`d688ec4c90653801f3a91384fb1e71d1d67760c6` was a **workflow configuration
failure**, not a source-code defect: the archive has a `src` layout and the
workflow ran `pytest` without putting `gate_b_v2/src` on `PYTHONPATH`. The
archive itself compiles and its tests pass when the path is set.

A corrected workflow is added at
`.github/workflows/gate-b-v2-source-audit.yml` with:
- the archive SHA256 verification and extraction retained;
- `PYTHONPATH` pointing at the extracted `gate_b_v2/src`;
- numpy/pytest installed before the archive test;
- a second `current-harness-tests` job that runs the current tree's
  `compileall` and 56-test suite.

Post-push result for code commit `1de828728c0bf4d740cb0924950e070712315726`:

| Trigger | Run | Result |
|---|---|---|
| push to `codex/gate-b-v2` | [43141211175](https://github.com/iC0ol/EAI/actions/runs/43141211175) | **success** |
| `pull_request` (Draft #1) | [43141217110](https://github.com/iC0ol/EAI/actions/runs/43141217110) | **success** |

Job results from run 43141217110:

- `source-archive-audit`: success; archive SHA256 verified; **8 passed in 0.09 s**.
- `current-harness-tests`: success; compileall and **56 passed in 0.50 s**.

The historical failing run
[42779437780](https://github.com/iC0ol/EAI/actions/runs/42779437780) at
`d688ec4` failed for the missing `PYTHONPATH`; it was reproduced locally and
is fixed in the new workflow. The report-only follow-up commit triggers the
same workflow again; no code change is involved.

## 9. Experiment status

| Phase | Status |
|---|---|
| B0 | **COMPLETED** — 84/100 = 0.84, Wilson 95 % CI 0.7558–0.8990 |
| B1 Pilot | **NOT EXECUTED** |
| B1 Full | **NOT EXECUTED** |
| B2 | **NOT EXECUTED** |

No `runs/b1_*` directory exists. No simulator, GPU or training command was
executed in this round.

## 10. Final status

**CODE_REVISION_COMPLETE — AWAITING INDEPENDENT REVIEW AND B1 PILOT
AUTHORIZATION.**

Open items for the research lead:

1. Accept or revise the pre-registered thresholds (alpha 0.05, 8 pp practical
   difference, Holm over four comparisons, ceiling 0.95 / floor 0.05).
2. Accept the disjoint seed design (Pilot 200000–200019, Full 200020–200119).
3. Authorize B1 Pilot separately; this round deliberately did not start it.
4. B2 still requires a frozen insertion-stage window and deterministic
   snapshot/restore replay; B2 state collection is not part of B1.
