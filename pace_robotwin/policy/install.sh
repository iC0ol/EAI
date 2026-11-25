#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/env.sh"

if [[ ! -d "$POLICY_SOURCE/.git" ]]; then
    git clone --depth 1 https://github.com/niejunnan25/Openpi-PACE.git "$POLICY_SOURCE"
fi
if [[ "$(git -C "$POLICY_SOURCE" rev-parse HEAD)" != "$POLICY_REVISION" ]]; then
    git -C "$POLICY_SOURCE" fetch --depth 1 origin "$POLICY_REVISION"
    git -C "$POLICY_SOURCE" checkout --detach FETCH_HEAD
fi

uv="$POLICY_RUNTIME/bootstrap/bin/uv"
if [[ ! -x "$uv" ]]; then
    PIP_CONFIG_FILE=/dev/null PIP_DISABLE_PIP_VERSION_CHECK=1 python3 -m pip install \
        --index-url https://pypi.org/simple --target "$POLICY_RUNTIME/bootstrap" uv==0.9.30
fi
"$uv" python install --no-bin 3.11.14

# LeRobot is pinned in uv.lock. Leave LFS pointers untouched without installing Git LFS.
export GIT_LFS_SKIP_SMUDGE=1
export GIT_CONFIG_COUNT=3
export GIT_CONFIG_KEY_0=filter.lfs.process GIT_CONFIG_VALUE_0=
export GIT_CONFIG_KEY_1=filter.lfs.smudge GIT_CONFIG_VALUE_1=cat
export GIT_CONFIG_KEY_2=filter.lfs.required GIT_CONFIG_VALUE_2=false
export UV_HTTP_TIMEOUT=180
cd "$POLICY_SOURCE"
# The upstream model import path imports pytest from its locked dev group.
"$uv" sync --locked --python 3.11.14
