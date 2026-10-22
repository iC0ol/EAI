"""Single detached local supervisor; no automatic retries or extra training."""
import datetime
import json
import os
import subprocess

from d_alignment.io import ROOT, read_json, write_json

auth = read_json(ROOT / "data/manifests/retry_authorization.json")
assert auth["overall_attempt_number"] == 7 and auth["authorized_additional_training_attempts"] == 1
path = ROOT / "outputs/gate1/retry_status.json"
assert not path.exists(), "Retry supervisor already started; do not duplicate"
status = {"state": "running", "phase": "training", "run": auth["retry_run"],
          "overall_attempt_number": 7, "supervisor_pid": os.getpid(),
          "started_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
write_json(path, status)
try:
    for phase, module in [("training", "d_alignment.train"), ("evaluation", "d_alignment.evaluate")]:
        status["phase"] = phase
        write_json(path, status)
        log = ROOT / "reports/gate1/logs" / f"{'train' if phase == 'training' else 'eval'}_larger_lag_seed43_retry1.txt"
        args = ["bash", str(ROOT / "scripts/run.sh"), "-m", module, "--condition", "larger_lag", "--seed", "43"]
        with log.open("x") as output:
            child = subprocess.Popen(args, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT)
            status.update(child_pid=child.pid, command=args)
            write_json(path, status)
            rc = child.wait()
        status[phase + "_exit_code"] = rc
        write_json(path, status)
        if rc:
            raise RuntimeError(f"{phase} exited with code {rc}; no automatic retry")
    status.update(state="completed", phase="done", finished_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
except BaseException as exc:
    status.update(state="failed", error=repr(exc), finished_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    raise
finally:
    write_json(path, status)
    print(json.dumps(status), flush=True)
