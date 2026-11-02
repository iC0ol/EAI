"""Independent CPU-only checks of saved render-repair evidence; no renderer import."""
from pathlib import Path
import json, hashlib, datetime
import numpy as np
from PIL import Image
D=Path(__file__).resolve().parents[1];P=D/'render_repair';O=P/'results/worker_2'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
events=[json.loads(x) for x in (O/'events.jsonl').read_text().splitlines()]
rows=read(O/'entries.json');frames=read(O/'readback.json');checks=[];hashes=0
for e in events:
    m=e.get('array')
    if m:
        p=P/m['file'];a=np.load(p,allow_pickle=False)
        assert sha(p)==m['file_sha256']
        assert hashlib.sha256(a.tobytes()).hexdigest()==m['sha256'];hashes+=1
for r in rows:
    name=r['entry'];n=r['read_ordinal']
    raw=np.load(O/f'read_{n:02d}_normal_raw.npy',allow_pickle=False)
    sentinel=np.load(O/f'read_{n+1:02d}_sentinel.npy',allow_pickle=False)
    pre=np.load(O/f'{name}_read_pixels_return_preflip_{n+1:02d}.npy',allow_pickle=False)
    fi=np.load(O/f'{name}_flip_input.npy',allow_pickle=False)
    fo=np.load(O/f'{name}_flip_output.npy',allow_pickle=False)
    tensor=np.load(O/f'{name}_float_tensor_rgb.npy',allow_pickle=False)
    with np.load(O/f'{name}_saved.npz',allow_pickle=False) as z:saved=z['rgb_float'].copy()
    png=np.asarray(Image.open(O/f'{name}.png'))
    tests={'raw_preflip':np.array_equal(raw,pre),'raw_flip_input':np.array_equal(raw,fi),
           'flip':np.array_equal(raw[::-1],fo),'float_roundtrip':np.array_equal(np.rint(tensor.transpose(1,2,0)*255).astype(np.uint8),raw[::-1]),
           'saved_exact':np.array_equal(tensor,saved),'png':np.array_equal(png,raw[::-1])}
    with np.load(O/f'{name}_common_raw_preprocess.npz',allow_pickle=False) as z:
        tests['common_rgb']=np.array_equal(z['dataset'],z['evaluator']) and np.array_equal(z['dataset'],z['custom'])
    assert all(tests.values());assert sha(O/f'{name}_saved.npz')==r['saved_npz_sha256']
    checks.append({'entry':name,'checks':tests,'sentinel_retained_fraction':float(np.mean(sentinel==165))})
base=read(P/'local_only/old_execution_baseline.json');changed=[]
for name,m in base.items():
    f=D/'execution'/name;s=f.stat()
    if s.st_size!=m['bytes'] or s.st_mtime_ns!=m['mtime_ns'] or sha(f)!=m['sha256']:changed.append(name)
assert not changed
manifest=read(P/'run_manifest.json');assert all(sha(Path(p))==s for p,s in manifest['sources'].items())
recovery=read(P/'engineering_recovery_code.json');assert all(sha(P/'scripts'/p)==s for p,s in recovery['scripts'].items())
c=read(P/'completion.json');workers=c['worker_processes'];seconds=sum(w['ended_epoch']-w['started_epoch'] for w in workers)
assert workers[0]['ended_epoch']<workers[1]['started_epoch'];assert abs(seconds-c['gpu_allocation_seconds'])<.02
assert events[28]['event']=='eglReleaseThread_enter' and events[29]['event']=='eglReleaseThread_exit'
assert events[28]['telemetry']['current']=='w2_ctx2' and events[29]['telemetry']['current'] is None
out={'checked_local':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
 'new_model_or_renderer_calls':0,'entries':checks,'raw_array_file_hashes_checked':hashes,'old_execution_files_checked':len(base),
 'old_execution_changes':changed,'source_and_executed_code_hashes_match':True,'seconds_by_timestamps':seconds,
 'reported_gpu_seconds':c['gpu_allocation_seconds'],'reported_counts':c['counts'],'release_current_transition_verified':True,
 'valid_render_workers':1,'independent_valid_repeat':'NOT_RUN','framebuffer_object_deletion':'NOT_PROVEN: no binding/object telemetry',
 'state_xml_T_unique_counts':{k:len({r[k] for r in rows}) for k in ['source_state_sha256','xml_sha256','T_sha256']}}
(D/'artifacts/parent_render_repair_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'entries_verified':len(checks),'old_files':len(base),'seconds':seconds,'raw_hashes':hashes}))
