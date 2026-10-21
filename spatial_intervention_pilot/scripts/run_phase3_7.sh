#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
unset PYTHONHOME LD_LIBRARY_PATH ROS_DISTRO ROS_VERSION ROS_PYTHON_VERSION AMENT_PREFIX_PATH COLCON_PREFIX_PATH CMAKE_PREFIX_PATH CUDA_HOME CUDA_PATH
export PYTHONPATH="$task_root/src"
export PYTHONNOUSERSITE=1
export HF_HOME="$task_root/.cache/phase3_7/huggingface"
export XDG_CACHE_HOME="$task_root/.cache/phase3_7"
export TMPDIR="$task_root/.cache/phase3_7/tmp"
export TOKENIZERS_PARALLELISM=false
export USE_TF=0 USE_FLAX=0
export CUBLAS_WORKSPACE_CONFIG=:4096:8
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
mkdir -p "$TMPDIR" reports/phase3_7/logs
case "${1:-}" in
  prepare) .venv/bin/python -m spatial_pilot.scale_scenes ;;
  smoke) .venv-vlm/bin/python -m spatial_pilot.scale_infer --model 8b --run smoke8b --datasets smoke ;;
  infer8b) .venv-vlm/bin/python -m spatial_pilot.scale_infer --model 8b --run vlm8b_a --datasets old16 new24 ;;
  infer4b) .venv-vlm/bin/python -m spatial_pilot.scale_infer --model 4b --run vlm4b_new --datasets new24 ;;
  rgb) .venv/bin/python -m spatial_pilot.scale_rgb_run ;;
  evaluate) .venv/bin/python -m spatial_pilot.scale_evaluate ;;
  *) echo 'Usage: run_phase3_7.sh prepare|smoke|infer8b|infer4b|rgb|evaluate' >&2;exit 2 ;;
esac
