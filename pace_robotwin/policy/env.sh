#!/usr/bin/env bash

POLICY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
POLICY_ROOT="${POLICY_DIR%/policy}"
POLICY_RUNTIME="$POLICY_ROOT/runtime/policy"
POLICY_SOURCE="$POLICY_ROOT/vendor/Openpi-PACE"
POLICY_ASSETS="$POLICY_ROOT/assets/policy"
POLICY_REVISION=ba9876639cb7a4bf0c7db00ec39eeb9c8efd8b12

mkdir -p "$POLICY_RUNTIME"/{tmp,cache,cuda-cache,openpi-cache/big_vision}
export TMPDIR="$POLICY_RUNTIME/tmp"
export XDG_CACHE_HOME="$POLICY_RUNTIME/cache"
export UV_CACHE_DIR="$POLICY_RUNTIME/uv-cache"
export UV_PYTHON_INSTALL_DIR="$POLICY_RUNTIME/uv-python"
export UV_PYTHON_BIN_DIR="$POLICY_RUNTIME/bootstrap/bin"
export UV_PROJECT_ENVIRONMENT="$POLICY_RUNTIME/venv"
export PIP_CACHE_DIR="$POLICY_RUNTIME/pip-cache"
export HF_HOME="$POLICY_RUNTIME/huggingface"
export HF_HUB_CACHE="$HF_HOME/hub"
export HF_XET_CACHE="$HF_HOME/xet"
export HF_LEROBOT_HOME="$HF_HOME/lerobot"
export OPENPI_DATA_HOME="$POLICY_RUNTIME/openpi-cache"
export JAX_COMPILATION_CACHE_DIR="$POLICY_RUNTIME/jax-cache"
export CUDA_CACHE_PATH="$POLICY_RUNTIME/cuda-cache"
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1
