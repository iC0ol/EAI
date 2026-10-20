#!/usr/bin/env bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
unset PYTHONHOME PYTHONPATH LD_LIBRARY_PATH ROS_DISTRO AMENT_PREFIX_PATH COLCON_PREFIX_PATH
export UV_CACHE_DIR="$task_root/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$task_root/.runtime/python"
export TMPDIR="$task_root/.cache/vlm/tmp"
mkdir -p "$TMPDIR" reports/phase3/logs
if [ ! -x .venv-vlm/bin/python ]; then
  .tools/bin/uv venv --python 3.11.17 --no-config .venv-vlm
fi
.tools/bin/uv pip sync --python .venv-vlm/bin/python --require-hashes \
  --extra-index-url https://download.pytorch.org/whl/cu124 --index-strategy unsafe-best-match \
  --no-config requirements-vlm.lock
.tools/bin/uv pip check --python .venv-vlm/bin/python
