"""Extra 2.5 cm check for the review set; do not infer continuous unreachability."""
import json
from pathlib import Path
import yaml
from spatial_pilot.edits import apply_edits
from spatial_pilot.oracle import solve
from spatial_pilot.scenes import STATES

ROOT = Path(__file__).resolve().parents[1]
config = yaml.safe_load((ROOT/'configs/pilot.yaml').read_text())
labels = [json.loads(line) for line in (ROOT/'data/private_labels.jsonl').read_text().splitlines()]
results = []
for label in labels:
    sid = label['sample_id']
    scene = json.loads((ROOT/f'data/scenes/{sid}/scene.json').read_text())
    for state,names in STATES.items():
        result = solve(apply_edits(scene,names),.025,config['buffer_quad_segs'],config['contact_epsilon_m'])
        expected = label['labels']['F_'+state]
        results.append({'sample_id':sid,'state':state,'resolution_m':.025,'passable':result['passable'],
                        'agrees_with_primary':result['passable'] == expected,
                        'witness_min_clearance_m':result['path_min_clearance_m']})
report = {'checked_states':len(results),'disagreements':sum(not row['agrees_with_primary'] for row in results),
          'continuous_unreachability_claimed':False,'results':results}
(ROOT/'reports/resolution_audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='results'},indent=2))
if report['disagreements']:
    raise SystemExit('Finer-grid disagreement: quarantine affected labels before evaluation.')
