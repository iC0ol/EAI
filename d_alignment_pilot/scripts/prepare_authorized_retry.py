"""Archive the interrupted attempt and record one human-authorized retry.

All frozen scientific inputs and the original train/evaluate implementation stay
unchanged. The archive preserves attempt count; this is attempt seven overall.
"""
import datetime
import shutil

from d_alignment.io import ROOT, read_json, sha256, write_json

name = "larger_lag_seed43"
source = ROOT / "outputs/gate1" / name
archive = ROOT / "outputs/gate1/interrupted_attempts" / f"{name}_attempt1"
authorization = ROOT / "data/manifests/retry_authorization.json"
assert not authorization.exists() and not archive.exists()
metadata = read_json(source / "run.json")
assert metadata["status"] == "interrupted" and metadata["updates_completed"] == 42400
assert metadata["condition"] == "larger_lag" and metadata["seed"] == 43
assert len(list((ROOT / "outputs/gate1").glob("*/run.json"))) == 6
assert not (ROOT / "outputs/gate1/checkpoints" / f"{name}.pt").exists()
assert not (source / "evaluation.jsonl").exists()
frozen = read_json(ROOT / "data/manifests/frozen_protocol.json")
for path, expected in {**frozen["files"], **frozen["data_manifests"]}.items():
    assert sha256(ROOT / path) == expected, path
files = {str(p.relative_to(source)): sha256(p) for p in source.rglob("*") if p.is_file()}
assert set(files) == {"run.json", "metrics.jsonl"}
archive.parent.mkdir(parents=True, exist_ok=True)
shutil.move(str(source), str(archive))
for path, expected in files.items():
    assert sha256(archive / path) == expected
record = {
    "recorded_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "human_instruction": "Larger-Lag阶段seed43重新训练 然后按新得出的结论重新push 可能是额度的问题导致中断 检查一下",
    "previous_public_result_commit": "9e481355caa0f3136100b18e087753aed61e294d",
    "condition": "larger_lag", "seed": 43, "authorized_additional_training_attempts": 1,
    "overall_attempt_number": 7, "maximum_total_attempts_after_authorization": 7,
    "retry_run": name, "start_from": "original seed initialization, not partial weights",
    "archived_attempt": str(archive.relative_to(ROOT)), "archived_files_sha256": files,
    "frozen_protocol_sha256": sha256(ROOT / "data/manifests/frozen_protocol.json"),
    "config_sha256": sha256(ROOT / "configs/gate1.json"),
    "train_code_sha256": sha256(ROOT / "src/d_alignment/train.py"),
    "evaluation_code_sha256": sha256(ROOT / "src/d_alignment/evaluate.py"),
    "scientific_inputs_changed": False, "test_seeds_changed": False,
    "step_d_threshold_changed": False,
    "budget_handling": "Frozen train guard counts active run slots. Archiving the interrupted slot allows its sole authorized replacement; archive remains counted as attempt six, replacement as attempt seven.",
    "selection": "Use the only completed final EMA for this seed; never compare/select multiple completed replacements.",
    "scope": "One replacement training and the same 50 full 400-step trials; reapply original Gate 1 decisions, no posterior-policy training.",
}
write_json(authorization, record)
print(record["archived_attempt"])
print("Recorded human-authorized attempt 7; all 29 frozen inputs unchanged")
