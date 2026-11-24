#!/usr/bin/env bash
set -euo pipefail
umask 077

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
gate_root="$(dirname -- "$project_dir")/gate_b_v2"
unit=eai-component-pilot.service
mode="${1:-status}"

case "$mode" in
    start)
        if systemctl --user is-active --quiet "$unit"; then
            printf '%s\n' "The existing pilot service is running."
            exit 0
        fi
        bash "$project_dir/run.sh" check-acceptance
        if [[ -f "$project_dir/runs/overnight/STATUS.json" ]] &&
            "$gate_root/.venv/bin/python" -IB -c 'import json,sys; sys.exit(json.load(open(sys.argv[1]))["state"] != "COMPLETE")' "$project_dir/runs/overnight/STATUS.json"; then
            exec bash "$project_dir/run.sh" verify
        fi
        exec systemd-run --user --collect --unit="$unit" \
            --description="Square-MH paired component-commitment pilot" \
            --property="WorkingDirectory=$project_dir" --property=Restart=on-failure \
            --property=RestartSec=45s --property=StartLimitBurst=3 \
            --property=StartLimitIntervalSec=900s --property=RestartPreventExitStatus=65 \
            /bin/bash "$project_dir/run.sh" worker
        ;;
    status)
        for stage in engineering overnight; do
            if [[ -f "$project_dir/runs/$stage/STATUS.json" ]]; then
                cat "$project_dir/runs/$stage/STATUS.json"
            fi
        done
        exit 0
        ;;
    worker|engineering|accept|verify|check-acceptance|test) ;;
    *) printf 'Unknown command %s\n' "$mode" >&2; exit 2 ;;
esac

runtime_dir="$project_dir/runs/runtime"
mkdir -p "$runtime_dir"/{cache,tmp,numba,wandb,cuda,matplotlib}
export TZ=Asia/Shanghai
unset PYTHONHOME
export PYTHONPATH="$(dirname -- "$project_dir"):$project_dir:$gate_root/src:$gate_root/third_party/diffusion_policy"
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
export GATE_B_ROOT="$gate_root"
export PATH="$gate_root/.venv/bin:$PATH"
export MUJOCO_PY_MUJOCO_PATH="$gate_root/.venv/lib/python3.9/site-packages/mujoco_py/binaries/linux/mujoco210"
export MUJOCO_PY_FORCE_CPU=1
export LD_LIBRARY_PATH="$gate_root/.cuda_compat:$MUJOCO_PY_MUJOCO_PATH/bin:$gate_root/.mesa/usr/lib/x86_64-linux-gnu"
export LD_PRELOAD="/usr/lib/x86_64-linux-gnu/libstdc++.so.6"
export CPATH="$gate_root/.mesa/usr/include"
export LIBRARY_PATH="$MUJOCO_PY_MUJOCO_PATH/bin:$gate_root/.mesa/usr/lib/x86_64-linux-gnu"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 LP_NUM_THREADS=3
export XDG_CACHE_HOME="$runtime_dir/cache" NUMBA_CACHE_DIR="$runtime_dir/numba"
export MPLCONFIGDIR="$runtime_dir/matplotlib" CUDA_CACHE_PATH="$runtime_dir/cuda"
export TMPDIR="$runtime_dir/tmp" WANDB_DIR="$runtime_dir/wandb"
export WANDB_MODE=offline WANDB_SILENT=true
cd "$project_dir"
python_bin="$gate_root/.venv/bin/python"
case "$mode" in
    worker|engineering)
        stage=overnight
        if [[ "$mode" == engineering ]]; then stage=engineering; fi
        mkdir -p "runs/$stage"
        exec "$python_bin" -u -B study.py "$stage" >>"runs/$stage/worker.log" 2>&1
        ;;
    check-acceptance)
        exec "$python_bin" -B -c 'from study import audit_acceptance, digest, source_hashes; audit_acceptance(digest(source_hashes()))'
        ;;
    test)
        exec "$python_bin" -B -m pytest -q -p no:cacheprovider "$project_dir"
        ;;
    accept|verify)
        exec "$python_bin" -B study.py "$mode"
        ;;
esac
