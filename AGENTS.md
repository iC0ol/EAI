# EAI workspace

The Spatial Intervention Pilot is in spatial_intervention_pilot/. Read its AGENTS.md before editing.
Keep all experiments and Python environments under this EAI workspace; do not create another workspace or worktree.
Do not modify inspection_robot*, ROS2, system Python, NVIDIA drivers or system CUDA.
Checkpoint B was reviewed and the user authorized Phase 3 deployment and six-core VLM smoke inference.
Phase 3 was reviewed. The user now authorizes Phase 3.5 error-source diagnostics on the same six core samples.
Preserve Phase 0–2 geometry/data/requirements.lock. Use a separate VLM environment. No training or dataset expansion.
Inference may read only public_inputs.jsonl and data/images; private labels are read only by a separate post-inference evaluator.
For Phase 3.5 only, inference may also read diagnostics/phase3_5/inputs and its clean post-state images.
Keep Phase 3.5 derivatives/results separate. No truth, scene JSON, QC, family or Phase 3 predictions may enter model prompts.
The user explicitly requested PUBLIC GitHub synchronization to iC0ol/EAI, including generated results.
Never commit Python runtimes, virtual environments, caches or credentials.
