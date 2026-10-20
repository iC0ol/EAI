#!/usr/bin/env bash
# Optional rebuild in THIS project. Does not touch conda/base/system/site packages.
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
export UV_CACHE_DIR="$task_root/.cache/uv"
export UV_PYTHON_INSTALL_DIR="$task_root/.runtime/python"
export UV_PYTHON_BIN_DIR="$task_root/.tools/bin"
export TMPDIR="$task_root/.cache/tmp"
mkdir -p "$TMPDIR" reports/logs
if [ ! -x .tools/bin/uv ]; then
  /usr/bin/python3 -m pip install --isolated --target "$task_root/.tools" --cache-dir "$task_root/.cache/pip" uv==0.13.3
fi
.tools/bin/uv python install 3.11.17 --no-bin --no-config
if [ ! -x .venv/bin/python ]; then
  .tools/bin/uv venv --python 3.11.17 --no-config .venv
fi
.tools/bin/uv pip sync --python .venv/bin/python --require-hashes --no-config requirements.lock
.tools/bin/uv pip check --python .venv/bin/python
