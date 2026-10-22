"""Hash every tracked pre-existing file, without importing the old project."""
import hashlib
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[2]
dest = root / "d_alignment_pilot/reports/gate1"
files = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).split(b"\0")
hashes = {}
for raw in files:
    if not raw or raw.startswith(b"d_alignment_pilot/"):
        continue
    p = root / raw.decode()
    hashes[raw.decode()] = hashlib.sha256(p.read_bytes()).hexdigest()
target = dest / "preserved_before.json"
if not target.exists():
    target.write_text(json.dumps(hashes, sort_keys=True, indent=2) + "\n")
    print(f"Recorded {len(hashes)} original tracked file hashes")
else:
    before = json.loads(target.read_text())
    changed = sorted(k for k in before if before[k] != hashes.get(k))
    (dest / "preservation_check.json").write_text(json.dumps({"original_tracked_files": len(before), "changed": changed}, indent=2) + "\n")
    assert not changed, changed
    print(f"Verified {len(before)} original files unchanged")
