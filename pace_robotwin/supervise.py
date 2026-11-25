"""Persistent single-GPU queue, completion checks and time estimates."""

import argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import signal
import socket
import statistics
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

from design import PORT, ROOT, RUNS, STAGES, TASKS, file_hash, methods, pair_dir, read_json, scenes, verify_record, write_json
from manifest import make_manifest


BEIJING = timezone(timedelta(hours=8))
FORMAL = RUNS / "formal"
ACCEPTED = RUNS / "ACCEPTED.json"
LOCAL_HTTP = build_opener(ProxyHandler({}))


def now():
    return datetime.now(BEIJING)


def engineering_path():
    path = RUNS / "ENGINEERING_PATH.json"
    return ROOT / read_json(path)["path"] if path.is_file() else None


def read_times(root, stages):
    durations = defaultdict(list)
    if root:
        for stage in stages:
            for path in (root / stage).glob("*/*/*/timing.json"):
                task, _, method = path.parts[-4:-1]
                if method.startswith("."):
                    continue
                if task not in TASKS or method not in STAGES[stage][1]:
                    raise ValueError(f"unregistered timing record {path}")
                durations[stage, task, method].append(float(read_json(path)["wall_with_io_s"]))
    return durations


def report_progress():
    formal = read_times(FORMAL, ("reproduction", "heldout"))
    engineering = read_times(engineering_path(), ("engineering",))
    cells = {}
    remaining = 0.
    covered = True
    for stage in ("reproduction", "heldout"):
        for task in TASKS:
            for method in STAGES[stage][1]:
                samples = formal[stage, task, method]
                reference = samples or engineering["engineering", task, method]
                key = f"{stage}/{task}/{method}"
                cells[key] = {"complete": len(samples), "total": 100,
                              "mean_seconds": statistics.mean(reference) if reference else None}
                if len(samples) < 100 and not reference:
                    covered = False
                if reference:
                    remaining += (100 - len(samples)) * statistics.mean(reference)
    completed = sum(len(values) for values in formal.values())
    return {
        "checked_beijing": now().isoformat(timespec="seconds"), "completed": completed, "expected": 1600,
        "engineering_completed": sum(map(len, engineering.values())),
        "estimated_remaining_hours_at_observed_speed": round(remaining / 3600, 2) if covered else None,
        "estimated_finish_beijing_while_running": (now() + timedelta(seconds=remaining)).isoformat(timespec="minutes")
        if covered and completed < 1600 else None, "cells": cells,
    }


def freeze_for_engineering():
    manifest = make_manifest(verify_tasks=(TASKS[0],))
    prior = engineering_path()
    if prior and read_json(prior / "MANIFEST.json") == manifest:
        return prior
    root = RUNS / now().strftime("engineering_%Y%m%d_%H%M%S_%f")
    root.mkdir(parents=True)
    write_json(root / "MANIFEST.json", manifest)
    write_json(RUNS / "ENGINEERING_PATH.json", {"path": str(root.relative_to(ROOT))})
    return root


