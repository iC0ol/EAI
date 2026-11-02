"""CPU-only post-stop audit. No experiment imports, GL, torch or worker launch."""
from pathlib import Path
import ast
import datetime
import hashlib
import importlib.util
import json
import sys

P = Path(__file__).resolve().parents[1]
W = P.parent


def read(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    manifest = read(P/'candidate_manifest.json')
    changed = []
    for group, base in [('files', P), ('sources', Path('/'))]:
        for name, digest in manifest[group].items():
            if sha(base/name) != digest:
                changed.append(group+':'+name)
    old = read(P/'local_only/input_old_evidence_baseline.json')
    old_changed = []
    for name, rec in old.items():
        f = W/'research_kyc_diagnostics_20261029'/name
        st = f.stat()
        if sha(f) != rec['sha256'] or st.st_size != rec['bytes'] or st.st_mtime_ns != rec['mtime_ns']:
            old_changed.append(name)
    state = read(P/'run_state.json')
    stage = read(P/'stages/input.json')
    dispatch = read(P/'dispatch.json')
    stop = read(P/'stop_request.json')
    ledger = [json.loads(x) for x in (P/'call_ledger.jsonl').read_text().splitlines()]
    commands = [json.loads(x) for x in (P/'commands.jsonl').read_text().splitlines()]
    assert state['counts'] == dict(workers=1, make_env=0, renders=0, readPixels=0,
                                   ACT=0, env_steps=0, rollouts=0, backward=0, optimizer=0)
    assert state['active_lease'] is None and stage['exit_code'] == 1
    assert stage == state['stages']['input']
    assert 0 < state['GPU_seconds'] == stage['GPU_seconds'] < 210 < 600
    assert stage['ended_epoch'] < dispatch['deadline_epoch']
    assert len(ledger) == 1 and ledger[0]['kind'] == 'workers' and ledger[0]['permitted']
    assert len(commands) == 1 and commands[0]['event'] == 'FRESH_EXEC'
    assert stop['terminal'] and stop['stage'] == 'input'
    owned = [read(P/'input_supervisor_launch.json')['identity'], stage['identity']]
    identities = []
    for identity in owned:
        f = Path('/proc')/str(identity['pid'])/'stat'
        same = False
        if f.exists():
            fields = f.read_text().rsplit(')', 1)[1].split()
            same = int(fields[19]) == identity['start_ticks'] and fields[0] != 'Z'
        identities.append(dict(pid=identity['pid'], start_ticks=identity['start_ticks'], active=same))
    assert not any(x['active'] for x in identities)
    absent = ['input_result.json', 'input_gate.json', 'model_result.json', 'model_events.jsonl',
              'analysis.json', 'stages/model_started.json', 'stages/model.json']
    assert all(not (P/n).exists() for n in absent)
    assert not list((P/'inputs').glob('*.npz'))
    assert not list((P/'results').rglob('*.png'))
    trace = (P/'logs/input.log').read_text()
    assert "cannot import name 'ROOT' from 'common'" in trace
    assert str(P/'scripts/common.py') in trace
    # Evaluate only the one stdlib-only import statement, NOT experiment_lib.
    source = W/'research_expansion_20261029/reproduction/scripts/experiment_lib.py'
    node = ast.parse(source.read_text()).body[1]
    assert isinstance(node, ast.ImportFrom) and node.module == 'common'
    requested = [a.name for a in node.names]
    assert requested == ['ROOT', 'atomic_json', 'utc']
    spec = importlib.util.spec_from_file_location('common', P/'scripts/common.py')
    diagnostic = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(diagnostic)  # bookkeeping-only module
    previous = sys.modules.get('common')
    try:
        sys.modules['common'] = diagnostic
        try:
            exec(compile(ast.Module(body=[node], type_ignores=[]), '<single-import-CPU-proof>', 'exec'), {})
        except ImportError as exc:
            proof = dict(error_type=type(exc).__name__, missing_ROOT=not hasattr(diagnostic, 'ROOT'),
                         missing_atomic_json=not hasattr(diagnostic, 'atomic_json'),
                         cached_module_is_diagnostic=sys.modules['common'] is diagnostic,
                         no_experiment_lib_body_executed=True)
        else:
            raise AssertionError('CPU import collision was not reproduced')
    finally:
        if previous is None:
            sys.modules.pop('common', None)
        else:
            sys.modules['common'] = previous
    assert not changed and not old_changed
    record = dict(checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        verdict='ACCEPT_EXECUTION_FAILURE_NOT_CHECKPOINT_NO_GO', run_id=state['run_id'],
        frozen_local_files=len(manifest['files']), frozen_sources=len(manifest['sources']),
        old_evidence_files=len(old), changed=changed, old_changed=old_changed,
        counts=state['counts'], GPU_allocation_seconds=state['GPU_seconds'],
        owned_processes=identities, active_lease=None, absent_artifacts=absent,
        import_collision_CPU_proof=proof, raw_traceback_sha256=sha(P/'logs/input.log'),
        protocol_sha256=sha(P/'PROTOCOL.md'), code_manifest_sha256=sha(P/'candidate_manifest.json'),
        input_arrays_or_images_generated=0, model_evidence='NOT_RUN',
        scientific_checkpoint_verdict='NOT_EVALUATED', historic_0_of_32='UNKNOWN',
        new_GL_model_training_calls_from_this_audit=0,
        no_freeze_changes_or_restart=True)
    (P/'artifacts/parent_failure_acceptance.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(record, ensure_ascii=False))


if __name__ == '__main__':
    main()
