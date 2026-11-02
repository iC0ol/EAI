"""Fail-closed, shared two-stage authorization and cumulative budget ledger."""
from common import *


def gate(stage, full=False):
    require(stage in ['input', 'model'], 'invalid stage')
    manifest = read(P/'candidate_manifest.json')
    reviews = read(P/'review_gate.json')
    dispatch = read(P/'dispatch.json')
    require(manifest and reviews and dispatch, 'NO_RUN_AUTHORIZATION: preparation only')
    manifest_sha = sha(P/'candidate_manifest.json')
    protocol_sha = sha(P/'PROTOCOL.md')
    require(reviews.get('state') == 'APPROVED', 'final double review absent')
    for reviewer in ['codex', 'deepseek']:
        item = reviews.get(reviewer, {})
        require(item.get('decision') == 'APPROVE'
                and item.get('protocol_sha256') == protocol_sha
                and item.get('code_manifest_sha256') == manifest_sha,
                'protocol/code review hash mismatch: ' + reviewer)
        require(item.get('evidence_file') and sha(P/item['evidence_file']) == item.get('evidence_sha256'),
                'missing review evidence')
    require(dispatch.get('mode') == 'RUN' and dispatch.get('executor') == EXECUTOR,
            'wrong dispatch or executor/model declaration')
    require(dispatch.get('protocol_sha256') == protocol_sha == manifest['protocol_sha256']
            and dispatch.get('code_manifest_sha256') == manifest_sha,
            'dispatch not bound to exact code/protocol')
    require(dispatch.get('caps') == CAPS and dispatch.get('GPU_seconds') == 600,
            'immutable cumulative caps changed')
    require(dispatch.get('run_id') and dispatch.get('input_stage_authorized') is True,
            'missing unique RUN id')
    require(dispatch['dispatch_epoch'] <= time.time()
            and dispatch['deadline_epoch'] == dispatch['dispatch_epoch'] + 8*3600
            and time.time() < dispatch['deadline_epoch'], 'dispatch deadline expired/changed')
    identity = os.environ.get('CODEX_THREAD_ID')
    require(identity in [None, EXECUTOR['thread_id']], 'wrong executor thread')
    for name, digest in manifest['files'].items():
        require(sha(P/name) == digest, 'frozen local file changed: ' + name)
    if full:
        for name, digest in manifest['sources'].items():
            require(sha(Path(name)) == digest, 'read-only source changed: ' + name)
    if stage == 'model':
        input_gate(dispatch, manifest_sha)
    return dispatch


