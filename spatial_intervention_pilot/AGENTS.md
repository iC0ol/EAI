# Spatial Intervention Pilot

Scope: Phase 0–2, CPU geometry only. Wait for the user's scene/label review before VLM work.
Research files, environments and caches stay in this project directory under /home/asus/EAI.
Git metadata is at /home/asus/EAI/.git, following the user's explicit workspace preference.
Never change inspection_robot*, ROS2, system Python, drivers or system CUDA. No sudo.
No model weights or training. The user explicitly authorized a PUBLIC iC0ol/EAI GitHub repository.
Synchronize source, configuration, generated scenes, labels, previews and reports; exclude runtimes, venv and caches.
Use Python 3.11 in .venv; scripts must use its absolute interpreter or scripts/run.sh.
Compute labels with geometry, never copy expected family labels into results.
Illegal/conflicting edits must raise explicit errors, never become F=0.
Private QC labels and paths must never enter data/images or public_inputs.jsonl.
Preserve failure logs, seeds, environment locks and source revisions.
