# KYC bounded diagnostics, 2026-10-29

Read `00_原始任务书.md`, `STATUS.md`, and the frozen execution protocol before work. This directory is a new authorized round; previous research directories are read-only evidence.

- Codex and real DeepSeek review and accept; GPT-6.1-sol / max executes diagnostics only after both reviewers approve a concrete task.
- Zero optimizer updates. No full training, new algorithm, environment installation, dataset/model download, test-set evaluation, or automatic resource expansion.
- Stage 0 is read-only. Stage 1 requires a documented unresolved question and the joint-approved gate. Caps: 32 fixed-sample forward calls, 16 rollouts × at most 150 steps, 1 GPU hour including rendering/simulation and diagnostics. Unused budget is not a target.
- Preserve prior data/checkpoints/code/results. New outputs only here. Read existing EAI runtime and public assets; put new caches and temporary files here. No system or other project changes.
- Freeze root/sample IDs, metrics, thresholds, counting rules, and stop conditions before running. Record NOT_RUN explicitly. Replicates are not independent roots.
- Only the assigned executor runs model inference/simulation. Main reviewers may read existing files and perform CPU statistics without creating new observations or model outputs.
- Public GitHub synchronization is authorized for original code and small results. Do not commit third-party weights/data/software, credentials, raw CLI transcripts, runtimes, or caches. Coordinate Git writes; executor owns publication after dispatch.
- New full ACT training requires a new explicit human approval. A next-stage task document is not execution authorization.
