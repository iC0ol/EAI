"""Pure I/O and schema helpers shared by the isolated programs."""
import hashlib
import json
from pathlib import Path

import numpy as np

FIELDS = {"command": 7, "position": 3, "quaternion": 4, "gripper": 2,
          "next_position": 3, "next_quaternion": 4, "next_gripper": 2}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(2**20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value, exclusive=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x" if exclusive else "w") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def save_view(path, view):
    validate_view(view)
    with Path(path).open("xb") as handle:
        np.savez_compressed(handle, **view)


def load_view(path):
    with np.load(path, allow_pickle=False) as archive:
        view = {name: archive[name] for name in archive.files}
    validate_view(view)
    return view


def validate_view(view):
    assert set(view) == set(FIELDS) | {"sample_id", "trajectory_id"}, "Unauthorized input fields"
    n = len(view["command"])
    assert n > 12
    for name, width in FIELDS.items():
        array = np.asarray(view[name])
        assert array.shape == (n, width), (name, array.shape)
        assert array.dtype.kind == "f" and np.isfinite(array).all(), name
    for name in ("sample_id", "trajectory_id"):
        assert np.asarray(view[name]).shape == () and np.asarray(view[name]).dtype.kind in "US"
        assert len(str(view[name])) >= 8


def deadline(config):
    import datetime
    assert datetime.datetime.now(datetime.timezone.utc) < datetime.datetime.fromisoformat(config["budget_deadline_utc"]), "Eight-hour budget exhausted"