def wait_for_engineering_inputs(task):
    stack_probe = ROOT / f"runtime/policy/engineering/{TASKS[0]}.probe.json"
    policy_ready = ROOT / "runtime/policy/READY.json"
    locations = {"policy": stack_probe if task == TASKS[0] else policy_ready, "sim": ROOT / "runtime/sim/READY.json"}
    while True:
        ready = {name: path.is_file() for name, path in locations.items()}
        write_json(RUNS / "SETUP.json", {"state": "VERIFYING_INPUTS" if all(ready.values()) else "WAITING_FOR_INPUTS",
                                         "task": task, "checked_beijing": now().isoformat(timespec="seconds"), "ready": ready})
        if all(ready.values()):
            break
        time.sleep(45)
    if task == TASKS[0]:
        probes = {task: str(stack_probe.relative_to(ROOT))}
    else:
        probes = read_json(policy_ready)["probes"]
        if set(probes) != set(TASKS):
            raise ValueError("two task-specific GPU policy probes are required")
    for probed_task, relative in probes.items():
        result = read_json(ROOT / relative)
        if not (result["same_seed_exact"] and result["different_seed_differs"] and result["matches_upstream_seed_zero_sequence"]
                and result["metadata"]["task"] == probed_task and result["metadata"]["candidate_count"] == 1):
            raise ValueError(f"failed real GPU inference/replay on {probed_task}")
    sim = {}
    for relative in read_json(locations["sim"])["reports"]:
        result = read_json(ROOT / relative)
        if result["status"] != "pass":
            raise ValueError(f"simulator verification failed: {relative}")
        for item in result["tasks"]:
            sim[item["task"]] = item
    if set(sim) != set(TASKS):
        raise ValueError("two physical simulator probes are required")
    for sim_task, item in sim.items():
        if not (item["scene_cache_seed"] == 2 and item["executed_test_actions"] == 1 and
                item["reset"] == {"action_count": 0, "success": False} and math.isfinite(item["joint_change_l2"])
                and item["joint_change_l2"] > 0 and item["state_shape"] == [14] and len(item["cameras"]) == 3):
            raise ValueError(f"invalid native reset or joint command evidence on {sim_task}")
    write_json(RUNS / "SETUP.json", {"state": "INPUT_PROBES_VERIFIED", "policy": probes,
                                     "task": task, "sim": list(sim), "checked_beijing": now().isoformat(timespec="seconds")})


def accepted_root(check_assets):
    accepted = read_json(ACCEPTED)
    engineering = ROOT / accepted["engineering"]
    if file_hash(engineering / "MANIFEST.json") != accepted["manifest_sha256"]:
        raise ValueError("accepted manifest changed")
    if file_hash(engineering / "AUDIT.json") != accepted["engineering_audit_sha256"]:
        raise ValueError("accepted engineering audit changed")
    if check_assets and read_json(engineering / "MANIFEST.json") != make_manifest():
        raise ValueError("live scientific inputs differ from the accepted inputs")
    return engineering


def prepare_formal():
    engine = accepted_root(True)
    manifest = read_json(engine / "MANIFEST.json")
    target = FORMAL / "MANIFEST.json"
    if target.exists():
        if read_json(target) != manifest:
            raise ValueError("existing formal manifest differs")
    else:
        write_json(target, manifest)
    return FORMAL


def wait_for_server(child):
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        if child.poll() is not None:
            raise RuntimeError(f"policy server exited with {child.returncode}")
        try:
            with LOCAL_HTTP.open(f"http://127.0.0.1:{PORT}/healthz", timeout=3) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(4)
    raise TimeoutError("the local policy server has not become healthy")


