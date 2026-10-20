"""Download only the pinned public model. Save SHA256/size manifest; no scene reads."""
import hashlib
import json
import time
from pathlib import Path
import yaml
from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]
config = yaml.safe_load((ROOT/'configs/vlm_smoke.yaml').read_text())
info = json.loads((ROOT/'reports/phase3/model_source.json').read_text())
assert info['sha'] == config['model_revision']
destination = ROOT/config['model_local_dir']
start = time.perf_counter()
snapshot_download(repo_id=config['model_id'],revision=config['model_revision'],
                  local_dir=destination,max_workers=2,
                  allow_patterns=['*.json','*.safetensors','*.txt','README.md'],token=False)
download_seconds = time.perf_counter()-start
rows = []
for entry in info['files']:
    name = entry['rfilename']
    if name == '.gitattributes':
        continue
    path = destination/name
    if not path.is_file():
        raise FileNotFoundError(path)
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(16*1024*1024),b''):
            digest.update(chunk)
    actual = digest.hexdigest()
    expected = entry.get('lfs',{}).get('sha256')
    if expected and actual != expected:
        raise ValueError(f'Weight SHA256 mismatch: {name}')
    if path.stat().st_size != entry['size']:
        raise ValueError(f'File size mismatch: {name}')
    rows.append({'file':name,'size_bytes':path.stat().st_size,'sha256':actual,'expected_lfs_sha256':expected})
result = {'model_id':config['model_id'],'model_revision':config['model_revision'],
          'source':info['model_url'],'download_seconds':download_seconds,'files':rows,
          'total_bytes':sum(row['size_bytes'] for row in rows)}
(ROOT/'reports/phase3/model_files.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='files'},indent=2))
