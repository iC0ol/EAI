"""Pin execution inputs before the engineering and formal runs."""

import hashlib
import json
import subprocess

from design import CACHE_SHA, OPENPI_REVISION, POLICY_REVISION, ROOT, SIM, TASKS, UPSTREAM, file_hash, read_json


def command(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd)


def git_fingerprint(repo, revision):
    head = command("git", "rev-parse", "HEAD", cwd=repo).decode().strip()
    if head != revision:
        raise ValueError(f"{repo} is at {head}, expected {revision}")
    diff = command("git", "diff", "--binary", "HEAD", "--", cwd=repo)
    return {"commit": head, "tracked_diff_sha256": hashlib.sha256(diff).hexdigest(),
            "changed_tracked_paths": command("git", "diff", "--name-only", "HEAD", cwd=repo).decode().splitlines()}


def packages(python):
    script = (
        "import importlib.metadata as m,json,sys;"
        "print(json.dumps({'python':sys.version,'distributions':"
        "sorted((d.metadata['Name'],d.version) for d in m.distributions() if d.metadata['Name'])}))"
    )
    return json.loads(command(str(python), "-I", "-B", "-c", script))


def checked_files(base, entries):
    output = {}
    for item in entries:
        path = base / item["path"]
        if path.stat().st_size != item["bytes"] or file_hash(path) != item["sha256"]:
            raise ValueError(f"asset checksum failed: {path}")
        output[item["path"]] = item["sha256"]
    return output


def make_manifest():
    candidate = ROOT / "assets/policy"
    policy = read_json(candidate / "manifest.json")
    if file_hash(candidate / "manifest.json") != "2337bd9e7244fc3f6d51b0b830a9cdfc8d6e683decf2c398a431bc5800696c41":
        raise ValueError("official model manifest changed")
    if policy["openpi_pace_revision"] != OPENPI_REVISION:
        raise ValueError("official OpenPI commit does not match")
    released = {m["task"]: m for m in policy["models"]}
    entries = [policy["tokenizer"]]
    for task in TASKS:
        entries.extend(released[task]["files"])
    policy_files = checked_files(candidate, entries)
    models = ROOT / "assets/sim/robotwin"
    sim = read_json(models / "asset_manifest.json")
    environment_files = checked_files(models, [f for a in sim["archives"].values() for f in a["files"]])
    pace_commit = "5d0f4a92415f8899963cba7f0f929f1b9c5f75db"
    sources = [ROOT / p for p in ("PROTOCOL.md", "design.py", "trial.py")]
    for folder in ("controller", "sim", "policy"):
        # Include local inference, simulation and kinematic adapters.
        sources.extend(p for p in (ROOT / folder).rglob("*")
                       if p.is_file() and p.suffix in {".py", ".sh", ".txt", ".patch"} and "__pycache__" not in p.parts)
    source_files = {str(p.relative_to(ROOT)): file_hash(p) for p in sorted(sources)}
    if file_hash(SIM / "pace/configs/expert_scenes.json") != CACHE_SHA:
        raise ValueError("installed scene cache changed")
    return {
        "schema": 1, "scene_cache_sha256": CACHE_SHA, "policy_revision": POLICY_REVISION,
        "official_policy_manifest_sha256": file_hash(candidate / "manifest.json"), "policy_files": policy_files,
        "simulation_assets_revision": sim["revision"], "simulation_assets": environment_files,
        "simulation_assets_manifest_sha256": file_hash(models / "asset_manifest.json"),
        "pace": git_fingerprint(UPSTREAM, pace_commit), "simulation": git_fingerprint(SIM, pace_commit),
        "openpi": git_fingerprint(ROOT / "vendor/Openpi-PACE", OPENPI_REVISION),
        "adapters": source_files, "policy_runtime": packages(ROOT / "runtime/policy/venv/bin/python"),
        "simulation_runtime": packages(ROOT / "runtime/sim/venv/bin/python"),
    }
