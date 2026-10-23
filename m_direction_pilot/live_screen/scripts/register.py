import subprocess
from live_screen.io import ROOT,OUT,BASE,read_json,write_json,sha256,git,now

protocol=git('rev-parse','58ac609')
paths=['configs/protocol.json','reports/protocol.md','reports/task_authority.md','outputs/frozen_state_manifest.csv',
       'outputs/branch_plan.csv','outputs/action_eligibility.csv','outputs/resource_audit.json']
for p in paths:
    blob=subprocess.check_output(['git','show',f'{protocol}:m_direction_pilot/live_screen/{p}'],cwd=ROOT.parent.parent)
    assert blob==(ROOT/p).read_bytes(),p
r=read_json(OUT/'resource_audit.json')
write_json(OUT/'registration.json',{'protocol_commit':protocol,'base':BASE,'utc':now(),'new_simulation_steps':0,
    'new_suffixes':0,'frozen_files':{p:sha256(ROOT/p) for p in paths},
    **{k:r[k] for k in ['historical_files','assets','upstream_files','old_branch_heads']}})
print(protocol)
