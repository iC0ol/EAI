#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/env.sh"

if [[ "$(git -C "$POLICY_SOURCE" rev-parse HEAD)" != "$POLICY_REVISION" ]]; then
    printf '%s\n' "Openpi-PACE must be at $POLICY_REVISION" >&2
    exit 1
fi

install -m 0644 "$POLICY_ASSETS/tokenizer.model" "$OPENPI_DATA_HOME/big_vision/paligemma_tokenizer.model"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export JAX_PLATFORMS=cuda
export XLA_PYTHON_CLIENT_PREALLOCATE=false
export HF_HUB_OFFLINE=1
cd "$POLICY_SOURCE"
exec "$UV_PROJECT_ENVIRONMENT/bin/python" "$POLICY_DIR/serve_policy.py" "$@"
