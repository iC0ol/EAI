#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
export TZ=Asia/Shanghai

if (( $# < 1 || $# > 2 )); then
    printf 'Usage: %s RUN_DIR [SOURCE_RUN_DIR]\n' "$0" >&2
    exit 2
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
project_root="$(cd -- "$script_dir/../.." && pwd -P)"
run_dir="$(realpath -e -- "$1")"
source_dir="${2:-$project_root/runs/b2_confirmation_20261118T110331}"
prefix="$run_dir/b2_continuation_h4_"
worker_pid=
gpu_pid=

log() {
    printf '[%s] %s\n' "$(date --iso-8601=seconds)" "$*"
}

finish() {
    local exit_code="$1"
    if [[ -n "$worker_pid" ]]; then
        kill -TERM "$worker_pid" 2>/dev/null || true
        wait "$worker_pid" || true
    fi
    if [[ -n "$gpu_pid" ]]; then
        kill -TERM "$gpu_pid" 2>/dev/null || true
        wait "$gpu_pid" 2>/dev/null || true
    fi
    log "LAUNCHER_END exit_code=$exit_code"
}

if [[ "$(dirname -- "$run_dir")" != "$project_root/runs" || "$(basename -- "$run_dir")" != b2_continuation_h4_* ]]; then
    log "BLOCKED invalid diagnostic run directory"
    exit 2
fi
if ! (set -o noclobber; printf '%s\n' "$$" > "${prefix}launcher.pid"); then
    log "BLOCKED run directory already reserved by a launcher"
    exit 1
fi
trap 'finish "$?"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

log "LAUNCHER_START pid=$$ run_dir=$run_dir"
cd -- "$project_root"
test -x .venv/bin/python
source scripts/gateb_env.sh

nvidia-smi --query-gpu=timestamp,name,driver_version,pstate,temperature.gpu,utilization.gpu,memory.used,power.draw,clocks.sm \
    --format=csv --loop=30 > "${prefix}gpu.csv" 2> "${prefix}gpu.stderr.log" &
gpu_pid=$!
log "GPU_MONITOR pid=$gpu_pid interval_s=30"

python -u -B "$script_dir/run_b2_continuation_h4.py" --source-run-dir "$source_dir" --run-dir "$run_dir" &
worker_pid=$!
printf '%s\n' "$worker_pid" > "${prefix}worker.pid"
log "DIAGNOSTIC_WORKER pid=$worker_pid"
exit_code=0
wait "$worker_pid" || exit_code=$?
worker_pid=
log "DIAGNOSTIC_WORKER_END exit_code=$exit_code"
exit "$exit_code"
