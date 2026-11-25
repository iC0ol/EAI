#!/usr/bin/env bash
# Source in a process dedicated to this RoboTwin client.
sim_source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PACE_SIM_ROOT="$(dirname -- "$sim_source_dir")"
export PACE_ROBOTWIN_ROOT="$PACE_SIM_ROOT/vendor/RoboTwin-PACE"
export PACE_SIM_RUNTIME="$PACE_SIM_ROOT/runtime/sim"
export PACE_SIM_PYTHON="$PACE_SIM_RUNTIME/venv/bin/python"

unset PYTHONHOME LD_LIBRARY_PATH
export PYTHONPATH="$PACE_ROBOTWIN_ROOT:$PACE_ROBOTWIN_ROOT/pace/src:$PACE_ROBOTWIN_ROOT/description/utils:$(dirname -- "$PACE_SIM_ROOT")"
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUTF8=1
export PIP_CONFIG_FILE=/dev/null
export PIP_CACHE_DIR="$PACE_SIM_RUNTIME/pip"
export TMPDIR="$PACE_SIM_RUNTIME/tmp"
export XDG_CACHE_HOME="$PACE_SIM_RUNTIME/cache"
export XDG_CONFIG_HOME="$PACE_SIM_RUNTIME/config"
export XDG_RUNTIME_DIR="$PACE_SIM_RUNTIME/xdg"
export CUDA_CACHE_PATH="$XDG_CACHE_HOME/cuda"
export WARP_CACHE_PATH="$XDG_CACHE_HOME/warp"
export TORCH_EXTENSIONS_DIR="$XDG_CACHE_HOME/torch_extensions"
export __GL_SHADER_DISK_CACHE_PATH="$XDG_CACHE_HOME/nvidia"
export HF_HOME="$XDG_CACHE_HOME/huggingface"
export MPLCONFIGDIR="$XDG_CACHE_HOME/matplotlib"
export CUDA_HOME=/usr/local/cuda-11.8
export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export PATH="$PACE_SIM_RUNTIME/venv/bin:$PATH"

mkdir -p -- "$PIP_CACHE_DIR" "$TMPDIR" "$XDG_CONFIG_HOME" "$CUDA_CACHE_PATH" "$WARP_CACHE_PATH" "$__GL_SHADER_DISK_CACHE_PATH"
mkdir -p -m 700 -- "$XDG_RUNTIME_DIR"
