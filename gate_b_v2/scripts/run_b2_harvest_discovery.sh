#!/usr/bin/env bash
# Formal B2 discovery state harvesting. Requires separate researcher authorization.
# Discovery and confirmation are separate invocations by protocol design.
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "Usage: $0 RUN_DIR" >&2
  exit 2
fi
RUN_DIR="$1"
source "$(dirname "$0")/gateb_env.sh"
cd "$GATE_B_ROOT"
python -m gate_b_v2.cli b2-harvest --split discovery --run-dir "$RUN_DIR"
