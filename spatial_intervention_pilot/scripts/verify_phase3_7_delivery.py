"""Final immutable-artifact/weight audit, with reports confined to Phase 3.7."""
import json
from pathlib import Path
from spatial_pilot.scale_audit import audit
from spatial_pilot.scale_io import digest,verify_frozen

root=Path(__file__).resolve().parents[1];reports=root/'reports/phase3_7'
audit(output_name='environment_after.json')
verify_frozen(root)
freeze=json.loads((reports/'frozen_run.json').read_text())
assert all(digest(root/n)==h for n,h in freeze['private_files'].items())
weights=json.loads((reports/'model8b_files.json').read_text())
for item in weights['files']:
    p=root/'.cache/phase3_7/model8b'/item['file']
    assert p.stat().st_size==item['size_bytes'] and digest(p)==item['sha256']
with (reports/'model8b_preservation_after.json').open('x') as f:
    json.dump({'model_revision':weights['model_revision'],'files_checked':len(weights['files']),'all_match':True},f,indent=2);f.write('\n')
with (reports/'raw_output_sha256.json').open('x') as f:
    json.dump({str(p.relative_to(root)):digest(p) for p in sorted((root/'outputs/phase3_7').rglob('*')) if p.is_file()},f,indent=2);f.write('\n')
print('Historical artifacts, both environments, original protected system files, both model filesets and frozen inputs verified.')
