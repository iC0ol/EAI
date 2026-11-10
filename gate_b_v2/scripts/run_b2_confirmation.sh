#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 1 ]]; then echo "Usage: $0 RUN_DIR [other CLI args...]" >&2; exit 2; fi
RUN_DIR="$1"; shift
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
python -m gate_b_v2.cli b2 --split confirmation --run-dir "$RUN_DIR" "$@"
