# Spatial Intervention Pilot

Scope: Phase 0–2, CPU geometry only. Wait for the user's scene/label review before VLM work.
All writes, environments and caches must stay in this independent project directory.
Never change inspection_robot*, ROS2, system Python, drivers or system CUDA. No sudo.
No model weights, training, external upload or remote repository creation.
Use Python 3.11 in .venv; scripts must use its absolute interpreter or scripts/run.sh.
Compute labels with geometry, never copy expected family labels into results.
Illegal/conflicting edits must raise explicit errors, never become F=0.
Private QC labels and paths must never enter data/images or public_inputs.jsonl.
Preserve failure logs, seeds, environment locks and source revisions.
