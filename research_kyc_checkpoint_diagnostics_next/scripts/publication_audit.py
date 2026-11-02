"""Explicit publication allowlist only; never stages or publishes by itself."""
from pathlib import Path
import datetime
import hashlib
import json
import re

P = Path(__file__).resolve().parents[1]
OUTPUTS = {'publication_allowlist.txt', 'publication_secret_scan.json', 'publication_manifest.json'}
EXCLUDED_PARTS = {'logs', 'local_only', 'cache', 'tmp', '__pycache__'}
RULES = {
    'private_key': r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
    'api_token': r'\bsk-[A-Za-z0-9_-]{20,}',
    'github_token': r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})',
    'aws_access_key': r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'bearer_value': r'(?i)bearer\s+[A-Za-z0-9._~+/-]{20,}',
    'credential_literal': r'''(?i)(?:api[_-]?key|password|access[_-]?token|refresh[_-]?token|client[_-]?secret)["']?\s*[:=]\s*["'][A-Za-z0-9_./+\-=]{20,}["']''',
    'native_pointer_literal': r'\b0x[0-9a-fA-F]{10,}\b',
    'embedded_mujoco_xml': r'<mujoco\s+model\s*=',
    'url_password': r'https?://[^\s/:@]+:[^\s/@]+@',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    names = (P/'publication_allowlist.txt').read_text().splitlines()
    assert names == sorted(set(names)) and OUTPUTS <= set(names)
    records, findings = [], []
    for name in names:
        relative = Path(name)
        assert not relative.is_absolute() and '..' not in relative.parts
        assert not EXCLUDED_PARTS.intersection(relative.parts)
        assert not name.endswith(('_raw.jsonl', '_metadata.json'))
        assert name != 'discussion/session.json'
        if name in OUTPUTS - {'publication_allowlist.txt'}:
            continue
        f = P/relative
        assert f.is_file() and not f.is_symlink()
        assert f.stat().st_size < 2*1024*1024
        content = f.read_text(encoding='utf-8')
        for label, rule in RULES.items():
            for match in re.finditer(rule, content):
                findings.append(dict(path=name, line=content[:match.start()].count('\n')+1, rule=label))
        records.append(dict(path=name, bytes=f.stat().st_size, sha256=digest(f)))
    # No values are printed on a finding; the publisher inspects locally.
    scan = dict(checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        passed=not findings, findings=findings, actual_values_disclosed=False,
        rules=list(RULES), text_files_scanned=len(records), numeric_arrays=0, images=0,
        original_runtime_results='no model/input outputs generated',
        excluded=['raw CLI', 'provider metadata and session', 'credentials', 'native addresses/XML',
                  'runtime/cache', 'weights/datasets', 'full machine query records'],
        limitations='Pattern scan plus explicit allowlist; not a proof of absence of every possible secret.')
    (P/'publication_secret_scan.json').write_text(json.dumps(scan, ensure_ascii=False, indent=2)+'\n')
    assert not findings, findings
    f = P/'publication_secret_scan.json'
    records.append(dict(path=f.name, bytes=f.stat().st_size, sha256=digest(f)))
    records.sort(key=lambda x: x['path'])
    manifest = dict(checked_utc=scan['checked_utc'], allowed_files=len(names), files=records,
        self_hash_excluded='publication_manifest.json',
        review_status='parent independent + real DeepSeek independent/cross; see report and receipts',
        source_code_status='frozen v2 kept unchanged despite terminal import error',
        Git_index_owner='parent', new_experiment_authorized=False)
    (P/'publication_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(passed=True, allowed_files=len(names), hashed_files=len(records),
                         total_bytes=sum(x['bytes'] for x in records), findings=0)))


if __name__ == '__main__':
    main()
