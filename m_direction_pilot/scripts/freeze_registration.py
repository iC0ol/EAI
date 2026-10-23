"""Record the already committed, independently preregistered scientific inputs."""
import datetime
import subprocess
import time

from m_direction.audit import FROZEN_PATHS
from m_direction.io import ROOT, OUT, D_ROOT, sha256, write_json, git

protocol = git("rev-parse", "b2a64fb")
for p in FROZEN_PATHS:
    committed = subprocess.check_output(["git", "show", f"{protocol}:m_direction_pilot/{p}"], cwd=ROOT.parent)
    assert committed == (ROOT/p).read_bytes(), p
write_json(OUT / "registration.json", {
    "protocol_commit": protocol, "protocol_commit_time": git("show", "-s", "--format=%cI", protocol),
    "registered_unix_time": time.time(),
    "recorded_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "M_suffixes_at_registration": 0, "M_prefix_steps_at_registration": 0,
    "frozen_sha256": {p: sha256(ROOT/p) for p in FROZEN_PATHS},
    "reuse_input_sha256": {str(p.relative_to(ROOT.parent)): sha256(p) for p in [
        D_ROOT/"configs/gate1.json", D_ROOT/"data/manifests/normalization.json", D_ROOT/"requirements.lock"]}
})
print(protocol)
