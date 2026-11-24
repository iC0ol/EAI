"""Paired pilot ordering, disk integrity checks, and resumable execution."""

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import subprocess
import tempfile
import traceback


ROOT = Path(__file__).resolve().parent
ARMS = ("fixed15", "refresh", "smooth", "always_split", "adaptive")
SEEDS = {"engineering": (520096,), "overnight": tuple(range(520000, 520032))}
SOURCE_FILES = ("PROTOCOL.md", "run.sh", "mechanism.py", "rollout.py", "study.py", "analyze.py", "audit.py")
BASE_COMMIT = "52acc79b2315a4a16efb55188a5f3230fbef454a"


class IntegrityError(ValueError):
    """An evidence or protocol mismatch that must be inspected before retrying."""


def require(condition, message):
    if not condition:
        raise IntegrityError(message)


def now():
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def encoded(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def digest(data):
    return hashlib.sha256(encoded(data)).hexdigest()


def read_json(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temporary, path)
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if temporary.exists():
                temporary.unlink()


def save(path, data):
    atomic_write(path, encoded(data) + b"\n")


def source_hashes():
    subprocess.run(["git", "diff", "--quiet", BASE_COMMIT, "--", "gate_b_v2/src",
                    "gate_b_v2/configs", "gate_b_v2/reports/b1_full_environment_manifest.json"],
                   cwd=ROOT.parent, check=True)
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCE_FILES}


def episode_order(stage):
    arms = list(ARMS)
    random.Random(20261125).shuffle(arms)
    return [(seed, arm) for i, seed in enumerate(SEEDS[stage])
            for arm in arms[i % len(arms):] + arms[:i % len(arms)]]


