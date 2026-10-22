"""Read-only compact status of the bounded pipeline."""
import json

from d_alignment.io import ROOT, read_json

retry = ROOT / "outputs/gate1/retry_status.json"
path = retry if retry.exists() else ROOT / "outputs/gate1/pipeline_status.json"
state = read_json(path) if path.exists() else {"state": "not_started"}
result = {k: state[k] for k in ("state", "phase", "run", "error") if k in state}
name = state.get("run", "")
run = ROOT / "outputs/gate1" / name
if state.get("phase") == "training" and (run / "metrics.jsonl").exists():
    lines = (run / "metrics.jsonl").read_text().splitlines()
    records = []
    for line in lines:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    if records:
        result.update(update=records[-1]["update"], train_mse=round(records[-1]["train_noise_mse"], 5))
elif state.get("phase") == "evaluation" and (run / "evaluation.jsonl").exists():
    records = []
    for line in (run / "evaluation.jsonl").read_text().splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    result.update(episodes=len(records), successes=sum(r["success"] for r in records))
print(json.dumps(result))