def stop_owned_process(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def run_child(command, log, server, outroot, active):
    child = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    try:
        while child.poll() is None:
            if server.poll() is not None:
                raise RuntimeError(f"policy exited with {server.returncode}")
            write_json(outroot / "STATUS.json", {"state": "RUNNING", "active": active, **report_progress()})
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass
        if child.returncode != 0:
            raise RuntimeError(f"client exited with {child.returncode}; see {log.name}")
    finally:
        stop_owned_process(child)


def cell_is_done(outroot, stage, task, index, scene_seed, method, manifest_hash):
    target = pair_dir(outroot, stage, task, index) / method
    if not target.exists():
        return False
    verify_record(target, {"stage": stage, "task": task, "index": index, "scene_seed": scene_seed,
                           "method": method, "manifest_sha256": manifest_hash})
    return True


def run_task(outroot, stage, task, manifest_hash):
    rows = scenes(stage, task)
    count = 1 if stage == "engineering" else 100
    pending = []
    for index in range(count):
        if not all(cell_is_done(outroot, stage, task, index, rows[index]["scene_seed"], method, manifest_hash)
                   for method in methods(stage, index)):
            pending.append(index)
    if not pending:
        return
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", PORT))
    session = outroot / "sessions" / f"{stage}_{task}_{now():%Y%m%d_%H%M%S_%f}"
    session.mkdir(parents=True)
    started = time.monotonic()
    with (session / "server.log").open("ab", buffering=0) as logfile:
        server = subprocess.Popen(["bash", str(ROOT / "policy/serve.sh"), "--task", task, "--port", str(PORT)],
                                  cwd=ROOT, stdout=logfile, stderr=subprocess.STDOUT)
        try:
            wait_for_server(server)
            load_s = time.monotonic() - started
            warm = ["bash", str(ROOT / "run.sh"), "warmup", "--task", task, "--port", str(PORT),
                    "--output", str(session / "warmup.json")]
            with (session / "warmup.log").open("ab", buffering=0) as log:
                run_child(warm, log, server, outroot, f"{stage}/{task}/warmup")
            write_json(session / "startup.json", {"load_s": load_s, "warmup_wall_s": time.monotonic() - started - load_s})
            # Releasing the simulator every five scenes bounds renderer/allocator lifetime.
            for start in range(0, count, 5):
                stop = min(start + 5, count)
                if not any(start <= idx < stop for idx in pending):
                    continue
                command = ["bash", str(ROOT / "run.sh"), "trial", stage, task, str(start), str(stop),
                           "--output", str(outroot), "--manifest", manifest_hash, "--port", str(PORT)]
                with (session / f"client_{start:03d}.log").open("ab", buffering=0) as log:
                    run_child(command, log, server, outroot, f"{stage}/{task}/{start}-{stop-1}")
        finally:
            stop_owned_process(server)


def run_queue(mode):
    RUNS.mkdir(exist_ok=True)
    with (RUNS / "workstation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if mode == "engineering":
            wait_for_engineering_inputs(TASKS[0])
        outroot = freeze_for_engineering() if mode == "engineering" else prepare_formal()
        manifest_hash = file_hash(outroot / "MANIFEST.json")
        stages = ("engineering",) if mode == "engineering" else ("reproduction", "heldout")
        try:
            for stage in stages:
                for task in TASKS:
                    if stage == "engineering" and task == TASKS[1]:
                        wait_for_engineering_inputs(task)
                        if read_json(outroot / "MANIFEST.json") != make_manifest():
                            raise ValueError("inputs changed between the two engineering tasks")
                    write_json(outroot / "STATUS.json", {"state": "PREPARING", "active": f"{stage}/{task}", **report_progress()})
                    # The standalone phone policy probe uses the same lock. Take it only during GPU work.
                    with (ROOT / "runtime/probe-gpu.lock").open("a") as gpu_lock:
                        fcntl.flock(gpu_lock, fcntl.LOCK_EX)
                        run_task(outroot, stage, task, manifest_hash)
            info = report_progress()
            observed = info["engineering_completed"] if mode == "engineering" else info["completed"]
            if observed != (10 if mode == "engineering" else 1600):
                raise ValueError(f"incomplete queue: {observed}")
            write_json(outroot / "STATUS.json", {"state": "AWAITING_AUDIT", **info})
            with (outroot / "audit.log").open("ab") as log:
                subprocess.run(["bash", str(ROOT / "run.sh"), "audit", mode], cwd=ROOT,
                               stdout=log, stderr=subprocess.STDOUT, check=True)
            write_json(outroot / "STATUS.json", {"state": "AUDITED", **report_progress()})
        except BaseException as error:
            write_json(outroot / "STATUS.json", {"state": "INTERRUPTED", "error": repr(error), **report_progress()})
            raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("engineering", "formal", "status", "accept"))
    args = parser.parse_args()
    if args.mode == "status":
        print(json.dumps(report_progress(), indent=2))
        return
    if args.mode == "accept":
        root = engineering_path()
        if root is None or read_json(root / "STATUS.json")["state"] not in {"AWAITING_AUDIT", "AUDITED"}:
            raise ValueError("engineering is incomplete")
        audit = read_json(root / "AUDIT.json")
        if audit["verified_records"] != 10 or audit["manifest_sha256"] != file_hash(root / "MANIFEST.json"):
            raise ValueError("engineering acceptance needs a complete independent audit")
        receipt = {"engineering": str(root.relative_to(ROOT)), "manifest_sha256": file_hash(root / "MANIFEST.json"),
                   "engineering_audit_sha256": file_hash(root / "AUDIT.json")}
        if ACCEPTED.exists() and read_json(ACCEPTED) != receipt:
            raise ValueError("existing acceptance is bound to a different engineering run")
        write_json(ACCEPTED, receipt)
        print(json.dumps(receipt, indent=2))
        return
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    run_queue(args.mode)


if __name__ == "__main__":
    main()
