#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 1 ]]; then echo "Usage: $0 RUN_DIR [analyze args...]" >&2; exit 2; fi
RUN_DIR="$1"; shift
source "$(dirname "$0")/gateb_env.sh"
cd "$GATE_B_ROOT"
python -m gate_b_v2.cli analyze --run-dir "$RUN_DIR" "$@"
