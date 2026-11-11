# B1 readiness report

Date: 2026-11-11 (Asia/Shanghai).
Branch: `codex/gate-b-v2`.
Base commit: `09e9ca63b89349c3905a7dc2bca9fd8e2b99844b`.
Status: **PROTOCOL_REVISION_COMPLETE** — protocol and code are consistent;
B1 has **not** been executed and awaits explicit authorization.

## 1. Readiness checklist

| # | Item | Result | Evidence |
|---|---|---|---|
| 1 | B0 raw data and statistics preserved | **PASS** — 12/12 files byte-identical to `09e9ca6` | SHA256 comparison, `B1_PROTOCOL_AMENDMENT.md` §1 |
| 2 | 10-D absolute action documented; 10→7 conversion retained | **PASS** | protocol §2.1/§3; `actions.py` unchanged |
| 3 | `control_delta=false` remains | **PASS** | `env.py`; B0 manifest |
| 4 | Horizon list amended to `{1,2,4,8,15}` | **PASS** | `configs/gate_b.yaml`, protocol §4.1 |
| 5 | h=15 accepted, h=16 rejected without truncation | **PASS** | unit tests; live validation output |
| 6 | B1 seeds independent of B0 (200000+) | **PASS** | config, runner check, protocol §2.3 |
| 7 | Pilot/Full separate record files | **PASS** | `b1_pilot_episodes.jsonl`, `b1_full_episodes.jsonl`; no-overwrite guard |
| 8 | Pilot 20×5=100; Full 100×5=500; Full includes Pilot seeds | **PASS (design)** | config counts; runner `phase` handling |
| 9 | Same initial state across five h | **PASS (existing)** | runner hash check; analysis rejects mismatches |
| 10 | Policy seed recorded (700000+seed) | **PASS** | B0 rows; runner code |
| 11 | Final-state success predicate, not sticky | **PASS** | `env.py`; B0 rows `success_error=null` |
| 12 | Raw JSONL append-only; no overwrite/mixing | **PASS** | `ensure_new_records_path`; unit test |
| 13 | Statistics pre-registered | **PASS** | Cochran Q, paired cluster bootstrap, exact McNemar, Holm, Wilson, ceiling/floor |
| 14 | Protocol documents updated | **PASS** | `GATE_B_PROTOCOL.md`, `README.md`, `IMPLEMENTATION_STATUS.md` |
| 15 | No B1/B2/simulation/GPU/training run | **PASS** | only static/unit/config checks executed |

## 2. Commands actually run (no experiment)

```bash
cd /home/asus/EAI/gate_b_v2
PYTHONPATH=src .venv/bin/python -m pytest -q
# 38 passed

.venv/bin/python -m compileall -q src tests
# clean

PYTHONPATH=src .venv/bin/python - <<'PY'
# config validation:
# horizons == [1,2,4,8,15]
# B0 seed == 100000, B1 seed == 200000
# available future actions == 15
# validate_horizons(...,16,2) accepts 15 and rejects 16
PY
```

B0 integrity was checked by comparing SHA256 of each report/data file against
`git show 09e9ca6:gate_b_v2/reports/<file>`; all 12 matched.

No `cli smoke`, `cli b0`, `cli b1`, `cli b2`, simulator reset, GPU kernel, or
training command was executed in this round.

## 3. Code changes and tests

New tests: `tests/test_b1_protocol.py`, `tests/test_b1_analysis.py`.

Covered:

- amended config values and B0/B1 seed independence;
- h=15 acceptance and h=16 rejection;
- separate Pilot/Full record names and append guard;
- Holm adjustment and Cochran's Q edge cases;
- Wilson interval;
- paired analysis with synthetic 20-seed × 5-horizon data;
- rejection of unpaired initial states, wrong horizon set and missing
  reference horizon;
- ceiling detection.

Total suite: **38 passed**.

## 4. Is B1 executable under the new protocol?

The code and configuration now support the amended design:

- `bash scripts/run_b1_pilot.sh --run-dir runs/b1_pilot_...` would run
  20 states × 5 horizons with seeds 200000–200019.
- `bash scripts/run_b1_full.sh --run-dir runs/b1_full_...` would run
  100 states × 5 horizons with seeds 200000–200099.
- Records, pairing hashes, policy seeds and pre-registration metadata are
  written per run.
- `bash scripts/analyze.sh <run-dir> --b1-phase pilot|full` computes the
  pre-registered statistics.

However, **execution is intentionally not authorized in this round**. The
actual simulator/GPU behaviour of h=15, the runtime cost, and the empirical
ceiling/floor can only be established by running B1; they are recorded here
as pending validation, not as results.

## 5. Items requiring research-lead confirmation

1. Accept the pre-registered B1 thresholds: alpha 0.05, practical difference
   8 percentage points, Holm over four comparisons, ceiling 0.95 / floor 0.05.
2. Confirm that the 20 Pilot states may be included in the 100-state Full run,
   conditional on Pilot being used only for feasibility.
3. Authorize B1 Pilot execution in a separate round.
4. B2 remains independently blocked: insertion-stage window not frozen,
   snapshot/restore replay not validated, no B2 state collected.

## 6. Answers to the required questions

| Question | Answer |
|---|---|
| Is B0 fully preserved? | **Yes** — 12/12 evidence files match `09e9ca6` byte-for-byte. |
| Is the new protocol consistent with the code? | **Yes** for the amended horizon, seed, phase, pairing, record and statistics paths, verified by 38 static/unit tests. |
| Can B1 be executed under the new protocol? | **Code/config: yes. Experiment: not yet** — awaiting authorization; no B1 episode has run. |
| Are there items that must be confirmed by the research lead? | **Yes** — thresholds, Pilot-state inclusion, B1 authorization, and separately B2 window/snapshot. |
| Was any formal B1 experiment run this round? | **No.** No Pilot, no Full, no B2, no simulator/GPU run. |

**Final status: PROTOCOL_REVISION_COMPLETE — awaiting independent acceptance
and explicit B1 authorization.**
