"""Read-only baseline/environment audit; new Phase 3.7 reports only. No installations."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import runpy
import subprocess

from .vlm_io import sha256

ROOT = Path(__file__).resolve().parents[2]


def environment(root, executable, baseline):
    code = 'import sys,json,importlib.metadata as m; print(json.dumps({"python":sys.version,"packages":{d.metadata["Name"]:d.version for d in m.distributions()}}))'
    import os
    env = dict(os.environ, PYTHONPATH=str(root/'src'), PYTHONNOUSERSITE='1')
    current = json.loads(subprocess.check_output([str(root/executable), '-c', code], text=True, env=env))
    def normalize(values):
        return {re.sub(r'[-_.]+', '-', k).lower(): v for k, v in values.items()}
    before = json.loads((root/baseline).read_text())['packages']
    current['same_as_historical_packages'] = normalize(current['packages']) == normalize(before)
    if not current['same_as_historical_packages']:
        raise ValueError(f'Environment changed: {executable}')
    return current


def audit(root=ROOT, output_name='environment_before.json'):
    root = Path(root)
    historic = json.loads((root/'reports/phase3_7/preserved_before.json').read_text())
    changed = [n for n, h in historic['files'].items() if not (root/n).is_file() or sha256(root/n) != h]
    if changed:
        raise ValueError(f'Historical artifacts changed: {changed}')
    system = runpy.run_path(str(root/'scripts/audit_environment.py'), run_name='readonly')['protected_manifest']()
    original = json.loads((root/'reports/protected_before.json').read_text())
    system_changed = [p for p in set(system) | set(original) if system.get(p) != original.get(p)]
    if system_changed:
        raise ValueError(f'Protected system files changed: {system_changed}')
    model = json.loads((root/'reports/phase3/model_files.json').read_text())
    verified = []
    for item in model['files']:
        p = root/'.cache/vlm/model'/item['file']
        if p.stat().st_size != item['size_bytes'] or sha256(p) != item['sha256']:
            raise ValueError(f'Pinned model artifact changed: {p.name}')
        verified.append(item['file'])
    result = {'time': datetime.now(timezone.utc).isoformat(), 'historical_files_checked': len(historic['files']),
              'historical_files_changed': changed, 'protected_system_files_checked': len(system),
              'protected_system_files_changed': system_changed, 'model_files_verified': verified,
              'model_revision': model['model_revision'],
              'geometry_environment': environment(root, '.venv/bin/python', 'reports/dependencies.json'),
              'vlm_environment': environment(root, '.venv-vlm/bin/python', 'reports/phase3/environment.json'),
              'gpu': subprocess.check_output(['nvidia-smi', '--query-gpu=name,driver_version,memory.total,memory.used', '--format=csv'], text=True),
              'disk': subprocess.check_output(['df', '-h', str(root)], text=True),
              'scope': 'Historical tracked project files, model hashes, environment metadata and selected 113 system/robot files; not a full filesystem audit.'}
    destination = root/'reports/phase3_7'/output_name
    with destination.open('x') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps({k: result[k] for k in ['historical_files_checked', 'historical_files_changed', 'protected_system_files_changed', 'model_revision']}, indent=2))
    return result


if __name__ == '__main__':
    audit()
