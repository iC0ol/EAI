"""M-Gate0-R diagnostics only; historical files are read-only inputs."""
import csv
import datetime
import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np

from m_direction.io import ROOT, D_ROOT, sha256, array_hash, read_json, encode, git

REPORT = ROOT / "reports/replay_recovery"
OUT = ROOT / "outputs/replay_recovery"
LOCAL = ROOT / "local/replay_recovery"
CODE = ROOT / "scripts/replay_recovery"
BASE = "537e6a6db79ed1e8aa884b4bad8a44f08b17c480"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as f:
        json.dump(value, f, indent=2, ensure_ascii=False, default=encode, allow_nan=False)
        f.write("\n")


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="") as f:
        w = csv.DictWriter(f, list(rows[0]), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: json.dumps(v, default=encode, separators=(",", ":")) if isinstance(v, (dict, list, np.ndarray)) else v for k, v in r.items()})


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def plan():
    return read_json(OUT / "plan.json")


def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, default=encode, allow_nan=False).encode()).hexdigest()


def protected():
    old = read_json(ROOT / "outputs/gate0/sha256_manifest.json")
    hashes = {**old["sha256"], "outputs/gate0/sha256_manifest.json": sha256(ROOT/"outputs/gate0/sha256_manifest.json")}
    for p, h in hashes.items():
        assert sha256(ROOT/p) == h, p
    return hashes


def verify():
    reg = read_json(OUT/"registration.json")
    for p, h in reg["frozen_files"].items():
        assert sha256(ROOT/p) == h, p
    for p, h in reg["historical_M_files"].items():
        assert sha256(ROOT/p) == h, p
    for p, h in reg["asset_files"].items():
        assert sha256(ROOT.parent/p) == h, p
    for p, h in reg["source_files"].items():
        assert sha256(ROOT.parent/p) == h, p
    assert not git("diff", "--name-only", "HEAD", "--", str(CODE.relative_to(ROOT.parent)))
    assert time.time()-reg["registered_unix_time"] < 48*3600
    return reg


class Ledger:
    def __init__(self, root=OUT):
        self.path = root/"attempt_ledger.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read(self):
        return [json.loads(x) for x in self.path.read_text().splitlines()] if self.path.exists() else []

    def append(self, event):
        with self.path.open("a") as f:
            f.write(json.dumps({"utc": now(), **event}, default=encode, allow_nan=False)+"\n")
            f.flush(); os.fsync(f.fileno())

    def reserve(self, item, kind):
        import fcntl
        with (self.path.parent/".recovery.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            events = self.read()
            starts = [e for e in events if e["event"] == "start"]
            if any(e["attempt_id"] == item["attempt_id"] for e in starts):
                raise RuntimeError("No overwrite or automatic replay of a started attempt")
            limit = 6 if kind == "prefix" else 4
            if sum(e["kind"] == kind for e in starts) >= limit:
                raise RuntimeError("M-Gate0-R budget exhausted")
            self.append({"event": "start", "kind": kind, **item})


def old_limits():
    return read_json(ROOT/"configs/gate0.json")["prefix_tolerances"]
