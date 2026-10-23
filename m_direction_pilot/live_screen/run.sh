#!/usr/bin/env bash
set -euo pipefail
LIVE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
M_ROOT="$(cd -- "$LIVE_ROOT/.." && pwd)"
D_ROOT="$(cd -- "$M_ROOT/../d_alignment_pilot" && pwd)"
unset PYTHONHOME
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$LIVE_ROOT/src:$M_ROOT/src:$D_ROOT/external/robomimic-7c66e7a41b5d9dcc905b1a68346bfee1b49b79c9:$D_ROOT/external/robosuite-51cc01785bab80ffeed20da15e67d7dd4140e76a:$D_ROOT/external/diffusion_policy-5ba07ac6661db573af695b419a7947ecb704690f"
export XDG_CACHE_HOME="$LIVE_ROOT/.cache" TMPDIR="$LIVE_ROOT/.cache/tmp"
export NUMBA_CACHE_DIR="$LIVE_ROOT/.cache/numba" MPLCONFIGDIR="$LIVE_ROOT/.cache/matplotlib"
export HF_HOME="$LIVE_ROOT/.cache/huggingface" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export WANDB_MODE=disabled WANDB_DISABLED=true MUJOCO_GL=egl
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 NUMBA_NUM_THREADS=2
export CUBLAS_WORKSPACE_CONFIG=:4096:8
mkdir -p "$TMPDIR" "$NUMBA_CACHE_DIR"
exec "$D_ROOT/.venv/bin/python" "$@"
