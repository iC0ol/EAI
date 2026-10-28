import os, json, time, hashlib, datetime, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read_json(p, default=None):
    try: return json.loads(pathlib.Path(p).read_text())
    except FileNotFoundError: return default
def atomic_json(p, obj):
    p=pathlib.Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    q=p.with_suffix(p.suffix+'.tmp'); q.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str)+'\n'); q.replace(p)
def append_json(p,obj):
    with pathlib.Path(p).open('a') as f: f.write(json.dumps(obj,ensure_ascii=False,default=str)+'\n'); f.flush()
def sha(p):
    h=hashlib.sha256()
    with pathlib.Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8<<20),b''): h.update(b)
    return h.hexdigest()
def own_env():
    env=os.environ.copy()
    for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS']:env[k]='3'
    for k,v in {'PYTHONDONTWRITEBYTECODE':'1','PYTHONUNBUFFERED':'1','MUJOCO_GL':'egl','PYOPENGL_PLATFORM':'egl','WANDB_MODE':'disabled','HF_HOME':str(ROOT/'cache/huggingface'),'TORCH_HOME':str(ROOT/'cache/torch'),'XDG_CACHE_HOME':str(ROOT/'cache'),'PIP_CACHE_DIR':str(ROOT/'cache/pip'),'MPLCONFIGDIR':str(ROOT/'cache/matplotlib'),'NUMBA_CACHE_DIR':str(ROOT/'cache/numba'),'TMPDIR':str(ROOT/'tmp')}.items():env[k]=v
    return env
