#!/usr/bin/env bash
set -euo pipefail
umask 077
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$project_dir"
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 TZ=Asia/Shanghai
mode="${1:-status}"
shift || true
case "$mode" in
    engineer|start)
        stage=engineering
        if [[ "$mode" == start ]]; then
            stage=formal
            [[ -f "$project_dir/runs/ACCEPTED.json" ]]
        fi
        unit="eai-pace-$stage.service"
        if systemctl --user is-active --quiet "$unit"; then
            echo "Existing PACE $stage service is active."
            exit 0
        fi
        exec systemd-run --user --collect --unit="$unit" \
            --description="Paired RoboTwin PACE $stage" --property="WorkingDirectory=$project_dir" \
            --property=Restart=on-failure --property=RestartSec=90s --property=StartLimitBurst=2 \
            --property=StartLimitIntervalSec=1800s --property=TimeoutStopSec=45s \
            /bin/bash "$project_dir/run.sh" worker "$stage"
        ;;
    worker|status|accept)
        if [[ "$mode" == worker ]]; then mode="$1"; fi
        exec /usr/bin/python3 -B "$project_dir/supervise.py" "$mode"
        ;;
    trial|audit)
        source "$project_dir/sim/runtime.sh"
        exec "$PACE_SIM_PYTHON" -u -B "$project_dir/$mode.py" "$@"
        ;;
    warmup)
        source "$project_dir/policy/env.sh"
        exec "$UV_PROJECT_ENVIRONMENT/bin/python" -u -B "$project_dir/policy/probe_policy.py" "$@"
        ;;
    *) echo "Unknown PACE command $mode" >&2; exit 2 ;;
esac
