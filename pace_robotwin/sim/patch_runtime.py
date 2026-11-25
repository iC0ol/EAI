"""Apply the two dependency edits from PACE's official installer to this venv."""

import difflib
from pathlib import Path
import re
import sysconfig


PACKAGES = Path(sysconfig.get_paths()["purelib"])


def patch(relative_path, pattern, replacement, already_patched):
    path = PACKAGES / relative_path
    before = path.read_text(encoding="utf-8")
    after, changes = re.subn(pattern, replacement, before)
    if changes == 0:
        if already_patched in before:
            return
        raise RuntimeError(f"Official installer pattern was not found in {relative_path}")
    path.write_text(after, encoding="utf-8")
    print("".join(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile=relative_path, tofile=relative_path,
    )), end="")


def main():
    patch(
        "sapien/wrapper/urdf_loader.py", r'("r")(\))( as)',
        r'\1, encoding="utf-8") as', '"r", encoding="utf-8") as',
    )
    patch(
        "mplib/planner.py", r"(if np.linalg.norm\(delta_twist\) < 1e-4 )or collide (or not within_joint_limit:)",
        r"\1\2", "if np.linalg.norm(delta_twist) < 1e-4 or not within_joint_limit:",
    )


if __name__ == "__main__":
    main()
