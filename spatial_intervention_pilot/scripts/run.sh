#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
# These changes apply only to this child shell, never the user's ROS shell.
unset PYTHONHOME LD_LIBRARY_PATH ROS_DISTRO ROS_VERSION ROS_PYTHON_VERSION AMENT_PREFIX_PATH COLCON_PREFIX_PATH CMAKE_PREFIX_PATH CUDA_HOME CUDA_PATH
export PYTHONPATH="$task_root/src"
export PYTHONNOUSERSITE=1
export MPLBACKEND=Agg
export MPLCONFIGDIR="$task_root/.cache/matplotlib"
export XDG_CACHE_HOME="$task_root/.cache"
export UV_CACHE_DIR="$task_root/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$task_root/.runtime/python"
export TMPDIR="$task_root/.cache/tmp"
export HF_HOME="$task_root/.cache/huggingface"
mkdir -p "$TMPDIR" reports/logs
case "${1:-all}" in
  core)
    .venv/bin/python -m pytest tests/test_oracle.py -k test_core_six -v --junitxml=reports/core_tests.xml --basetemp="$task_root/.cache/pytest-core" 2>&1 | tee reports/logs/core_tests.log
    ;;
  generate)
    .venv/bin/python -m spatial_pilot.make_dataset --config configs/pilot.yaml --output . 2>&1 | tee reports/logs/generation.log
    ;;
  test)
    .venv/bin/python -m pytest -v --junitxml=reports/tests.xml --basetemp="$task_root/.cache/pytest-full" 2>&1 | tee reports/logs/tests.log
    ;;
  reproduce)
    .venv/bin/python scripts/check_reproducibility.py 2>&1 | tee reports/logs/reproducibility.log
    ;;
  resolution)
    .venv/bin/python scripts/check_resolution.py 2>&1 | tee reports/logs/resolution.log
    ;;
  reports)
    .venv/bin/python scripts/build_reports.py
    ;;
  all)
    bash scripts/run.sh core
    bash scripts/run.sh generate
    bash scripts/run.sh test
    bash scripts/run.sh reproduce
    bash scripts/run.sh resolution
    bash scripts/run.sh reports
    ;;
  *) echo 'Usage: bash scripts/run.sh [all|core|generate|test|reproduce|resolution|reports]' >&2; exit 2 ;;
esac
