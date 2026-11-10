#!/usr/bin/env bash
# Source this file before any Gate B v2 command. It pins the isolated runtime
# and prevents ROS/other PYTHONPATH entries from leaking into this Python 3.9 venv.
set -euo pipefail

GATE_B_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export GATE_B_ROOT

unset PYTHONPATH PYTHONHOME
export PYTHONNOUSERSITE=1
export PYTHONPATH="$GATE_B_ROOT/src:$GATE_B_ROOT/third_party/diffusion_policy"

export MUJOCO_PY_MUJOCO_PATH="$GATE_B_ROOT/.mujoco/mujoco210"
export LD_LIBRARY_PATH="$GATE_B_ROOT/.mujoco/mujoco210/bin${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PATH="$GATE_B_ROOT/.venv/bin:$PATH"

# Workspace construction imports wandb; never open a network run.
export WANDB_MODE=offline
export WANDB_SILENT=true
