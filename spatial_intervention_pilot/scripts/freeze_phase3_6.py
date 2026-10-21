"""Freeze after geometry and tests pass, before the only official inference run."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from spatial_pilot.vlm_io import sha256

root = Path(__file__).resolve().parents[1]
report = root/'reports/phase3_6'
assert not (root/'outputs/phase3_6').exists(), 'Inference already started'
assert json.loads((report/'generation_manifest.json').read_text())['status'] == 'completed'
tree = ET.parse(report/'tests_before.xml')
assert all(int(s.attrib.get(k, 0)) == 0 for s in tree.iter('testsuite') for k in ['failures', 'errors', 'skipped'])
assert (report/'environment_before.json').is_file()
assert (root/'prompts/phase3_6/poststate_reach_en_v1.txt').read_bytes() == (root/'prompts/poststate_reach_en_v1.txt').read_bytes()
public_files = [root/'configs/phase3_6.yaml', root/'prompts/phase3_6/poststate_reach_en_v1.txt',
                root/'prompts/phase3_6/version_record.json', root/'scripts/run_phase3_6.sh',
                *sorted((root/'diagnostics/phase3_6/images').glob('*.png')),
                root/'diagnostics/phase3_6/inputs/public_inputs.jsonl', root/'diagnostics/phase3_6/inputs/order.json',
                root/'src/spatial_pilot/control_infer.py', root/'src/spatial_pilot/control_io.py',
                root/'src/spatial_pilot/diagnostic_io.py', root/'src/spatial_pilot/infer_vlm.py', root/'src/spatial_pilot/vlm_io.py']
common = {'frozen_at': datetime.now(timezone.utc).isoformat(),
          'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
          'files': {str(p.relative_to(root)): sha256(p) for p in public_files},
          'policy': 'Exactly one greedy call per frozen input, in frozen order. No retries, prompt changes or truth-based repairs.'}
with (root/'diagnostics/phase3_6/inputs/frozen_public.json').open('x') as f:
    json.dump(common, f, indent=2); f.write('\n')
private_files = [*sorted((root/'diagnostics/phase3_6/private').rglob('*.json*')),
                 root/'src/spatial_pilot/control_scenes.py', root/'src/spatial_pilot/control_evaluate.py',
                 root/'configs/phase3_6.yaml', report/'tests_before.xml', report/'generation_manifest.json']
with (report/'frozen_run.json').open('x') as f:
    json.dump({**common, 'private_files': {str(p.relative_to(root)): sha256(p) for p in private_files}}, f, indent=2); f.write('\n')
print('Frozen 16 images, manifest, order, prompt, config, inference source and private oracle artifacts.')
