"""Record immutable preregistration inputs, source evidence and code hashes."""
import subprocess

from d_alignment.io import ROOT, read_json, sha256, write_json

target = ROOT / "data/manifests/frozen_protocol.json"
assert not target.exists(), "Protocol has already been frozen"
assert (ROOT / "data/manifests/eval_initial_conditions.json").exists()
audit = read_json(ROOT / "reports/gate1/data_audit.json")
assert audit["raw_action_replay"]["success"], "Clean recorded actions did not succeed; inspect environment first"
assert max(audit["next_obs_to_following_obs_max_abs"].values()) < 1e-8
for checks in audit["state_restore_max_abs"].values():
    assert max(v for k, v in checks.items() if k != "object") < 1e-4
cache_check = read_json(ROOT / "reports/gate1/observation_cache_summary.json")
assert max(ep["absolute_object_max"] for ep in cache_check.values()) < 1e-8
paths = sorted(list((ROOT / "configs").glob("*")) + list((ROOT / "src").rglob("*.py")) + list((ROOT / "scripts").glob("*.py")) + list((ROOT / "scripts").glob("*.sh")) + list((ROOT / "tests").glob("*.py")) + [ROOT / "reports/gate1/experiment_protocol.md", ROOT / "requirements.lock"])
manifest_paths = [p for p in (ROOT / "data/manifests").glob("*.json") if p != target]
record = {"git_parent": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "files": {str(p.relative_to(ROOT)): sha256(p) for p in paths},
    "data_manifests": {str(p.relative_to(ROOT)): sha256(p) for p in sorted(manifest_paths)},
    "status": "frozen before first optimizer update"}
write_json(target, record)
print(f"Froze {len(paths)} code/config/protocol files and {len(manifest_paths)} manifests")