def check_record(row):
    arm, seed = row["arm"], row["seed"]
    require(arm in ARMS and type(seed) is int, "Unexpected episode key")
    require(type(row["steps"]) is int and row["steps"] == 500, "Incomplete control-step budget")
    for key in ("initial_state_hash", "first_chunk_sha256"):
        require(isinstance(row[key], str) and re.fullmatch(r"[0-9a-f]{64}", row[key]), key)
    first = row["first_success_step"]
    require(first is None or (type(first) is int and 1 <= first <= 500), "Invalid first success")
    require(type(row["success"]) is bool and (not row["success"] or first is not None),
            "Inconsistent final predicate")
    for key in ("wall_seconds", "inference_seconds"):
        require(math.isfinite(row[key]) and row[key] > 0, key)
    require(row["inference_seconds"] <= row["wall_seconds"] + 0.01, "Invalid inference timing")
    expected = [t for t in range(500) if t % 15 == 0 or (arm != "fixed15" and t % 15 == 6)]
    schedule = row["query_schedule"]
    require([q["t"] for q in schedule] == expected, "Physical query times changed")
    for q in schedule:
        t = q["t"]
        count = 1 if t % 15 == 0 else 2
        noises = [2000000 + (seed - 520000) * 4096 + 3 * t + k for k in range(count)]
        require(q["candidate_count"] == count and q["noise_seeds"] == noises,
                "Candidate/noise schedule changed")
        require(q["phase"] == ("anchor" if count == 1 else "mid") and len(q["chunk_sha256"]) == count
                and all(re.fullmatch(r"[0-9a-f]{64}", h) for h in q["chunk_sha256"]), "Missing chunk hashes")
    require(schedule[0]["chunk_sha256"][0] == row["first_chunk_sha256"], "First prediction hash mismatch")
    samples = sum(q["candidate_count"] for q in schedule)
    require((len(schedule), samples) == ((34, 34) if arm == "fixed15" else (67, 100)),
            "Incorrect registered budget")
    require((row["policy_queries"], row["policy_samples"]) == (len(schedule), samples),
            "Recorded budget disagrees with queries")
    events = row["events"]
    require([e["t"] for e in events] == [t for t in expected if t % 15 == 6],
            "Missing or extra mid-cycle events")
    for e in events:
        require(e["pre_success"] == (first is None or first > e["t"]), "Success timing mismatch")
        eligible = e["eligible"]
        require(all(type(e[key]) is bool for key in ("eligible", "pre_success", "admissible", "stall")),
                "Invalid decision predicates")
        require(not eligible or e["pre_success"], "Post-success intervention")
        require(eligible == (e["mid_grasped"] and e["pre_success"] and e["all_commands_closed"]
                             and e["actual_hole_lateral_start_m"] <= 0.12), "Unexpected opportunity")
        require(e["old_action_indices"] == list(range(6, 15)) and e["new_action_indices"] == list(range(9)),
                "Incorrect temporal alignment")
        candidate_rms = e["candidate_axial_rms_m"]
        require(e["chosen_candidate"] == (int(candidate_rms[1] < candidate_rms[0]) if eligible else 0),
                "Mid-cycle selection does not match axial disagreement")
        require(e["stall"] == (e["anchor_grasped"] and e["planned_down_m"] >= 0.004
                               and e["actual_down_m"] < 0.25 * e["planned_down_m"]), "Stall mismatch")
        require(e["chosen_candidate"] in (0, 1) and (eligible or e["chosen_candidate"] == 0),
                "Invalid selected candidate")
        if eligible:
            admissible = e["axial_rms_m"] <= 0.010 and e["axial_max_abs_m"] <= 0.020 and not e["stall"]
            require(admissible == e["admissible"], "Compatibility rule changed")
        else:
            require(not e["admissible"], "Ineligible decision passed")
        action = "fresh"
        if eligible and arm == "smooth":
            action = "smooth"
        if eligible and (arm == "always_split" or (arm == "adaptive" and e["admissible"])):
            action = "split"
        require(e["decision"] == action, "Action differs from registered decision")
        old = e["issued_hole_axial_minus_old_m"]
        new = e["issued_hole_axial_minus_new_m"]
        require(len(old) == len(new) == 9 and all(math.isfinite(v) for v in old + new),
                "Incomplete executed overlap")
        if action == "split":
            require(max(map(abs, old)) < 2e-6, "Split action lost old hole-axis reference")
        if action == "fresh":
            require(max(map(abs, new)) < 2e-6, "Fresh action changed selected candidate")
        if action == "smooth":
            require(max(map(abs, new[3:])) < 2e-6, "Smoothing exceeded three control steps")


def validate_pairs(rows):
    paired = {}
    state_to_seed = {}
    for (seed, _), row in rows.items():
        pair = (row["initial_state_hash"], row["first_chunk_sha256"])
        require(paired.setdefault(seed, pair) == pair, "Initial state or first chunk differs by arm")
        require(state_to_seed.setdefault(pair[0], seed) == seed, "Duplicate physical initial state")


def records(directory, stage, fingerprint):
    result = {}
    planned = set(episode_order(stage))
    for path in sorted((directory / "records").glob("*.json")):
        obj = read_json(path)
        row = obj["record"]
        key = (row["seed"], row["arm"])
        require(key in planned and key not in result and path.name == "{}_{}.json".format(*key),
                "Unexpected or duplicate episode file")
        require(obj["code_fingerprint"] == fingerprint and obj["record_sha256"] == digest(row),
                "Episode hash/version mismatch: " + path.name)
        check_record(row)
        result[key] = row
    validate_pairs(result)
    return result


def audit_acceptance(fingerprint, write=False):
    directory = ROOT / "runs" / "engineering"
    engineering = records(directory, "engineering", fingerprint)
    require(set(engineering) == set(episode_order("engineering")), "Incomplete engineering checks")
    require(read_json(directory / "STATUS.json")["state"] == "COMPLETE", "Engineering incomplete")
    values = {arm: digest(engineering[520096, arm]) for arm in ARMS}
    path = directory / "ACCEPTED.json"
    if write and not path.exists():
        from audit import audit
        save(directory / "AUDIT.json", audit(directory, SEEDS["engineering"]))
        save(path, {"code_fingerprint": fingerprint, "episodes": values, "verified_at": now()})
    accepted = read_json(path)
    require(accepted["code_fingerprint"] == fingerprint and accepted["episodes"] == values,
            "Engineering acceptance is stale")


