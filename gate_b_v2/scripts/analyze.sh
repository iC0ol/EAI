#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 1 ]]; then echo "Usage: $0 RUN_DIR" >&2; exit 2; fi
RUN_DIR="$1"
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
python -m gate_b_v2.cli analyze --run-dir "$RUN_DIR"
