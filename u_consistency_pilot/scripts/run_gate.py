#!/usr/bin/env python3
"""Offline, standard-library-only 0A resource audit. Does not run experiments.

Writes a new audit directory and refuses to overwrite one. No downloads, imports
from model/simulator packages, CUDA contexts, installation, or archive extraction.
Asset paths are published using aliases, never absolute private paths.
"""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone


def utc():
    return datetime.now(timezone.utc).isoformat()


def command(args, cwd=None):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=30)
    return {"argv": args, "exit_code": p.returncode,
            "stdout": p.stdout.strip(), "stderr": p.stderr.strip()}


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False,
                               allow_nan=False) + "\n", encoding="utf-8")


EXCLUDED = {".git", ".ssh", ".gnupg", ".config", ".mozilla", ".codex",
            "node_modules", "site-packages", "__pycache__", ".local",
            "snap", "Trash", "lost+found"}
TARGET_NAMES = {"weights.pt", "pusht_expert_train.h5.zst", "pusht_expert_train.h5"}
RELATED = ("lewm", "le-wm", "pusht", "stable-worldmodel", "stable_worldmodel")


def scan(alias, root, limits, expected_sizes):
    """Stream directory entries; no directory symlink following, bounded scope."""
    started = time.monotonic()
    result = {"alias": alias, "exists": root.exists(), "files_examined": 0,
              "directories_examined": 0, "permission_errors": 0,
              "excluded_directories": 0, "symlink_directories_skipped": 0,
              "max_depth": limits["max_depth"],
              "time_limit_seconds": limits["seconds"], "status": "COMPLETE",
              "name_hits": [], "size_hits": [], "related_hits": [],
              "related_hit_count": 0, "depth_pruned": 0}
    if not root.exists():
        result["status"] = "ABSENT"
        return result
    stack = [(root, 0)]
    while stack:
        if time.monotonic() - started >= limits["seconds"]:
            result["status"] = "TIME_LIMIT_PARTIAL"
            break
        directory, depth = stack.pop()
        try:
            with os.scandir(directory) as entries:
                result["directories_examined"] += 1
                for entry in entries:
                    if time.monotonic() - started >= limits["seconds"]:
                        result["status"] = "TIME_LIMIT_PARTIAL"
                        break
                    path = Path(entry.path)
                    rel = str(path.relative_to(root))
                    low = rel.lower()
                    related = any(s in low for s in RELATED)
                    if related:
                        result["related_hit_count"] += 1
                        if len(result["related_hits"]) < 40:
                            result["related_hits"].append(f"{alias}/{rel}")
                    if entry.is_dir(follow_symlinks=False):
                        if (entry.name in EXCLUDED or
                            entry.name.startswith(("inspection_robot", "ros2", ".venv")) or
                            entry.name in {"ros", "anaconda3"}):
                            result["excluded_directories"] += 1
                        elif depth >= limits["max_depth"]:
                            result["depth_pruned"] += 1
                        else:
                            stack.append((path, depth + 1))
                    elif entry.is_symlink() and entry.is_dir():
                        result["symlink_directories_skipped"] += 1
                    elif entry.is_file():
                        result["files_examined"] += 1
                        size = entry.stat().st_size
                        record = {"path_alias": f"{alias}/{rel}", "bytes": size}
                        if entry.name in TARGET_NAMES:
                            result["name_hits"].append(record)
                        if size in expected_sizes:
                            result["size_hits"].append(record)
        except (PermissionError, FileNotFoundError, OSError):
            result["permission_errors"] += 1
    result["elapsed_seconds"] = time.monotonic() - started
    return result