def run(stage):
    directory = ROOT / "runs" / stage
    directory.mkdir(parents=True, exist_ok=True)
    order = episode_order(stage)
    status_path = directory / "STATUS.json"
    with (directory / "worker.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another worker holds the run lock.", flush=True)
            return
        rows = {}
        current = None
        experiment = None

        def status(state, **extra):
            save(status_path, dict(stage=stage, state=state, completed=len(rows), total=len(order),
                                   active_episode=current, updated_at=now(), pid=os.getpid(), **extra))

        try:
            files = source_hashes()
            fingerprint = digest(files)
            manifest_path = directory / "MANIFEST.json"
            if manifest_path.exists():
                manifest = read_json(manifest_path)
                require(manifest["sources"] == files and manifest["code_fingerprint"] == fingerprint
                        and manifest["order"] == [list(k) for k in order], "Frozen manifest mismatch")
            else:
                require(not list((directory / "records").glob("*.json")), "Manifest missing for existing records")
                head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
                save(manifest_path, dict(sources=files, code_fingerprint=fingerprint, order=order,
                                         created_at=now(), git_commit=head, gate_b_base=BASE_COMMIT))
            rows = records(directory, stage, fingerprint)
            if stage == "overnight":
                audit_acceptance(fingerprint)
            if len(rows) < len(order):
                from component_commitment.rollout import create_experiment, run_episode
                from gate_b_v2.core import jsonable
                status("LOADING")
                experiment = create_experiment(directory)
                environment_path = directory / "ENVIRONMENT.json"
                if not environment_path.exists():
                    save(environment_path, jsonable(experiment.manifest))
                previous = read_json(environment_path)
                for field in ("checkpoint_sha256", "dataset_sha256", "dp_source_tree_sha256",
                              "available_future_actions", "python", "torch", "robosuite", "mujoco_py", "gpu_name"):
                    require(previous[field] == experiment.manifest[field], "Changed environment " + field)
                for key in order:
                    if key in rows:
                        continue
                    current = key
                    status("RUNNING")
                    row = run_episode(experiment, *key)
                    require((row["seed"], row["arm"]) == key, "Runner returned wrong episode key")
                    check_record(row)
                    validate_pairs({**rows, key: row})
                    wrapper = dict(record=row, record_sha256=digest(row), code_fingerprint=fingerprint)
                    save(directory / "records" / "{}_{}.json".format(*key), wrapper)
                    rows[key] = row
                    print(now(), len(rows), "/", len(order), *key, flush=True)
            current = None
            if stage == "overnight":
                from analyze import deliver
                status("ANALYZING")
                deliver(directory, records(directory, stage, fingerprint))
            status("COMPLETE")
        except Exception as exc:
            status("ERROR", error=repr(exc))
            raise
        finally:
            if experiment is not None:
                experiment.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["engineering", "overnight", "accept", "verify"])
    args = parser.parse_args()
    if args.command in SEEDS:
        run(args.command)
    elif args.command == "accept":
        audit_acceptance(digest(source_hashes()), write=True)
        print("Engineering acceptance recorded.")
    else:
        directory = ROOT / "runs" / "overnight"
        fingerprint = digest(source_hashes())
        audit_acceptance(fingerprint)
        rows = records(directory, "overnight", fingerprint)
        require(len(rows) == len(episode_order("overnight")), "Formal run is incomplete")
        from analyze import deliver
        deliver(directory, rows)
        print("Validated", len(rows), "formal episodes.")


if __name__ == "__main__":
    try:
        main()
    except IntegrityError:
        traceback.print_exc()
        raise SystemExit(65)
