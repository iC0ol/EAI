import subprocess
import time

from common import ROOT, OUT, REPORT, BASE, read_json, write_json, sha256, git, now

commit = git("rev-parse", "cdb04a6")
frozen = [REPORT/"protocol.md", REPORT/"researcher_proposal.md", REPORT/"R0_source_audit.md",
          OUT/"plan.json", OUT/"R0_audit.json", OUT/"R0_P0_window38_52.csv"]
for p in frozen:
    blob = subprocess.check_output(["git", "show", f"{commit}:{p.relative_to(ROOT.parent)}"], cwd=ROOT.parent)
    assert blob == p.read_bytes(), p
r0 = read_json(OUT/"R0_audit.json")
write_json(OUT/"registration.json", {"protocol_commit": commit, "base": BASE, "utc": now(),
    "registered_unix_time": time.time(), "new_steps_before_registration": 0,
    "frozen_files": {str(p.relative_to(ROOT)): sha256(p) for p in frozen},
    "historical_M_files": r0["historical_M_files"], "asset_files": r0["asset_files"], "source_files": r0["source_files"]})
print(commit)
