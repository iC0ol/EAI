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
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
mkdir -p "$TMPDIR" reports/phase3_5/logs
case "${1:-}" in
  prepare) .venv/bin/python -m spatial_pilot.diagnostic_data 2>&1 | tee reports/phase3_5/logs/input_build.log ;;
  geometry) .venv/bin/python -m spatial_pilot.diagnostic_geometry 2>&1 | tee reports/phase3_5/logs/geometry_diagnostics.log ;;
  infer) .venv-vlm/bin/python -m spatial_pilot.diagnostic_infer 2>&1 | tee reports/phase3_5/logs/inference.log ;;
  evaluate) .venv/bin/python -m spatial_pilot.diagnostic_evaluate 2>&1 | tee reports/phase3_5/logs/evaluation.log ;;
  *) echo 'Usage: bash scripts/run_phase3_5.sh [prepare|geometry|infer|evaluate]' >&2; exit 2 ;;
esac
