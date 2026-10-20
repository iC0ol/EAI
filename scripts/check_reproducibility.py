"""Regenerate the entire data delivery independently and compare exact data/image bytes."""
import hashlib
import json
from pathlib import Path
import tempfile
import yaml
from spatial_pilot.make_dataset import generate

ROOT = Path(__file__).resolve().parents[1]
config = yaml.safe_load((ROOT/'configs/pilot.yaml').read_text())
with tempfile.TemporaryDirectory(prefix='reproduction-', dir=ROOT/'.cache/tmp') as temporary:
    second = Path(temporary)
    manifest = generate(config,second,ROOT)
    paths = sorted(p.relative_to(ROOT) for p in (ROOT/'data').rglob('*') if p.is_file())
    new_paths = sorted(p.relative_to(second) for p in (second/'data').rglob('*') if p.is_file())
    mismatch = []
    if paths != new_paths:
        mismatch.append('different data file lists')
    for path in paths:
        if not (second/path).exists() or (ROOT/path).read_bytes() != (second/path).read_bytes():
            mismatch.append(str(path))
    result = {'seed':config['seed'], 'compared_files':len(paths), 'mismatches':mismatch,
              'pass':not mismatch, 'scope':'all data files: original PNGs, scene JSON, public inputs and private labels; timestamps in reports excluded'}
    (ROOT/'reports/reproducibility.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    if mismatch:
        raise SystemExit(1)