def package_inventory(label, prefix):
    sites = sorted(prefix.glob("lib/python*/site-packages"))
    versions = {}
    for site in sites:
        for dist in importlib.metadata.distributions(path=[str(site)]):
            name = dist.metadata.get("Name")
            if name:
                versions[name] = dist.version
    needed = ["torch", "torchvision", "numpy", "scipy", "scikit-learn",
              "h5py", "zstandard", "pymunk", "pygame", "gymnasium", "gym",
              "stable-worldmodel", "lance", "pylance", "einops"]
    normalized = {k.lower().replace("_", "-"): v for k, v in versions.items()}
    return {"alias": label, "exists": prefix.exists(),
            "inspection": "distribution metadata only; no model imports",
            "needed_package_versions": {k: normalized.get(k) for k in needed},
            "all_distribution_versions": dict(sorted(versions.items()))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True,
                        help="New directory inside u_consistency_pilot")
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    repo = project.parent
    out = Path(args.output).resolve()
    if project not in out.parents:
        parser.error("output must be inside u_consistency_pilot")
    if out.exists():
        parser.error("refusing to overwrite an existing audit directory")
    out.mkdir(parents=True)
    started = utc()
    t0 = time.monotonic()
    config_bytes = (project / "configs/protocol_v2.json").read_bytes()
    cfg = json.loads(config_bytes)
    sizes = {a["bytes"] for a in cfg["required_assets"] if "bytes" in a}
    home = Path.home()
    # These are search scopes, not claims about all possible local storage.
    scopes = [("EAI", repo, 24, 30),
              ("HF_CACHE", home / ".cache/huggingface", 20, 20),
              ("TORCH_CACHE", home / ".cache/torch", 20, 15)]
    for name in ["datasets", "Downloads", "Documents", "Desktop", "workspace"]:
        scopes.append((f"HOME_{name.upper()}", home / name, 16, 15))
    # Shallow home and mounted-drive coverage is explicitly reported as bounded.
    scopes.append(("HOME_SHALLOW", home, 2, 15))
    for i, drive in enumerate(sorted(Path("/media").glob("*/*"))):
        if drive.is_dir():
            scopes.append((f"MEDIA_{i}", drive, 5, 20))
    scopes.extend([("MNT", Path("/mnt"), 8, 10),
                   ("OPT", Path("/opt"), 5, 10),
                   ("SRV", Path("/srv"), 8, 10)])
    scans = [scan(alias, root, {"max_depth": depth, "seconds": seconds}, sizes)
             for alias, root, depth, seconds in scopes]
    hf = home / ".cache/huggingface/hub"
    cache_checks = {"HF_MODEL_LEWM_PUSHT":
                    (hf / "models--quentinll--lewm-pusht").exists(),
                    "HF_DATASET_LEWM_PUSHT":
                    (hf / "datasets--quentinll--lewm-pusht").exists()}
    name_hits = [x for s in scans for x in s["name_hits"]]
    size_hits = [x for s in scans for x in s["size_hits"]]
    # An audit never grants semantic/replay admission, even if an asset is found.
    disposition = ("RESOURCE_CANDIDATES_REQUIRE_REVIEW" if name_hits or size_hits
                   or any(cache_checks.values()) else "TECHNICAL-BLOCK")
    disk = shutil.disk_usage(repo)
    meminfo = dict(line.split(":", 1) for line in
                   Path("/proc/meminfo").read_text().splitlines())
    memory = {k: int(meminfo[k].strip().split()[0]) * 1024
              for k in ["MemTotal", "MemAvailable", "SwapTotal", "SwapFree"]}
    gpu = command(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used,utilization.gpu",
                   "--format=csv,noheader"])
    gpu_processes = command(["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory",
                             "--format=csv,noheader"])
    gpu_processes["stdout"] = "\n".join(
        ", ".join([parts[0].strip(), Path(parts[1].strip()).name, parts[2].strip()])
        for line in gpu_processes["stdout"].splitlines()
        if len(parts := line.split(",")) == 3)
    environment_prefixes = [("EAI_D_EXISTING", repo / "d_alignment_pilot/.venv"),
                            ("EAI_SPATIAL_EXISTING", repo / "spatial_intervention_pilot/.venv"),
                            ("EAI_VLM_EXISTING", repo / "spatial_intervention_pilot/.venv-vlm"),
                            ("CONDA_BASE_EXISTING", home / "anaconda3")]
    for i, prefix in enumerate(sorted((home / "anaconda3/envs").glob("*"))):
        if prefix.is_dir():
            environment_prefixes.append((f"CONDA_ENV_{i}", prefix))
    packages = [package_inventory(label, path) for label, path in environment_prefixes]
    write_json(out / "environment_packages.json", packages)
    write_json(out / "resource_manifest.json", {
        "schema_version": 1, "started_at_utc": started, "ended_at_utc": utc(),
        "status": disposition,
        "required_assets": [{**a, "local_verification": "NOT_FOUND_IN_COMPLETED_SCOPES"}
                            for a in cfg["required_assets"]],
        "expected_hash_provenance": "user-supplied pins; no local matching asset hashed",
        "direct_hf_cache_directory_checks": cache_checks,
        "searches": scans, "candidate_name_hits": name_hits, "candidate_size_hits": size_hits,
        "excluded_directory_basenames": sorted(EXCLUDED),
        "coverage_limit": "No directory symlink following. Shallow/depth/time-limited and permission-denied areas are not exhaustive. No archive contents searched.",
        "disk": {"total_bytes": disk.total, "used_bytes": disk.used, "free_bytes": disk.free},
        "host_memory_snapshot_bytes": memory, "gpu_snapshot": gpu,
        "existing_gpu_process_snapshot": gpu_processes,
        "existing_gpu_processes_modified": False,
        "model_dataset_download_bytes": 0, "research_source_download_bytes": 0,
        "archive_extracted_bytes": 0, "new_environments": 0,
        "torch_or_simulator_imported": False})
    write_json(out / "versions.json", {
        "audit_python": platform.python_version(),
        "audit_python_binary_sha256": hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
        "platform": {"system": platform.system(), "release": platform.release(),
                     "machine": platform.machine(), "libc": platform.libc_ver()},
        "git": {"branch": command(["git", "branch", "--show-current"], repo)["stdout"],
                "head_at_audit": command(["git", "rev-parse", "HEAD"], repo)["stdout"],
                "initial_branch": "research/m-gate0-live-screen",
                "initial_commit": "9ca5c2e8423d37ec05194c9df9330c0aade69fed",
                "initial_worktree_clean": True,
                "initial_protected_git_index_sha256": "e538228da0823252de575f48e67f27bd833ebd7681e60b9c5b31509b4181db1c"},
        "protocol_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "environment_inventory": "environment_packages.json",
        "experiment_environment_lock": "NOT_RUN_NO_COMPATIBLE_ENV_VALIDATED",
        "upstream_pins": cfg["upstream_pins"]})
    headers = {
        "replay_check.csv": ["root", "source", "seed", "branch", "candidate_source",
                             "repeat", "action_block", "max_state_difference",
                             "pixels_equal", "J", "J_repeat_difference", "status", "reason"],
        "root_manifest.csv": ["split", "root", "source", "seed", "prefix_hash", "goal_hash",
                              "history_hash", "contact_stratum", "status", "reason"],
        "per_root_metrics.csv": ["split", "root", "source", "seed", "method", "lambda",
                                 "selected_index", "R", "J", "block_only", "success",
                                 "candidate_range", "uninformative", "status", "reason"]}
    for filename, header in headers.items():
        with (out / filename).open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle, lineterminator="\n").writerow(header)
    write_json(out / "audit_execution.json", {
        "started_at_utc": started, "ended_at_utc": utc(),
        "elapsed_seconds": time.monotonic() - t0,
        "peak_audit_process_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "status": disposition, "strict_load": "NOT_RUN", "simulator_steps": "NOT_RUN",
        "training": "NOT_RUN", "calibration": "NOT_RUN", "dev": "NOT_RUN", "test": "NOT_RUN",
        "gpu_process_seconds": 0, "task_gpu_vram_bytes": 0,
        "scope": "resource metadata audit only"})
    print(json.dumps({"status": disposition, "audit_directory": str(out.relative_to(repo)),
                      "name_candidates": len(name_hits), "size_candidates": len(size_hits)}))
    return 2 if disposition == "TECHNICAL-BLOCK" else 3


if __name__ == "__main__":
    raise SystemExit(main())
