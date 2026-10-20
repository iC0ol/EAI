# EAI workspace

The Spatial Intervention Pilot is in spatial_intervention_pilot/. Read its AGENTS.md before editing.
Keep all experiments and Python environments under this EAI workspace; do not create another workspace or worktree.
Do not modify inspection_robot*, ROS2, system Python, NVIDIA drivers or system CUDA.
Checkpoint B was reviewed and the user authorized Phase 3 deployment and six-core VLM smoke inference.
Preserve Phase 0–2 geometry/data/requirements.lock. Use a separate VLM environment. No training or dataset expansion.
Inference may read only public_inputs.jsonl and data/images; private labels are read only by a separate post-inference evaluator.
The user explicitly requested PUBLIC GitHub synchronization to iC0ol/EAI, including generated results.
Never commit Python runtimes, virtual environments, caches or credentials.
