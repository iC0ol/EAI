"""Extract only quota-error facts from this task's private local transcript."""
import datetime
import hashlib
import json
import os
from pathlib import Path

from d_alignment.io import ROOT, read_json, write_json

thread_id = os.environ["CODEX_THREAD_ID"]
matches = list(Path("/home/asus/.codex/sessions/2026/10/22").glob(f"*{thread_id}*.jsonl"))
assert len(matches) == 1
snapshots, failures = [], []
for line in matches[0].open():
    item = json.loads(line)
    timestamp = item.get("timestamp", "")
    if timestamp > "2026-10-22T15:35:00Z":
        continue
    payload = item.get("payload", {})
    if not isinstance(payload, dict):
        continue
    rate = payload.get("rate_limits") or {}
    if payload.get("type") == "token_count" and rate.get("limit_id") == "codex":
        snapshots.append({"timestamp_utc": timestamp, "primary": rate.get("primary"), "secondary": rate.get("secondary")})
    error = payload.get("error") or {}
    if payload.get("type") == "task_complete" and error.get("codex_error_info") == "usage_limit_exceeded":
        failures.append({"timestamp_utc": timestamp, "event": "task_complete",
                         "error_code": error["codex_error_info"],
                         "last_agent_message_present": payload.get("last_agent_message") is not None,
                         "source_event_sha256": hashlib.sha256(line.encode()).hexdigest()})
assert failures
last = failures[-1]
snapshot = [s for s in snapshots if s["timestamp_utc"] <= last["timestamp_utc"]][-1]
assert snapshot["primary"]["used_percent"] == 100
interruption = read_json(ROOT / "reports/gate1/interruption.json")
report = {
    "observed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "source": "Same task's local rollout JSONL; raw messages, account identifiers and credentials are not exported.",
    "last_quota_snapshot_before_agent_stop": snapshot,
    "agent_stop": last,
    "agent_turn_ended_due_to_usage_limit": True,
    "training_last_metric_utc": interruption["metrics_last_modified_utc"],
    "training_process_direct_termination_cause_established": False,
    "interpretation": "Quota exhaustion explicitly ended the agent turn. Local training kept progressing afterward; no exit code/traceback establishes how it later terminated.",
    "current_usage_check": {"source": "Codex get_usage_limits at continuation start, 2026-10-23 00:52 Asia/Shanghai", "five_hour_remaining_percent": 91, "weekly_remaining_percent": 67, "ordinary_usage_allowed": True, "reset_credit_consumed": False},
    "official_documentation": "https://learn.chatgpt.com/docs/pricing#what-happens-when-you-hit-usage-limits",
    "documentation_scope": "Current docs allow continuing active turns subject to fair use; they do not diagnose this historical local-process exit.",
}
kernel = ROOT / ".cache/kernel_interruption_window.txt"
if kernel.exists():
    report["kernel_journal_check"] = {
        "window_local": "2026-10-22 23:15:00 to 23:35:00 Asia/Shanghai",
        "result": kernel.read_text().strip() if kernel.read_text().strip() == "-- No entries --" else "See local diagnostic; raw system journal is not exported.",
        "scope": "No retained entries were returned. This cannot establish or exclude OOM/driver faults.",
    }
write_json(ROOT / "reports/gate1/interruption_diagnosis.json", report)
print(json.dumps(report, indent=2))
