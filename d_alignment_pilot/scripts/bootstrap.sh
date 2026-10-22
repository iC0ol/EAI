#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$TASK_ROOT"
mkdir -p external .cache/tmp data/raw reports/gate1/logs
unset PYTHONPATH PYTHONHOME
export PYTHONNOUSERSITE=1
export PIP_CACHE_DIR="$TASK_ROOT/.cache/pip"
export TMPDIR="$TASK_ROOT/.cache/tmp"
if [[ ! -x .venv/bin/python ]]; then
    /home/asus/anaconda3/bin/python -m venv .venv
fi
.venv/bin/python -m pip install pip==25.3 setuptools==75.8.0 wheel==0.45.1
.venv/bin/python -m pip install torch==2.2.2+cu121 torchvision==0.17.2+cu121 --index-url https://download.pytorch.org/whl/cu121
if [[ -f requirements.lock ]]; then
    .venv/bin/python -m pip install --index-url https://pypi.org/simple --extra-index-url https://download.pytorch.org/whl/cu121 -r requirements.lock
else
    .venv/bin/python -m pip install --index-url https://pypi.org/simple -r requirements.in
fi
while read -r repo revision; do
    name="${repo##*/}"
    if [[ ! -d "external/$name-$revision" ]]; then
        curl -fL --retry 2 "https://codeload.github.com/$repo/tar.gz/$revision" -o ".cache/$name.tar.gz"
        tar xzf ".cache/$name.tar.gz" -C external
    fi
done <<'SOURCES'
ARISE-Initiative/robomimic 7c66e7a41b5d9dcc905b1a68346bfee1b49b79c9
ARISE-Initiative/robosuite 51cc01785bab80ffeed20da15e67d7dd4140e76a
real-stanford/diffusion_policy 5ba07ac6661db573af695b419a7947ecb704690f
SOURCES
if [[ ! -f data/raw/square_ph_low_dim_v15.hdf5 ]]; then
    curl -fL --retry 2 https://huggingface.co/datasets/robomimic/robomimic_datasets/resolve/74fa018461f479cd9fd15b924a16103012096203/v1.5/square/ph/low_dim_v15.hdf5 -o data/raw/square_ph_low_dim_v15.hdf5
fi
printf '%s\n' '45d8cabb6d57a4c03e839aa5e4b3e58fb60fe8bd20e1951fec563a2abfd14951  data/raw/square_ph_low_dim_v15.hdf5' | sha256sum -c -
if [[ ! -f requirements.lock ]]; then
    .venv/bin/python -m pip freeze > requirements.lock
fi
.venv/bin/python -m pip freeze > reports/gate1/logs/installed_packages.txt
