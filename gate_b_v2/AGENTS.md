# Gate B v2 agent constraints

- Work only in `gate_b_v2/` on `codex/gate-b-v2`; never modify `main`, other experiments,
  ROS 2, system Python/CUDA, drivers, or the existing VGPO environment.
- Read `/home/asus/EAI/AGENTS.md`, the Gate B protocol, and `README.md` before acting.
- Small fixes are allowed only with a reproducible traceback/test; add tests and log each fix.
- Load the official Square-MH checkpoint; do not train, fine-tune, or replace it.
- Do not silently change h=16, action alignment, observation/action semantics, success predicate,
  geometry metric, or B2 stage-window thresholds.
- If H=16 and To=2, only 15 future action slots are available. Stop and ask for approval to amend
  the horizon list; never pad/repeat/stale-fill the missing action.
- B2 is blocked until numeric insertion-stage bounds are approved and deterministic snapshot/
  restore replay passes on the actual workstation.
- Do not run confirmation states for tuning. Keep discovery and confirmation disjoint.
- Do not commit assets, checkpoints, datasets, videos, snapshots, environments, caches, or secrets.
- Record real commands, versions, logs, failures, and decisions in
  `reports/WORKSTATION_EXECUTION_LOG.md`; never claim a simulator run from unit tests.
