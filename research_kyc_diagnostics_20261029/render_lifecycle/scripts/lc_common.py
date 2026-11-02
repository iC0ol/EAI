from pathlib import Path
import datetime,hashlib,json,os,time,fcntl
P=Path(__file__).resolve().parents[1];D=P.parent;W=D.parent
R=W/'research_expansion_20261029/reproduction';K=R/'vendor/kyc/policy_robosuite'
SHA='53b7058bd290886d5787cd73ed9cb926a38ec49792a99305a84db11a1c3d8d0f'
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(p,default=None):
    try:return json.loads(Path(p).read_text())
    except FileNotFoundError:return default
def write(p,obj,exclusive=False):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);s=json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if exclusive:
        with p.open('x') as f:f.write(s);f.flush();os.fsync(f.fileno())
    else:
        q=p.with_name(p.name+f'.{os.getpid()}.tmp')
        with q.open('w') as f:f.write(s);f.flush();os.fsync(f.fileno())
        q.replace(p)
def append(p,obj):
    with Path(p).open('a') as f:f.write(json.dumps(obj,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8<<20),b''):h.update(b)
    return h.hexdigest()
def proc(pid):
    try:
        s=Path(f'/proc/{pid}/stat').read_text();v=s[s.rfind(')')+2:].split()
        return {'pid':pid,'ppid':int(v[1]),'start_ticks':int(v[19]),'rss':int(v[21])*os.sysconf('SC_PAGE_SIZE'),'state':v[0]}
    except (OSError,ValueError):return None
def gate():
    g=read(P/'review_gate.json');d=read(P/'dispatch.json')
    assert g['state']=='APPROVED' and g['protocol_sha256']==sha(P/'PROTOCOL.md')==SHA
    assert g['codex_review']==g['deepseek_review']=='APPROVE' and d['status']=='DISPATCHED'
    assert d['protocol_sha256']==SHA
    return d
def reserve(kind,worker,label):
    caps={'workers':2,'make_env':2,'renders':8,'readPixels':16,'ACT':0,'env_steps':0,'rollouts':0,'optimizer_updates':0}
    with (P/'counter.lock').open('a+') as f:
        fcntl.flock(f,fcntl.LOCK_EX);c=read(P/'counts.json')
        assert not (P/'stop_request.json').exists() and time.time()<read(P/'budget.json')['deadline_epoch']
        assert c[kind]<caps[kind],kind+' hard cap'
        c[kind]+=1;write(P/'counts.json',c)
        append(P/'call_ledger.jsonl',{'utc':utc(),'monotonic':time.monotonic(),'worker':worker,'kind':kind,'ordinal':c[kind],'label':label,'event':'RESERVED_BEFORE_CALL'})
        return c[kind]
def envvars():
    e=os.environ.copy()
    for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS']:e[k]='3'
    e.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',
        XDG_CACHE_HOME=str(P/'cache'),MPLCONFIGDIR=str(P/'cache/mpl'),NUMBA_CACHE_DIR=str(P/'cache/numba'),
        HF_HOME=str(P/'cache/hf'),HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',WANDB_MODE='disabled',TORCH_HOME=str(R/'cache/torch'),TMPDIR=str(P/'tmp'))
    return e
