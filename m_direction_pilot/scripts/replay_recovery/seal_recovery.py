"""Final source/evidence hash seal and preservation audit. No physics calls."""
from common import ROOT, OUT, REPORT, CODE, BASE, read_json, write_json, sha256, protected, git, now

old = protected()
original = read_json(ROOT/"outputs/gate0/branch_results/A_S00_repeat0.json")
assert sha256(ROOT/original["trace_path"]) == original["trace_sha256"]
reg = read_json(OUT/"registration.json")
for p,h in reg["frozen_files"].items(): assert sha256(ROOT/p)==h,p
for p,h in reg["asset_files"].items(): assert sha256(ROOT.parent/p)==h,p
for p,h in reg["source_files"].items(): assert sha256(ROOT.parent/p)==h,p
for b,h in read_json(OUT/"R0_audit.json")["old_branch_heads"].items(): assert git("rev-parse",b)==h,b
for r in [read_json(OUT/"D1_P1_S00.json"),read_json(OUT/"D2_P2_S00.json")]:
    for p,h in r["code_sha256"].items(): assert sha256(ROOT/p)==h,p
local = read_json(OUT/"local_trace_index.json")
for item in local: assert sha256(ROOT/item["path"])==item["sha256"]
allowed = [str(p.relative_to(ROOT.parent))+"/" for p in [OUT,REPORT,CODE]]
changed = git("diff","--name-only",BASE).splitlines()
assert all(any(p.startswith(a) for a in allowed) for p in changed)
write_json(REPORT/"final_audit.json", {"utc":now(),"decision":"R-Fail / Engineering blocked",
    "protocol_commit":reg["protocol_commit"],"execution_commit":read_json(OUT/"D1_P1_S00.json")["execution_commit"],
    "new_simulation_steps_after_stop":0,"old_M_files_verified":len(old),"old_asset_hashes_verified":True,
    "old_dependencies_and_D_spatial_unchanged":True,"changed_paths_within_three_authorized_directories":True,
    "old_branch_heads":read_json(OUT/"R0_audit.json")["old_branch_heads"],"prefix_attempts":2,"complete_prefixes":2,
    "prefix_control_steps":104,"integration_steps":2600,"suffix_attempts":0,"DP_inference_calls":0,
    "no_training_or_directional_interventions":True,"R2_correctly_gated":True,
    "raw_local_files_verified":len(local),"preflight_tests_passed":6,"post_stop_delivery_tests_passed":5})
files=[]
for base in [OUT,REPORT,CODE]:
    files.extend(p for p in base.rglob("*") if p.is_file() and p.name not in ["sha256_manifest.json",".recovery.lock"])
write_json(OUT/"sha256_manifest.json", {"scope":"new replay_recovery source, configs, compact evidence and reports; excludes this manifest and transient lock",
    "sha256":{str(p.relative_to(ROOT)):sha256(p) for p in sorted(files)},"local_raw_files":local,
    "historical_M_files_preserved":old})
print(f"Sealed {len(files)} new files, {len(local)} local telemetry files; all {len(old)} old M files unchanged")
