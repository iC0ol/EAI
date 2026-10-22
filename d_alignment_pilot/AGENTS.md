# D alignment pilot

This is an independent Gate 1 experiment authorized by the researcher on 2026-10-22.
Do not edit any files outside d_alignment_pilot/. In particular preserve all of
spatial_intervention_pilot/ byte for byte. Use branch research/d-gate1 in the
existing EAI checkout; do not create another workspace or worktree.

Use only official Square low-dimensional demonstrations, one small diffusion
policy, three frozen label conditions and at most two seeds per condition.
No online WandB, pretrained weights, VLM/VLA, training of alignment/posterior
models, new tasks, dataset expansion or system package/driver/CUDA/ROS changes.
All runtimes, dependencies, caches, raw data and checkpoints stay here and are
ignored by Git. Commit only source, configs, compact evidence and reports.

Audit time conventions before training. Split by episode, reserve 5–10 clean
anchors, change only training action labels, use a common valid interval without
padding/wrapping or cross-episode access. The true injected lag is for data
generation and separate post-hoc scoring only, never estimator input.

First train and evaluate Clean. Stop if the pipeline fails, clean performance is
near zero or saturated, or official required dependencies/data are unavailable.
Run offline simple lag identification only after reproducible material closed-loop
degradation. Distinguish deployment failure, insufficient statistical evidence,
and scientific No-Go. Preserve actual errors and executed commands. Never invent
results. Stop after Gate 1 delivery and push without rewriting main or force push.
