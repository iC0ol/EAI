"""Freeze all Part A/B inputs, truth, rules, order and runtime after unscored 8B smoke."""
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
from spatial_pilot.scale_io import digest
from spatial_pilot.control_audit import environment

root=Path(__file__).resolve().parents[1];reports=root/'reports/phase3_7'
assert not (root/'outputs/phase3_7/vlm8b_a').exists() and not (root/'outputs/phase3_7/vlm4b_new').exists()
assert json.loads((reports/'generation_manifest.json').read_text())['status']=='completed'
tree=ET.parse(reports/'tests_before_final.xml');assert all(int(s.get(k,'0'))==0 for s in tree.iter('testsuite') for k in ['failures','errors','skipped'])
smoke=json.loads((root/'outputs/phase3_7/smoke8b/session.json').read_text());assert smoke['status']=='completed' and smoke['completed_queries']==1
row=json.loads((root/'outputs/phase3_7/smoke8b/predictions.jsonl').read_text());assert row['parse_ok'] and row['vision_forward_calls']==1
assert smoke['actual_parameter_dtypes']==['torch.bfloat16'] and smoke['quantization'] is None
runtime={'frozen_at':datetime.now(timezone.utc).isoformat(),
         'vlm_environment':environment(root,'.venv-vlm/bin/python','reports/phase3/environment.json'),
         'geometry_environment':environment(root,'.venv/bin/python','reports/dependencies.json'),
         'smoke_session_sha256':digest(root/'outputs/phase3_7/smoke8b/session.json'),
         'model8b_manifest_sha256':digest(reports/'model8b_files.json'),
         'requirements_vlm_lock_sha256':digest(root/'requirements-vlm.lock')}
with (reports/'environment_frozen.json').open('x') as f:json.dump(runtime,f,indent=2);f.write('\n')
public=[root/'configs/phase3_7.yaml',*sorted((root/'prompts/phase3_7').glob('*')),
        *sorted((root/'diagnostics/phase3_7/inputs').glob('*.jsonl')),
        *sorted((root/'diagnostics/phase3_7/images').glob('*.png')),
        *sorted((root/'diagnostics/phase3_6/images').glob('*.png')),
        *[root/f'src/spatial_pilot/{n}.py' for n in ['scale_io','scale_infer','scale_rgb','scale_rgb_run','infer_vlm','vlm_io','diagnostic_io']],
        root/'scripts/run_phase3_7.sh']
frozen={'frozen_at':runtime['frozen_at'],'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'files':{str(p.relative_to(root)):digest(p) for p in public},
        'order':{d:[json.loads(l)['query_id'] for l in (root/f'diagnostics/phase3_7/inputs/{d}.jsonl').read_text().splitlines()] for d in ['old16','new24']},
        'policy':'One greedy call per model per formal input; 4B old16 reused unchanged. No prompt tuning, sample replacement, rerun or truth repair.'}
with (root/'diagnostics/phase3_7/inputs/frozen_public.json').open('x') as f:json.dump(frozen,f,indent=2);f.write('\n')
private=[*sorted((root/'diagnostics/phase3_7/private').rglob('*.json*')),root/'src/spatial_pilot/scale_scenes.py',root/'src/spatial_pilot/scale_evaluate.py',
         reports/'model8b_files.json',reports/'environment_frozen.json',reports/'tests_before_final.xml',
         root/'diagnostics/phase3_6/private/private_labels.jsonl',root/'outputs/phase3_6/predictions.jsonl']
with (reports/'frozen_run.json').open('x') as f:json.dump({**frozen,'private_files':{str(p.relative_to(root)):digest(p) for p in private}},f,indent=2);f.write('\n')
print('Frozen Part A/B data, labels, order, prompt, RGB rules, VLM parameters and environments after successful unscored smoke.')
