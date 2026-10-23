# M — limited-budget directional action audit

Authorized M-Gate 0 v2, 2026-10-23. Independent branch `research/m-gate0`,
based on `cea2502eee1dd6504035f4fcde47af1833a90b93`. All new files and
runtime caches stay in this directory. Existing D assets are read-only inputs;
no D experiment is executed. No training, downloads, second task or Gate 1 run.

Delivered decision: **Invalid / Engineering blocked**. The first mandatory
expert prefix failed the frozen fidelity checks. Actual work:52 expert prefix
control steps,0 suffixes,0 B branches,0 new training. See the
[decision report](reports/gate0/gate0_go_no_go.md),
[numerical/physical diagnosis](reports/gate0/expert_fork_fidelity.md), and
[complete144-row branch ledger](outputs/gate0/all_branch_ledger.csv).
The12 frozen states remain in the denominator. Stop for researcher review;
the remaining budget does not authorize a retry or another experiment.

Read [the preregistration](reports/gate0/protocol.md) before running anything.
Use `bash m_direction_pilot/scripts/run.sh <script.py> [arguments]` from EAI.
The launcher reuses the installed isolated D Python environment without changing
it, imports only the pinned upstream libraries, and redirects caches here.
Large traces are local in `local/`; compact hashes and every planned branch are
public. Scripts refuse to overwrite experimental results.
