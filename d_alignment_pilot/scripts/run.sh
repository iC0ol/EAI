#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$TASK_ROOT"
unset PYTHONHOME
export PYTHONNOUSERSITE=1
export PYTHONPATH="$TASK_ROOT/src:$TASK_ROOT/external/robomimic-7c66e7a41b5d9dcc905b1a68346bfee1b49b79c9:$TASK_ROOT/external/robosuite-51cc01785bab80ffeed20da15e67d7dd4140e76a:$TASK_ROOT/external/diffusion_policy-5ba07ac6661db573af695b419a7947ecb704690f"
export XDG_CACHE_HOME="$TASK_ROOT/.cache"
mkdir -p "$TASK_ROOT/.cache/tmp"
export TMPDIR="$TASK_ROOT/.cache/tmp"
export HF_HOME="$TASK_ROOT/.cache/huggingface"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export WANDB_MODE=disabled
export WANDB_DISABLED=true
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
export OPENBLAS_NUM_THREADS=2
export NUMBA_NUM_THREADS=2
export NUMBA_CACHE_DIR="$TASK_ROOT/.cache/numba"
export MUJOCO_GL=egl
export MPLCONFIGDIR="$TASK_ROOT/.cache/matplotlib"
exec "$TASK_ROOT/.venv/bin/python" "$@"
