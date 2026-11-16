#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/gateb_env.sh"
cd "$GATE_B_ROOT"
python -m gate_b_v2.cli audit "$@"
