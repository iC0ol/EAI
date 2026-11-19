#!/usr/bin/env bash
# Formal B2 discovery branch execution. Requires a completed discovery harvest
# in RUN_DIR and separate researcher authorization.
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "Usage: $0 RUN_DIR" >&2
  exit 2
fi
RUN_DIR="$1"
source "$(dirname "$0")/gateb_env.sh"
cd "$GATE_B_ROOT"
python -m gate_b_v2.cli b2 --split discovery --run-dir "$RUN_DIR"
