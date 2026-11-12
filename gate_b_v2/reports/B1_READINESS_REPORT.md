# B1 readiness report

Date: 2026-11-11 (Asia/Shanghai).
Branch: `codex/gate-b-v2`.
Base commit: `09e9ca63b89349c3905a7dc2bca9fd8e2b99844b`.
Status: **CODE_REVISION_COMPLETE** — protocol and code are consistent;
B1 has **not** been executed and awaits explicit authorization.

## 1. Readiness checklist

| # | Item | Result | Evidence |
|---|---|---|---|
| 1 | B0 raw data and statistics preserved | **PASS** — 12/12 files byte-identical to `09e9ca6` | SHA256 comparison, `B1_PROTOCOL_AMENDMENT.md` §1 |
| 2 | 10-D absolute action documented; 10→7 conversion retained | **PASS** | protocol §2.1/§3; `actions.py` unchanged |
| 3 | `control_delta=false` remains | **PASS** | `env.py`; B0 manifest |
| 4 | Horizon list amended to `{1,2,4,8,15}` | **PASS** | `configs/gate_b.yaml`, protocol §4.1 |
| 5 | h=15 accepted, h=16 rejected without truncation | **PASS** | unit tests; static validation |
| 6 | B0/Pilot/Full seed intervals disjoint | **PASS** — 100000–100099 / 200000–200019 / 200020–200119 | config + `validate_seed_ranges` tests |
| 7 | Overlap checked on complete intervals, not just starts | **PASS** | shifted-range overlap tests |
| 8 | Pilot/Full separate records and manifests | **PASS** | `b1_{pilot,full}_episodes.jsonl`, `b1_{pilot,full}_run.json` |
| 9 | Formal counts locked: Pilot 20×5, Full 100×5 | **PASS** | no B1 `--episodes`; parser/signature tests |
| 10 | Same initial state across five h | **PASS (existing)** | runner hash check; analysis rejects mismatches |
| 11 | Policy seed recorded (700000+seed) | **PASS** | B0 rows; runner code |
| 12 | Final-state success predicate, not sticky | **PASS** | `env.py`; B0 rows `success_error=null` |
| 13 | Raw JSONL append-only; no overwrite/mixing | **PASS** | `ensure_new_records_path`; unit test |
| 14 | Analysis completeness gate | **PASS** | exact seeds, count, horizons, manifest, phase and pairing; failure tests |
| 15 | Ambiguous Pilot+Full requires explicit phase | **PASS** | `_select_b1_records` + unit test |
| 16 | B1 cannot collect B2 states | **PASS** | no CLI flag/parameter; no snapshot writes in `run_b1` |
| 17 | Statistics pre-registered | **PASS** | Cochran Q, paired cluster bootstrap, exact McNemar, Holm, Wilson, ceiling/floor |
| 18 | Protocol documents updated | **PASS** | `GATE_B_PROTOCOL.md`, `PRIMARY_TOPIC.md`, `README.md`, `IMPLEMENTATION_STATUS.md` |
| 19 | No B1/B2/simulation/GPU/training run | **PASS** | only static/unit/config checks executed |

## 2. Commands actually run (no experiment)

```bash
cd /home/asus/EAI/gate_b_v2
PYTHONPATH=src .venv/bin/python -m pytest -q
# 56 passed

.venv/bin/python -m compileall -q src tests
# clean

PYTHONPATH=src .venv/bin/python - <<'PY'
# config validation:
# horizons == [1,2,4,8,15]
# B0 == 100000-100099, Pilot == 200000-200019, Full == 200020-200119
# available future actions == 15
# validate_horizons(...,16,2) accepts 15 and rejects 16
# validate_seed_ranges rejects shifted/full-interval overlap
PY
```

B0 integrity was checked by comparing SHA256 of each report/data file against
`git show 09e9ca6:gate_b_v2/reports/<file>`; all 12 matched.

No `cli smoke`, `cli b0`, `cli b1`, `cli b2`, simulator reset, GPU kernel, or
training command was executed in this round.

## 3. Code changes and tests

New tests: `tests/test_b1_protocol.py`, `tests/test_b1_analysis.py`.

Covered:

- amended config values and disjoint B0/Pilot/Full seed intervals;
- overlap detection on complete intervals (shifted starts included);
- h=15 acceptance and h=16 rejection;
- separate Pilot/Full record and manifest names, append guard;
- locked formal counts (no `--episodes`, no B2 collection flag/parameter);
- Pilot 20×5 and Full 100×5 completeness, missing/duplicate/out-of-range
  seed and missing-horizon rejection;
- Manifest phase/horizon/count/seed-range/record-file validation;
- explicit phase required when both Pilot and Full exist;
- unpaired hash and `paired_initial_state_verified=false` rejection;
- Holm adjustment and Cochran's Q edge cases, Wilson interval, ceiling;
- statistics on synthetic 20-seed and 100-seed paired data.

Total suite: **56 passed**.

## 4. Is B1 executable under the new protocol?

The code and configuration now support the amended design:

- `bash scripts/run_b1_pilot.sh --run-dir runs/b1_pilot_...` would run
  20 states × 5 horizons with seeds 200000–200019.
- `bash scripts/run_b1_full.sh --run-dir runs/b1_full_...` would run
  100 **new** states × 5 horizons with seeds 200020–200119 (no Pilot reuse).
- Records, pairing hashes, policy seeds and phase-specific manifests are
  written per run; the analyzer refuses incomplete or ambiguous data.
- `bash scripts/analyze.sh <run-dir> --b1-phase pilot|full` computes the
  pre-registered statistics.

However, **execution is intentionally not authorized in this round**. The
actual simulator/GPU behaviour of h=15, the runtime cost, and the empirical
ceiling/floor can only be established by running B1; they are recorded here
as pending validation, not as results.

## 5. Items requiring research-lead confirmation

1. Accept the pre-registered B1 thresholds: alpha 0.05, practical difference
   8 percentage points, Holm over four comparisons, ceiling 0.95 / floor 0.05.
2. Confirm the disjoint design: Pilot 200000–200019 and Full 200020–200119
   (120 distinct states), with Full never reusing Pilot data.
3. Authorize B1 Pilot execution in a separate round.
4. B2 remains independently blocked: insertion-stage window not frozen,
   snapshot/restore replay not validated, no B2 state collected.

## 6. Answers to the required questions

| Question | Answer |
|---|---|
| Is B0 fully preserved? | **Yes** — 12/12 evidence files match `09e9ca6` byte-for-byte. |
| Is the new protocol consistent with the code? | **Yes** for the amended horizon, seed, phase, pairing, record and statistics paths, verified by 56 static/unit tests. |
| Can B1 be executed under the new protocol? | **Code/config: yes. Experiment: not yet** — awaiting authorization; no B1 episode has run. |
| Are there items that must be confirmed by the research lead? | **Yes** — thresholds, disjoint seed design, B1 authorization, and separately B2 window/snapshot. |
| Was any formal B1 experiment run this round? | **No.** No Pilot, no Full, no B2, no simulator/GPU run. |

**Final status: CODE_REVISION_COMPLETE — awaiting independent acceptance
and explicit B1 authorization.**
