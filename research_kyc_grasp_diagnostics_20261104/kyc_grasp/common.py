"""New-scope bookkeeping; import has no experimental side effects."""
from pathlib import Path
import datetime,fcntl,hashlib,json,os,time
P=Path(__file__).resolve().parents[1];W=P.parent
R=W/'research_expansion_20261029/reproduction';K=R/'vendor/kyc/policy_robosuite'
SCOPE_ID='kyc-grasp-rootcause-c96545a9-5b4f-43b9-91f0-8f42b9343836'
RECOVERY_ID=SCOPE_ID
EXECUTOR={'thread_id':'01a185d0-2da8-70a2-b997-d273c7285042','model':'gpt-6.1-sol','reasoning_effort':'max'}
PHASES=('gpu-preflight','expert-a','policy-b','c-local','c-official')
CAPS=dict(workers=5,make_env=8,resets=36,renders=102,readPixels=204,ACT=40,env_steps=1800,rollouts=12,getitems=44,backward=0,optimizer=0)
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def require(v,reason):
    if not v:raise RuntimeError(reason)
def read(path,default=None):
    try:return json.loads(Path(path).read_text())
    except FileNotFoundError:return default
def write(path,value,exclusive=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if exclusive:
        with path.open('x') as f:f.write(payload);f.flush();os.fsync(f.fileno())
    else:
        tmp=path.with_name(path.name+'.tmp')
        with tmp.open('w') as f:f.write(payload);f.flush();os.fsync(f.fileno())
        tmp.replace(path)
def append(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a') as f:f.write(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8<<20),b''):h.update(block)
    return h.hexdigest()
def proc(pid):
    try:
        a=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()
        return dict(pid=pid,ppid=int(a[1]),start_ticks=int(a[19]),state=a[0],rss=int(a[21])*os.sysconf('SC_PAGE_SIZE'))
    except (OSError,ValueError):return None
def active(i):
    now=proc(i['pid']) if i else None
    return bool(now and now['start_ticks']==i['start_ticks'] and now['state']!='Z')
def envvars():
    x=os.environ.copy()
    for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS']:x[k]='3'
    x.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',WANDB_MODE='disabled',CUBLAS_WORKSPACE_CONFIG=':4096:8',__GL_SHADER_DISK_CACHE='0')
    for k,n in [('XDG_CACHE_HOME','cache'),('TORCH_HOME','cache/torch'),('MPLCONFIGDIR','cache/mpl'),('NUMBA_CACHE_DIR','cache/numba'),('HF_HOME','cache/hf'),('TMPDIR','tmp'),('TORCHINDUCTOR_CACHE_DIR','cache/inductor'),('TORCH_EXTENSIONS_DIR','cache/extensions'),('PYTORCH_KERNEL_CACHE_PATH','cache/kernels'),('TRITON_CACHE_DIR','cache/triton'),('CUDA_CACHE_PATH','cache/nvidia'),('__GL_SHADER_DISK_CACHE_PATH','cache/nvidia')]:x[k]=str(P/n)
    return x

def save_npz(path,**arrays):
    """Compress in bounded CPU memory, check actual output bytes before any write."""
    import io,numpy as np
    stream=io.BytesIO();np.savez_compressed(stream,**arrays);payload=stream.getvalue()
    used=sum(f.stat().st_size for f in P.rglob('*') if f.is_file())
    require(used+len(payload)<=146*2**20,'OUTPUT_STORAGE_BUDGET; keep4MiB cleanup/log reserve')
    path=Path(path);path.parent.mkdir(exist_ok=True,parents=True)
    with path.open('xb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
