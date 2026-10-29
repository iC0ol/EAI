"""Local-only diagnostics bookkeeping; no model/environment imports."""
import contextlib
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

E = Path(__file__).resolve().parents[1]
D = E.parent
W = D.parent
R = W / 'research_expansion_20261029/reproduction'
K = R / 'vendor/kyc/policy_robosuite'
PROTOCOL_SHA = 'ae04cd358b7e7faa24110dbb447973e518aa739830e541e6bb5dab5c0a7c97ea'

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def read(p, default=None):
    try:
        return json.loads(Path(p).read_text())
    except FileNotFoundError:
        return default

def write(p, value, exclusive=False):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False, default=json_value) + '\n'
    if exclusive:
        with p.open('x') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    else:
        tmp = p.with_name(p.name + f'.{os.getpid()}.tmp')
        with tmp.open('w') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(p)

def append(p, value):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('a') as f:
        f.write(json.dumps(value, ensure_ascii=False, allow_nan=False, default=json_value) + '\n')
        f.flush()
        os.fsync(f.fileno())

def json_value(value):
    if hasattr(value, 'tolist'):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return value.decode('utf-8')
    raise TypeError(f'Unsupported JSON type: {type(value).__name__}')

def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()

def proc(pid):
    try:
        raw = Path(f'/proc/{pid}/stat').read_text()
        v = raw[raw.rfind(')') + 2:].split()
        return {'pid': pid, 'ppid': int(v[1]), 'start_ticks': int(v[19]),
                'rss_bytes': int(v[21]) * os.sysconf('SC_PAGE_SIZE'), 'state': v[0]}
    except (OSError, ValueError):
        return None

def own_env(cpu=False):
    env = os.environ.copy()
    for key in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS']:
        env[key] = '3'
    values = {'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUNBUFFERED': '1',
              'MUJOCO_GL': 'egl', 'PYOPENGL_PLATFORM': 'egl', 'WANDB_MODE': 'disabled',
              'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
              'TORCH_HOME': str(R / 'cache/torch'),
              'XDG_CACHE_HOME': str(E / 'cache'), 'HF_HOME': str(E / 'cache/huggingface'),
              'MPLCONFIGDIR': str(E / 'cache/matplotlib'),
              'NUMBA_CACHE_DIR': str(E / 'cache/numba'), 'TMPDIR': str(E / 'tmp')}
    if cpu:
        values['CUDA_VISIBLE_DEVICES'] = ''
    env.update(values)
    return env

def check_gate():
    assert sha(D / '01_有限排障执行任务书.md') == PROTOCOL_SHA
    gate = read(D / 'orchestration/review_gate.json')
    dispatch = read(D / 'orchestration/dispatch.json')
    assert gate['status'] == 'APPROVED' and gate['sha256'] == PROTOCOL_SHA
    assert gate['codex_approval'] == gate['deepseek_approval'] == 'APPROVE'
    assert dispatch['status'] == 'DISPATCHED' and dispatch['protocol_sha256'] == PROTOCOL_SHA
    assert dispatch['new_executor_thread_id'] == '01a185d0-2da8-70a2-b997-d273c7285042'
    return dispatch

def before_call(category, label, rollout=None):
    """Reserve before invocation, including failed calls. Cross-process durable lock."""
    assert category in ('fixed', 'closed')
    with (E / 'counter.lock').open('a+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        c = read(E / 'counts.json')
        assert not (E / 'stop_request.json').exists(), 'supervisor stop requested'
        assert time.time() < read(E / 'budget.json')['final_deadline_epoch']
        key = 'fixed_forward_attempts' if category == 'fixed' else 'closed_query_attempts'
        cap = 32 if category == 'fixed' else 80
        assert c[key] < cap, key + ' exhausted'
        if category == 'closed':
            assert rollout is not None and c['rollouts'][rollout]['query_attempts'] < 5
            c['rollouts'][rollout]['query_attempts'] += 1
        c[key] += 1
        c['total_policy_attempts'] += 1
        assert c['total_policy_attempts'] <= 112
        c['utc'] = utc()
        write(E / 'counts.json', c)
        append(E / 'call_ledger.jsonl', {'utc': utc(), 'event': 'RESERVED_BEFORE_CALL',
               'category': category, 'label': label, 'rollout': rollout,
               'ordinal': c['total_policy_attempts'], 'category_ordinal': c[key]})

def closed_start(key):
    with (E / 'counter.lock').open('a+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        c = read(E / 'counts.json')
        assert key not in c['rollouts'], 'do not repeat rollout'
        assert len(c['rollouts']) < 16
        c['rollouts'][key] = {'steps_reserved': 0, 'query_attempts': 0, 'state': 'STARTED'}
        c['rollout_attempts'] += 1
        write(E / 'counts.json', c)

def before_step(key):
    with (E / 'counter.lock').open('a+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        c = read(E / 'counts.json')
        assert not (E / 'stop_request.json').exists()
        assert c['rollouts'][key]['steps_reserved'] < 150 and c['closed_steps_reserved'] < 2400
        c['rollouts'][key]['steps_reserved'] += 1
        c['closed_steps_reserved'] += 1
        write(E / 'counts.json', c)
