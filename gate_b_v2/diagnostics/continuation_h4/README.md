# B2 Confirmation Continuation-h4

This post-hoc diagnostic pairs 450 new branches with the completed Square-MH Confirmation branches. It loads the same 30 snapshots in the original state, repeat and randomized horizon order. The first commitment is still one of 1, 2, 4, 8 and 15. Each subsequent query executes at most four fresh actions through the same policy, observation and action interfaces. The episode step limit includes the steps before the snapshot.

The runner verifies the accepted Confirmation raw checksum list, original authorization, frozen B2 runtime and all 30 snapshot references before loading the simulator. It uses the frozen snapshot recheck on the live environment before the first diagnostic branch. Each branch checks and restores the original snapshot, resets the policy and uses the original seed rule indexed by policy call. Different continuation lengths can change the number and timing of policy calls.

## Workstation commands

From the Gate B project directory, use the existing isolated environment.

```bash
source scripts/gateb_env.sh
python -B -m pytest -q tests diagnostics/continuation_h4
python -u -B diagnostics/continuation_h4/run_b2_continuation_h4.py --check-source
bash -n diagnostics/continuation_h4/launch_b2_continuation_h4.sh
```

An authorized launch uses a fresh directory under `runs/`.

```bash
RUN_DIR="$PWD/runs/b2_continuation_h4_$(TZ=Asia/Shanghai date +%Y%m%dT%H%M%S)"
mkdir -m 700 -- "$RUN_DIR"
nohup setsid bash diagnostics/continuation_h4/launch_b2_continuation_h4.sh "$RUN_DIR" \
    > "$RUN_DIR/b2_continuation_h4_launcher.log" 2>&1 < /dev/null &
```

The launcher records its PID, the worker PID, a diagnostic log and 30-second GPU samples. The status JSON records the current stage and the count of validated branches. If a gate or rollout fails, the operator can inspect the failure and any partial records in that directory.

The integrity JSON ties the complete 450-row stream to the diagnostic manifest, live snapshot recheck and original Confirmation hashes. Use `first_horizon` for the diagnostic and `horizon` for the original when pairing on state, first horizon and repeat index. The two branches share the initial snapshot and call-index seed rule.
