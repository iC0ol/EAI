#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
unset PYTHONHOME LD_LIBRARY_PATH ROS_DISTRO ROS_VERSION ROS_PYTHON_VERSION AMENT_PREFIX_PATH COLCON_PREFIX_PATH CMAKE_PREFIX_PATH CUDA_HOME CUDA_PATH
export PYTHONPATH="$task_root/src"
export PYTHONNOUSERSITE=1
export HF_HOME="$task_root/.cache/vlm/huggingface"
export XDG_CACHE_HOME="$task_root/.cache/vlm"
export TMPDIR="$task_root/.cache/vlm/tmp"
export TOKENIZERS_PARALLELISM=false
export USE_TF=0 USE_FLAX=0
export CUBLAS_WORKSPACE_CONFIG=:4096:8
mkdir -p "$TMPDIR" reports/phase3/logs
case "${1:-}" in
  download)
    export HF_HUB_DISABLE_XET=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1
    .venv-vlm/bin/python scripts/download_vlm.py 2>&1 | tee reports/phase3/logs/download.log
    ;;
  single|three|core)
    export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
    .venv-vlm/bin/python -m spatial_pilot.infer_vlm --stage "$1" 2>&1 | tee "reports/phase3/logs/inference_$1.log"
    ;;
  *) echo 'Usage: bash scripts/run_vlm.sh [download|single|three|core]' >&2; exit 2 ;;
esac
