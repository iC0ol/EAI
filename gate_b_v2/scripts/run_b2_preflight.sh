#!/usr/bin/env bash
# PREFLIGHT only: live geometry audit + reserved-seed snapshot/replay validation.
# This never writes B2 discovery/confirmation manifests and must not be reported
# as a scientific B2 result.
set -euo pipefail
if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 RUN_DIR [SMOKE_SEEDS_CSV]" >&2
  exit 2
fi
RUN_DIR="$1"
SMOKE_ARGS=()
if [[ $# -eq 2 ]]; then
  SMOKE_ARGS=(--smoke-seeds "$2")
fi
source "$(dirname "$0")/gateb_env.sh"
cd "$GATE_B_ROOT"
python -m gate_b_v2.cli b2-preflight \
  --run-dir "$RUN_DIR" --seed 299999 --fallback-step 500 "${SMOKE_ARGS[@]}"
