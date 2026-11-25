"""Frozen cells and filesystem operations shared by the launcher and the audit."""

import hashlib
import json
import os
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
UPSTREAM = ROOT / "vendor" / "PACE"
SIM = ROOT / "vendor" / "RoboTwin-PACE"
TASKS = ("stack_blocks_three", "place_phone_stand")
LIMITS = dict(zip(TASKS, (1200, 400)))
STAGES = {
    "reproduction": (0, ("fixed5", "fixed25", "fixed50", "pace")),
    "heldout": (1, ("fixed25", "fixed50", "pace", "component")),
    "engineering": (2, ("fixed5", "fixed25", "fixed50", "pace", "component")),
}
CACHE_SHA = "12ac49e3913308901113cc8ddd9f71f0987ce8c9ebd83f03c308c759bdbeb939"
POLICY_REVISION = "17ef545270cf26ed81169893b60f845f80ce6557"
OPENPI_REVISION = "ba9876639cb7a4bf0c7db00ec39eeb9c8efd8b12"
PORT = 14826


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as stream:
        name = stream.name
        json.dump(data, stream, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(name, path)


def scenes(stage, task):
    seed, _ = STAGES[stage]
    path = UPSTREAM / "pace/configs/expert_scenes.json"
    if file_hash(path) != CACHE_SHA:
        raise ValueError("official scene cache changed")
    rows = read_json(path)["tasks"][task][str(seed)]
    if len(rows) != 100 or len({r["scene_seed"] for r in rows}) != 100:
        raise ValueError("expected 100 unique released scenes")
    return rows


def methods(stage, index):
    _, names = STAGES[stage]
    offset = index % len(names)
    return names[offset:] + names[:offset]


def pair_dir(output, stage, task, index):
    return output / stage / task / f"scene_{index:03d}"


def verify_record(path, expected):
    record = read_json(path / "record.json")
    if any(record.get(k) != v for k, v in expected.items()):
        raise ValueError(f"identity mismatch at {path}")
    hashes = read_json(path / "sha256.json")
    if set(hashes) != {"record.json", "chunks.npz", "timing.json"}:
        raise ValueError(f"incomplete manifest at {path}")
    for filename, digest in hashes.items():
        if file_hash(path / filename) != digest:
            raise ValueError(f"evidence digest mismatch at {path / filename}")
    return record
