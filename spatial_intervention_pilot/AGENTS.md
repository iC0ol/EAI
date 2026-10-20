# Spatial Intervention Pilot

Scope: Checkpoint B approved; Phase 3 Qwen3-VL-4B-Instruct deployment and six-core smoke inference only.
Phase 3 reviewed; Phase 3.5 diagnostics are now authorized on the same six samples with the same installed model/environment.
No training, fine-tuning, model substitution or dataset expansion. Report OOM/dependency issues before corrective changes.
Research files, environments and caches stay in this project directory under /home/asus/EAI.
Git metadata is at /home/asus/EAI/.git, following the user's explicit workspace preference.
Never change inspection_robot*, ROS2, system Python, drivers or system CUDA. No sudo.
Model weights may be downloaded to ignored project-local caches for the authorized Qwen3-VL model only. No training.
The user explicitly authorized a PUBLIC iC0ol/EAI GitHub repository.
Synchronize source, configuration, generated scenes, labels, previews and reports; exclude runtimes, venv and caches.
Preserve Python 3.11 .venv, requirements.lock, all geometry/data/tests. Use a separate .venv-vlm with its own lock.
VLM inference reads only public_inputs.jsonl and data/images; never read private labels, scenes, QC or family information.
Phase 3.5 additionally allows the dedicated sanitized diagnostics/phase3_5/inputs and images, never its private mapping.
Keep all Phase 3 predictions, locks, data and geometry implementation immutable. Do not upgrade any environment.
Only the independent evaluator reads private labels, after inference is complete. Do not tune the frozen prompt against answers.
Compute labels with geometry, never copy expected family labels into results.
Illegal/conflicting edits must raise explicit errors, never become F=0.
Private QC labels and paths must never enter data/images or public_inputs.jsonl.
Preserve failure logs, seeds, environment locks and source revisions.
