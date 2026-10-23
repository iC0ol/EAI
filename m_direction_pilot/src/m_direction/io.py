import csv
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT.parent
D_ROOT = WORKSPACE / "d_alignment_pilot"
OUT = ROOT / "outputs/gate0"
REPORT = ROOT / "reports/gate0"
LOCAL = ROOT / "local/gate0"


def read_json(path):
    return json.loads(Path(path).read_text())


def config():
    return read_json(ROOT / "configs/gate0.json")


def encode(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value))


def write_json(path, value, exclusive=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x" if exclusive else "w") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, default=encode, allow_nan=False)
        f.write("\n")


def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("empty CSV")
    with path.open("x", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for row in rows:
            w.writerow({k: json.dumps(v, default=encode, separators=(",", ":"))
                        if isinstance(v, (list, dict, np.ndarray)) else v for k, v in row.items()})


def read_csv(path):
    with Path(path).open(newline="") as f:
        return list(csv.DictReader(f))


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def array_hash(a):
    a = np.ascontiguousarray(a)
    return hashlib.sha256(str((a.dtype.str, a.shape)).encode() + a.tobytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=WORKSPACE, text=True).strip()


def stable_seed(state_id, replan_index=0, stream=0):
    key = f"M-v2:{state_id}:stream{stream}:replan{replan_index}"
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % (2**31 - 1)
