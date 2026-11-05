"""Build a bounded public evidence package. CPU/file operations only; never run experiments."""
from pathlib import Path
from datetime import datetime, timezone
import collections
import hashlib
import io
import json
import re
import zipfile

import numpy as np

P = Path(__file__).resolve().parents[1]
OUT = P / 'publication'
OUT.mkdir(exist_ok=True)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    now = datetime.now(timezone.utc).isoformat()
    frozen = json.loads((P / 'candidate_manifest.json').read_text())
    assert sha(P / 'candidate_manifest.json') == '3179c07a0cf77758d4dff01d57ffebcca1af0c11bc4034a0753b32610f40b530'
    assert sha(P / 'PROTOCOL_CANDIDATE.md') == '8773f4b7733335898d2bed5803f0d7729798896892abe6bdefd604a1f71a8ed8'
    for rel, digest in frozen['files'].items():
        assert sha(P / rel) == digest, rel
    end = json.loads((P / 'artifacts/parent_final_execution_integrity.json').read_text())
    for rel, digest in end['stage_SHA256'].items():
        assert sha(P / rel) == digest, rel
    scope = json.loads((P / 'scope_state.json').read_text())
    assert scope['active_lease'] is None and scope['active_rollout'] is None
    assert scope['counts'] == end['counts']
    assert scope['GPU_seconds'] == end['GPU_seconds']
    inactive = []
    for row in [json.loads(x) for x in (P / 'commands.jsonl').read_text().splitlines()]:
        for key in ('identity', 'supervisor'):
            identity = row[key]
            proc = Path('/proc') / str(identity['pid']) / 'stat'
            same_process = False
            if proc.exists():
                stat = proc.read_text().rsplit(')', 1)[1].split()
                same_process = int(stat[19]) == identity['start_ticks'] and stat[0] != 'Z'
            assert not same_process, (row['phase'], key)
            inactive.append({'phase': row['phase'], 'role': key, 'same_process_active': False})

    receipts = []
    for f in sorted((P / 'discussion').glob('*_metadata.json')):
        d = json.loads(f.read_text())
        assert d['exit_code'] == 0 and d['result_status'] == 'success', f.name
        turn = d['turn']
        receipts.append({
            'turn': turn, 'started_utc': d['started_utc'], 'ended_utc': d['ended_utc'],
            'exit_code': d['exit_code'], 'result_status': d['result_status'],
            'response_model_fields': d['response_model_fields'],
            'permission_denial_count': len(d.get('permission_denials', [])),
            'prompt_sha256': sha(P / 'discussion' / (turn + '_prompt.md')),
            'response_sha256': sha(P / 'discussion' / (turn + '_response.md')),
            'source_metadata_sha256': sha(f),
        })
    assert len(receipts) == 14
    write(OUT / 'deepseek_review_receipts.json', {
        'kind': 'derived_sanitized_receipts_not_raw_CLI', 'turns': receipts,
        'omitted': ['session identifier', 'command line', 'account and usage fields', 'raw tool streams'],
        'binary_review_limit': 'Codex decoded/recomputed arrays. DeepSeek reviewed records, images and SHA-bound numeric transcriptions; it did not independently decode NPZ.',
    })
    report_paths = ['02_联合根因报告.md', 'notes/17_Codex最终独立验收与六问.md',
                    'notes/18_最终交叉验收与报告勘误.md',
                    'discussion/50_final_independent_response.md', 'discussion/51_final_cross_response.md']
    write(OUT / 'final_review_record.json', {
        'utc': now, 'state': 'EXPERIMENTS_AND_DUAL_REVIEW_COMPLETE',
        'decision': 'STOP_CURRENT_CHECKPOINT_RECOVERY_AND_DEPENDENT_F_EXPERIMENTS',
        'historical_0_of_32_cause': 'NOT_UNIQUELY_IDENTIFIED',
        'deepseek_final_cross': 'ACCEPT_FINAL_CROSS_CONCLUSION_WITH_REPORT_CORRECTIONS',
        'three_report_corrections_applied_by_Codex': True,
        'claim_DeepSeek_reviewed_final_report_file_SHA': False,
        'file_SHA256': {rel: sha(P / rel) for rel in report_paths},
        'candidate_manifest_sha256': sha(P / 'candidate_manifest.json'),
        'protocol_sha256': sha(P / 'PROTOCOL_CANDIDATE.md'),
        'GPU_seconds': scope['GPU_seconds'], 'counts': scope['counts'],
        'current_process_check': inactive, 'additional_experiments_authorized': False,
    })

    selected = set()

    def add(rel):
        path = P / rel
        assert path.is_file() and not path.is_symlink(), rel
        selected.add(str(path.relative_to(P)))

    top = ['.gitignore', 'README.md', '02_联合根因报告.md', '00_本轮用户任务书_原文.md',
           'AGENTS.md', 'PROTOCOL_CANDIDATE.md', 'SOURCE_AUDIT.md', 'STORAGE_AND_STOP_PLAN.md',
           'CPU_PREPARATION_AUTHORIZATION.json', 'CPU_PREPARATION_REPORT.md',
           'CANDIDATE_SHA256SUMS.txt', 'candidate_manifest.json', 'source_manifest.json',
           'call_plan.json', 'phase_plan.json', 'rollout_plan.json', 'root_plan.json', 'sample_plan.json',
           'run.py', 'allocation_gate.json', 'engineering_gate.json', 'science_gate.json', 'expert_gate.json',
           'scope_state.json', 'science_clock.json', 'experiments_completion.json',
           'gpu_preflight_result.json', 'expert_result.json', 'policy_result.json',
           'c-local_result.json', 'c-official_result.json', 'policy_strict_load.json', 'preflight_strict_load.json',
           'commands.jsonl', 'resources.jsonl', 'call_ledger.jsonl', 'model_events.jsonl']
    for rel in top:
        add(rel)
    patterns = {
        'kyc_grasp': '*.py', 'inputs': '*.npz', 'notes': '*.md', 'figures': '*',
        'artifacts': '*', 'repairs': '*', 'dispatch': '*.json', 'phase_reviews': '*.json',
        'stages': '*.json', 'review_packets': '*.jsonl',
    }
    for folder, pattern in patterns.items():
        for path in (P / folder).rglob(pattern):
            if path.is_file():
                add(path.relative_to(P))
    for path in (P / 'results').rglob('*'):
        if path.is_file() and path.suffix in ('.json', '.jsonl', '.npz', '.png'):
            add(path.relative_to(P))
    for path in (P / 'roots').rglob('*'):
        if path.is_file() and path.suffix in ('.json', '.npy'):
            add(path.relative_to(P))
    for pattern in ('*_prompt.md', '*_response.md'):
        for path in (P / 'discussion').glob(pattern):
            add(path.relative_to(P))
    for pattern in ('parent_*.py', 'plot_grasp_diagnostics.py', 'freeze_candidate.py', 'build_publication.py'):
        for path in (P / 'scripts').glob(pattern):
            add(path.relative_to(P))
    for path in (P / 'orchestration').glob('*_completion.json'):
        add(path.relative_to(P))
    for rel in ['publication/deepseek_review_receipts.json', 'publication/final_review_record.json']:
        add(rel)

    # pthread identifiers may be address-sized. Keep local originals unchanged and
    # publish explicitly identified derivative copies wherever identifiers occur.
    native_key = re.compile(r'(?:thread_id|object_id|.*address.*|.*pointer.*|.*handle.*|py_?id)', re.I)
    replacements = {}
    redactions = []
    for rel in sorted(selected.copy()):
        path = P / rel
        if path.suffix not in ('.json', '.jsonl'):
            continue
        data = (json.loads(path.read_text()) if path.suffix == '.json'
                else [json.loads(line) for line in path.read_text().splitlines() if line.strip()])
        edits = collections.Counter()

        def clean(value):
            if isinstance(value, dict):
                output = {}
                for key, item in value.items():
                    if native_key.fullmatch(key) and isinstance(item, int) and abs(item) >= 2**40:
                        label = replacements.setdefault(str(item), 'native_identifier_' + str(len(replacements) + 1))
                        output[key] = label
                        edits[key] += 1
                    else:
                        output[key] = clean(item)
                return output
            if isinstance(value, list):
                return [clean(x) for x in value]
            return value

        result = clean(data)
        if edits:
            public_rel = 'publication/redacted/' + rel
            destination = P / public_rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == '.json':
                write(destination, result)
            else:
                destination.write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in result))
            selected.remove(rel)
            add(public_rel)
            redactions.append({'local_original': rel, 'original_sha256': sha(path),
                               'public_derivative': public_rel, 'public_sha256': sha(destination),
                               'replaced_fields_and_counts': dict(edits),
                               'scientific_numeric_values_changed': False})
    write(OUT / 'redactions.json', {'purpose': 'omit address-sized native identifiers; originals remain immutable locally',
                                   'files': redactions})
    add('publication/redactions.json')

    failures = []
    text_count = array_count = 0
    secret_patterns = {
        'API_token': r'(?<![\w-])(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{30,})',
        'private_key': r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
        'literal_bearer': r'(?i)Bearer\s+[A-Za-z0-9._-]{24,}',
        'native_hex_address': r'\b0x[0-9a-fA-F]{10,16}\b',
        'XML_content': r'<mujoco(?:\s|>)',
    }
    prohibited_parts = {'env', 'venv', '.venv', 'cache', 'tmp', '__pycache__', 'local_only', 'logs'}
    prohibited_suffixes = {'.xml', '.pt', '.pth', '.hdf5', '.h5', '.pyc'}
    for rel in sorted(selected):
        path = P / rel
        if prohibited_parts.intersection(path.relative_to(P).parts) or path.suffix in prohibited_suffixes:
            failures.append({'file': rel, 'rule': 'prohibited_path'})
        if path.stat().st_size >= 100 * 1024 * 1024:
            failures.append({'file': rel, 'rule': 'oversized_file'})
        if path.suffix in ('.npz', '.npy'):
            if path.suffix == '.npz':
                with zipfile.ZipFile(path) as archive:
                    headers = [archive.read(name)[:65536] for name in archive.namelist()]
            else:
                with path.open('rb') as handle:
                    headers = [handle.read(65536)]
            for header in headers:
                handle = io.BytesIO(header)
                version = np.lib.format.read_magic(handle)
                shape, fortran, dtype = np.lib.format._read_array_header(handle, version)
                if dtype.hasobject or dtype.kind not in 'buifc':
                    failures.append({'file': rel, 'rule': 'non_numeric_array'})
                array_count += 1
        elif path.suffix not in ('.png',):
            content = path.read_text()
            text_count += 1
            for name, pattern in secret_patterns.items():
                for match in re.finditer(pattern, content):
                    failures.append({'file': rel, 'rule': name, 'line': content.count('\n', 0, match.start()) + 1})

    # Links in the two final entry points must resolve to a published file.
    for rel in ('README.md', '02_联合根因报告.md'):
        for target in re.findall(r'\]\(([^)]+)\)', (P / rel).read_text()):
            if target.startswith(('https://', 'http://', '#')):
                continue
            linked = (Path(rel).parent / target.split('#')[0]).as_posix()
            if linked not in selected and linked not in ('publication/manifest.json', 'publication/scan.json'):
                failures.append({'file': rel, 'rule': 'unpublished_link', 'target': target})

    scan = {
        'utc': now, 'status': 'PASS' if not failures else 'FAIL', 'failures': failures,
        'text_files_scanned': text_count, 'numeric_array_headers_checked': array_count,
        'native_identifier_derivative_files': len(redactions),
        'rules': list(secret_patterns) + ['prohibited_paths', 'numeric_arrays_only', 'entrypoint_links'],
        'limitations': 'Pattern and header checks supplement an explicit path allowlist; not a universal secrecy proof.',
        'frozen_candidate_files_rechecked': len(frozen['files']), 'all_workers_inactive': True,
    }
    write(OUT / 'scan.json', scan)
    if failures:
        print(json.dumps(scan, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    add('publication/scan.json')
    allowlist = sorted(selected | {'publication/allowlist.txt', 'publication/manifest.json'})
    (OUT / 'allowlist.txt').write_text('\n'.join(allowlist) + '\n')
    manifest = {
        'utc': now, 'kind': 'FINAL_PUBLICATION_ALLOWLIST',
        'files': {rel: {'sha256': sha(P / rel), 'bytes': (P / rel).stat().st_size}
                  for rel in allowlist if rel != 'publication/manifest.json'},
        'self_hash_excluded': 'Git commit binds this manifest; avoid self-reference.',
        'private_material_retained_locally': ['XML', 'RNG snapshots', 'native-address mappings', 'full CLI streams',
                                            'credentials', 'usage/automation state', 'runtimes', 'full datasets and weights'],
        'original_result_hashes_and_redacted_derivatives': 'publication/redactions.json',
        'historical_preparation_files_are_not_current_authorization': True,
    }
    write(OUT / 'manifest.json', manifest)
    print(json.dumps({'status': 'PASS', 'files': len(allowlist), 'bytes': sum((P / r).stat().st_size for r in allowlist),
                      'redacted_copies': len(redactions), 'numeric_array_headers': array_count,
                      'candidate_files_unchanged': len(frozen['files'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
