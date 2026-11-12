#!/usr/bin/env bash
# Source this file before any Gate B v2 command. It pins the isolated runtime
# and prevents ROS/other PYTHONPATH entries from leaking into this Python 3.9 venv.
set -euo pipefail

GATE_B_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export GATE_B_ROOT

unset PYTHONPATH PYTHONHOME
export PYTHONNOUSERSITE=1
export PYTHONPATH="$GATE_B_ROOT/src:$GATE_B_ROOT/third_party/diffusion_policy"

# free-mujoco-py bundles MuJoCo 2.1 and overwrites MUJOCO_PY_MUJOCO_PATH at
# import. Its Linux GPU auto-detection does not recognise the Ubuntu
# /usr/lib/x86_64-linux-gnu driver layout, so this runtime uses the OSMesa
# software-render build. glibc caches LD_LIBRARY_PATH at process start, so both
# the bundled MuJoCo bin and the local OSMesa library must be set here.
MUJOCO_PY_BIN="$GATE_B_ROOT/.venv/lib/python3.9/site-packages/mujoco_py/binaries/linux/mujoco210/bin"
export MUJOCO_PY_MUJOCO_PATH="$GATE_B_ROOT/.venv/lib/python3.9/site-packages/mujoco_py/binaries/linux/mujoco210"
# The 580 driver installs libcuda.so.1 but no unversioned libcuda.so; cuDNN
# dlopens the unversioned name. Provide a workspace-local symlink (no system
# file is modified) and put it first on the loader path.
mkdir -p "$GATE_B_ROOT/.cuda_compat"
ln -sfn /usr/lib/x86_64-linux-gnu/libcuda.so.1 "$GATE_B_ROOT/.cuda_compat/libcuda.so"
export LD_LIBRARY_PATH="$GATE_B_ROOT/.cuda_compat:$MUJOCO_PY_BIN:$GATE_B_ROOT/.mesa/usr/lib/x86_64-linux-gnu"
export CPATH="$GATE_B_ROOT/.mesa/usr/include${CPATH:+:$CPATH}"
export LIBRARY_PATH="$MUJOCO_PY_BIN:$GATE_B_ROOT/.mesa/usr/lib/x86_64-linux-gnu${LIBRARY_PATH:+:$LIBRARY_PATH}"
export MUJOCO_PY_FORCE_CPU=1
# The OSMesa/LLVM stack needs the system libstdc++ (GLIBCXX_3.4.30); the
# extension build adds an Anaconda rpath with an older libstdc++, so preload
# the system copy before that search path is consulted.
export LD_PRELOAD="/usr/lib/x86_64-linux-gnu/libstdc++.so.6${LD_PRELOAD:+:$LD_PRELOAD}"
export PATH="$GATE_B_ROOT/.venv/bin:$PATH"

# Workspace construction imports wandb; never open a network run.
export WANDB_MODE=offline
export WANDB_SILENT=true