def input_gate(dispatch, manifest_sha):
    approval = read(P/'input_gate.json')
    result = read(P/'input_result.json')
    state = read(P/'run_state.json')
    require(approval and result and state, 'parent input approval absent')
    require(approval.get('decision') == 'APPROVE' and approval.get('actual_images_viewed') is True
            and approval.get('CPU_originals_checked') is True
            and approval.get('reviewer_thread_id') == '01a18138-0f15-76b2-b5cf-20e1722782a9',
            'parent visual/CPU input review incomplete')
    require(approval.get('review_evidence_file')
            and sha(P/approval['review_evidence_file']) == approval.get('review_evidence_sha256'),
            'parent input review evidence missing/changed')
    require(approval.get('run_id') == dispatch['run_id']
            and approval.get('code_manifest_sha256') == manifest_sha
            and approval.get('input_result_sha256') == sha(P/'input_result.json'),
            'input gate not bound to this RUN/code/result')
    require(result.get('state') == 'COMPLETE_HEALTHY_PENDING_PARENT'
            and result.get('all_health_pass') is True, 'saved inputs failed health')
    require(not (P/'results/input/fatal.json').exists(), 'late natural-destructor fatal after input result')
    actual_files = {str(f.relative_to(P)) for directory in [P/'inputs', P/'results/input']
                    for f in directory.rglob('*') if f.is_file()}
    require(actual_files == set(result['input_files']), 'input artifact set changed after snapshot')
    require(approval.get('input_files') == result['input_files']
            and approval.get('source_hashes') == result['source_hashes']
            == read(P/'candidate_manifest.json')['sources'], 'input/source gate hashes differ')
    require([x['sample'] for x in result['samples']] == [0, 1, 4, 5]
            and all(len(x['frames']) == 3 and all(y['health'] for y in x['frames']) for x in result['samples']),
            'input gate requires all four states/three original entries')
    require(all(('inputs/sample_%02d.npz' % j) in result['input_files'] for j in [0, 1, 4, 5]),
            'missing canonical model inputs')
    for name, digest in result['input_files'].items():
        require(sha(P/name) == digest, 'saved input changed: ' + name)
    previous = state.get('stages', {}).get('input', {})
    lease = state.get('active_lease')
    require(previous.get('state') == 'EXITED' and previous.get('exit_code') == 0
            and not active(previous.get('identity'))
            and (lease is None or lease.get('stage') == 'model'),
            'input worker not fully exited or GPU lease outstanding')
    require(approval.get('model_stage_authorized') is True and approval.get('mode') == 'RUN_MODEL',
            'explicit model-stage RUN not approved')
    require(approval.get('input_stage_record_sha256') == sha(P/'stages/input.json')
            and approval.get('counts_after_input') == read(P/'stages/input.json')['counts_after_exit'],
            'input approval cumulative budget/process record mismatch')
    expected = {**{k: 0 for k in CAPS}, 'workers': 1, 'make_env': 1, 'renders': 12, 'readPixels': 24}
    require(approval['counts_after_input'] == expected and previous['GPU_seconds'] <= 210,
            'input stage invocation/resource counts differ from frozen plan')
    return approval


def reserve(kind, worker, label):
    require(kind in CAPS, 'unknown counter')
    with (P/'counter.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = read(P/'run_state.json')
        require(state and (state.get('active_lease') or {}).get('stage') == worker,
                'no active supervised worker lease')
        require(not (P/'stop_request.json').exists(), 'terminal stop request')
        require(time.time() < state['deadline_epoch'], 'RUN deadline')
        current = state['counts'][kind]
        # A rejected attempted forbidden/over-budget call is durably visible.
        append(P/'call_ledger.jsonl', dict(utc=utc(), worker=worker, kind=kind,
               label=label, ordinal=current+1, event='ATTEMPT', permitted=current < CAPS[kind]))
        require(current < CAPS[kind], kind + ' hard cap; no retry')
        state['counts'][kind] += 1
        write(P/'run_state.json', state)
        return state['counts'][kind]


def worker_gate(stage):
    dispatch = gate(stage, full=False)
    state = read(P/'run_state.json')
    require(state and state['run_id'] == dispatch['run_id'], 'wrong ledger/run')
    lease = state.get('active_lease') or {}
    require(lease.get('stage') == stage and lease.get('token') == os.environ.get('KYC_STAGE_TOKEN')
            and lease.get('supervisor_pid') == os.getppid(), 'worker must be launched by approved supervisor')
    require(lease.get('lease_recorded_before_launch') is True, 'worker lease not recorded before launch')
    # Linux parent-death protection plus a wall-clock backup, installed before
    # any framework import. Default SIGALRM terminates even during a native call.
    import ctypes
    import signal
    parent = lease['supervisor_pid']
    require(ctypes.CDLL(None).prctl(1, signal.SIGTERM, 0, 0, 0) == 0, 'PDEATHSIG setup failed')
    require(os.getppid() == parent, 'supervisor died during worker bootstrap')
    remaining = lease['held_GPU_seconds'] - (time.monotonic()-lease['started_monotonic']) - 5
    require(remaining > 0, 'worker allocation already expired')
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    signal.setitimer(signal.ITIMER_REAL, remaining)
    gate(stage, full=True)
    return dispatch
