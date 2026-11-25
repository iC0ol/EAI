#!/usr/bin/env bash
set -euo pipefail
sim_install_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$sim_install_dir/runtime.sh"

# The local Python 3.10 lacks ensurepip. Bootstrap pip into the venv only.
if ! "$PACE_SIM_PYTHON" -m pip --version >/dev/null 2>&1; then
    /usr/bin/python3.10 -m venv --without-pip "$PACE_SIM_RUNTIME/venv"
    curl --fail --silent --show-error --location --retry 3 https://bootstrap.pypa.io/get-pip.py \
        -o "$PACE_SIM_RUNTIME/get-pip.py"
    "$PACE_SIM_PYTHON" "$PACE_SIM_RUNTIME/get-pip.py" 'pip==25.3'
fi

"$PACE_SIM_PYTHON" -m pip install --timeout 120 --index-url https://download.pytorch.org/whl/cu118 \
    'torch==2.4.1+cu118' 'torchvision==0.19.1+cu118'

"$PACE_SIM_PYTHON" -m pip install --timeout 120 --find-links "$PACE_SIM_RUNTIME/wheels" \
    -r "$sim_install_dir/requirements.txt"
"$PACE_SIM_PYTHON" "$sim_install_dir/patch_runtime.py"
"$PACE_SIM_PYTHON" -m pip install --timeout 120 -e "$PACE_ROBOTWIN_ROOT/pace[robotwin]" \
    "$PACE_SIM_ROOT/vendor/Openpi-PACE/packages/openpi-client"

if [[ ! -d "$PACE_ROBOTWIN_ROOT/envs/curobo/.git" ]]; then
    GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 --branch v0.7.8 https://github.com/NVlabs/curobo.git \
        "$PACE_ROBOTWIN_ROOT/envs/curobo"
fi
[[ "$(git -C "$PACE_ROBOTWIN_ROOT/envs/curobo" rev-parse HEAD)" == d64c4b005459db10c5dd867d8b30a87d5bda9bdb ]]
TORCH_CUDA_ARCH_LIST=8.6 MAX_JOBS=2 "$PACE_SIM_PYTHON" -m pip install --timeout 120 \
    -e "$PACE_ROBOTWIN_ROOT/envs/curobo" --no-build-isolation
"$PACE_SIM_PYTHON" -m pip check
"$PACE_SIM_PYTHON" -m pip freeze >"$PACE_SIM_RUNTIME/installed.txt"
