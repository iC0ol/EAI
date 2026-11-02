"""CPU-only publication gate for the controlled repair and parent-owned final review."""
from pathlib import Path
import datetime
import hashlib
import json
import re
import subprocess
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
OLD = ROOT / 'render_controlled'
allow = (OLD / 'public_allowlist.txt').read_text().splitlines()
paths = {OLD / x for x in allow if not x.endswith(('.lock', '.tmp'))}
paths.update(OLD / x for x in ['return_receipt.json', 'public_allowlist.txt'])
parent_files = ['.gitignore', 'STATUS.md', 'README.md', '02_联合排障报告.md', '03_下一阶段提示词_冻结模型诊断待批准.md', 'artifacts/deepseek_rounds_verified.json', 'artifacts/parent_render_controlled_audit.json', 'notes/06_Codex受控修复独立验收.md', 'notes/02_交叉讨论与联合优先级.md', 'orchestration/clocks.json', 'orchestration/controlled_followup_receipt.json', 'orchestration/controlled_acceptance.json', 'orchestration/deepseek_active.json', 'scripts/verify_render_controlled_cpu.py', 'scripts/prepare_controlled_publication.py']
paths.update(ROOT / x for x in parent_files)
for turn in ['23_controlled_independent', '24_controlled_final_cross', '25_draft_resolution']:
    paths.update(ROOT / 'discussion' / (turn + ext) for ext in ['_prompt.md', '_response.md', '_metadata.json'])
patterns = {
    'api_key': rb'\bsk-[A-Za-z0-9_-]{16,}',
    'github_token': rb'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})',
    'aws_access_key': rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'raw_pointer': rb'0x[0-9a-fA-F]{9,}',
    'credential_url': rb'https?://[^\s/:]+:[^\s/@]+@',
    'private_key': rb'-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----',
    'bearer_value': rb'(?i)authorization["\s:]+bearer\s+[A-Za-z0-9._-]{20,}',
}
hits, records, arrays = [], [], 0
for p in sorted(paths):
    assert p.is_file() and not p.is_symlink(), p
    rel = p.relative_to(REPO).as_posix()
    assert not {'local_only', 'cache', 'tmp', 'logs', 'env', '__pycache__'} & set(p.relative_to(ROOT).parts)
    ignored = subprocess.run(['git', 'check-ignore', '-q', rel], cwd=REPO)
    assert ignored.returncode == 1, 'Candidate ignored: ' + rel
    data = p.read_bytes()
    chunks = [data]
    if p.suffix == '.npy':
        chunks.append(np.ascontiguousarray(np.load(p, allow_pickle=False)).tobytes()); arrays += 1
    elif p.suffix == '.npz':
        with np.load(p, allow_pickle=False) as z:
            for k in z.files:
                chunks.append(np.ascontiguousarray(z[k]).tobytes()); arrays += 1
    elif p.suffix == '.png':
        with Image.open(p) as im:
            chunks.append(np.asarray(im).tobytes()); arrays += 1
    for name, pattern in patterns.items():
        if any(re.search(pattern, c) for c in chunks):
            hits.append({'path': rel, 'pattern': name})
    records.append({'path': rel, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
assert not hits, json.dumps(hits)
report = {'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'files': records, 'total_bytes': sum(x['bytes'] for x in records),
          'decoded_arrays_or_images': arrays, 'credential_pattern_hits': hits,
          'limitation': 'Known-pattern scan, not a proof of absence of all sensitive data; explicit scope allowlist also applied.',
          'excluded': 'Raw CLI, addresses/XML, machine/active-child snapshots, third-party assets, runtimes, weights, caches, locks',
          'git_index_owner': 'main'}
(ROOT / 'artifacts/controlled_publication_gate.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'files': len(records), 'bytes': report['total_bytes'], 'decoded_arrays_or_images': arrays, 'hits': len(hits)}))
