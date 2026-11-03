"""Bookkeeping only: importing this module creates no experimental state."""
from pathlib import Path
import datetime
import fcntl
import hashlib
import json
import os
import time

P = Path(__file__).resolve().parents[1]
W = P.parent
D = W / 'research_kyc_diagnostics_20261029'
R = W / 'research_expansion_20261029/reproduction'
K = R / 'vendor/kyc/policy_robosuite'
EXECUTOR = {'thread_id': '01a185d0-2da8-70a2-b997-d273c7285042',
            'model': 'gpt-6.1-sol', 'reasoning_effort': 'max'}
CAPS = dict(workers=2, make_env=2, renders=12, readPixels=24, ACT=16,
            env_steps=0, rollouts=0, backward=0, optimizer=0)
REFERENCE_SHA = '688297023a217d9874c347fdd0a6821def4d0a57d6abc8899014c63860976c37'


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return default


def write(path, value, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if exclusive:
        with path.open('x') as f:
            f.write(text); f.flush(); os.fsync(f.fileno())
    else:
        tmp = path.with_name(path.name + '.tmp')
        with tmp.open('w') as f:
            f.write(text); f.flush(); os.fsync(f.fileno())
        tmp.replace(path)


def append(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as f:
        f.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')
        f.flush(); os.fsync(f.fileno())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def proc(pid):
    try:
        raw = Path('/proc') / str(pid) / 'stat'
        values = raw.read_text().rsplit(')', 1)[1].split()
        return dict(pid=pid, ppid=int(values[1]), start_ticks=int(values[19]),
                    state=values[0], rss=int(values[21]) * os.sysconf('SC_PAGE_SIZE'))
    except (OSError, ValueError):
        return None


def active(identity):
    now = proc(identity['pid']) if identity else None
    return bool(now and now['start_ticks'] == identity['start_ticks'] and now['state'] != 'Z')


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def envvars():
    result = os.environ.copy()
    for key in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS']:
        result[key] = '3'
    result.update(PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1',
                  MUJOCO_GL='egl', PYOPENGL_PLATFORM='egl',
                  XDG_CACHE_HOME=str(P/'cache'), TORCH_HOME=str(P/'cache/torch'),
                  MPLCONFIGDIR=str(P/'cache/mpl'), NUMBA_CACHE_DIR=str(P/'cache/numba'),
                  HF_HOME=str(P/'cache/hf'), HF_HUB_OFFLINE='1',
                  TRANSFORMERS_OFFLINE='1', WANDB_MODE='disabled',
                  TMPDIR=str(P/'tmp'), CUBLAS_WORKSPACE_CONFIG=':4096:8')
    for key, name in [('TORCHINDUCTOR_CACHE_DIR', 'inductor'), ('TORCH_EXTENSIONS_DIR', 'extensions'),
                      ('PYTORCH_KERNEL_CACHE_PATH', 'kernels'), ('TRITON_CACHE_DIR', 'triton')]:
        result[key] = str(P/'cache'/name)
    return result
