# M — limited-budget directional action audit

Authorized M-Gate 0 v2, 2026-10-23. Independent branch `research/m-gate0`,
based on `cea2502eee1dd6504035f4fcde47af1833a90b93`. All new files and
runtime caches stay in this directory. Existing D assets are read-only inputs;
no D experiment is executed. No training, downloads, second task or Gate 1 run.

Read [the preregistration](reports/gate0/protocol.md) before running anything.
Use `bash m_direction_pilot/scripts/run.sh <script.py> [arguments]` from EAI.
The launcher reuses the installed isolated D Python environment without changing
it, imports only the pinned upstream libraries, and redirects caches here.
Large traces are local in `local/`; compact hashes and every planned branch are
public. Scripts refuse to overwrite experimental results.
