"""Parent independent acceptance: saved files only, no model/env/renderer imports."""
from pathlib import Path
import datetime, hashlib, json, os
import numpy as np
from PIL import Image

D=Path(__file__).resolve().parents[1]
E=D/'execution'
R=D.parent/'research_expansion_20261029/reproduction'
def read(p): return json.loads(p.read_text())
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8<<20),b''): h.update(b)
    return h.hexdigest()
def ah(a): return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()

rows=[];verified=0
for saved in read(E/'results/input_comparisons.json')['samples']:
    j=saved['sample']['sample'];p=E/f'inputs/sample_{j:02d}.npz'
    assert sha(p)==saved['npz_sha256']
    with np.load(p,allow_pickle=False) as z:
        for k,m in saved['tensor_metadata'].items():
            assert ah(z[k])==m['sha256'],(j,k)
            verified+=1
        images=[np.rint(z[k][0,0,:3].transpose(1,2,0)*255).astype('uint8') for k in ['dataset_image','eval_image','custom_image']]
        assert np.array_equal(images[0],z['rgb_uint8'])
        assert np.array_equal(images[0],np.asarray(Image.open(E/f'inputs/sample_{j:02d}.png')))
        entry=[]
        for other in [1,2]:
            delta=np.abs(images[0].astype(float)-images[other].astype(float))
            entry.append({'other':['dataset','eval','custom'][other],'different_pixels':int(np.any(delta!=0,axis=2).sum()),'mean_abs_uint8':float(delta.mean()),'max_abs_uint8':float(delta.max()),'flipud_mean_abs_uint8':float(np.abs(images[0].astype(float)-images[other][::-1].astype(float)).mean())})
        rays=all(np.array_equal(z['dataset_image'][:,:,3:],z[k][:,:,3:]) for k in ['eval_image','custom_image'])
        states=all(np.array_equal(z['state_before'],z[k]) for k in ['state_dataset','state_evaluator','state_custom'])
        qpos=all(np.array_equal(z['dataset_qpos'],z[k]) for k in ['eval_qpos','custom_qpos'])
        tokens=all(np.array_equal(z['dataset_cam_extrinsics'],z[k]) for k in ['eval_cam_extrinsics','custom_cam_extrinsics'])
        assert rays and states and qpos and tokens
        rows.append({'sample':j,'demo':saved['sample']['demo_id'],'t':saved['sample']['t'],'comparisons':entry,'rays_states_qpos_tokens_bit_equal':True,'png_matches_saved_tensor':True,'dataset_unique_rgb_count':int(len(np.unique(images[0].reshape(-1,3),axis=0)))})

code_changes={}
for name,h in read(E/'code_manifest_stage1.json')['scripts'].items():
    if sha(E/name)!=h:code_changes[name]={'expected':h,'actual':sha(E/name)}
assert not code_changes
old=read(E/'local_only/old_file_baseline.json');changes=[]
for name,m in old.items():
    p=R/name
    now={'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns,'sha256':sha(p)} if p.exists() else None
    if now!=m:changes.append(name)
assert not changes
processes=[]
for f in ['supervisor_identity.json','active_child.json']:
    d=read(E/f);d=d.get('identity',d);p=Path(f'/proc/{d["pid"]}/stat');same=False
    if p.exists():
        s=p.read_text();v=s[s.rfind(')')+2:].split();same=int(v[19])==d['start_ticks'] and v[0]!='Z'
    assert not same
    processes.append({'pid':d['pid'],'same_process_alive':same})
counts=read(E/'counts.json')
assert all(counts[k]==0 for k in ['fixed_forward_attempts','closed_query_attempts','total_policy_attempts','rollout_attempts','closed_steps_reserved','optimizer_updates'])
stage=read(E/'stages/stage1.json');elapsed=stage['ended_epoch']-stage['started_epoch']
assert abs(elapsed-stage['gpu_allocation_seconds'])<.1
result={'checked_local':datetime.datetime.now().astimezone().isoformat(),'reviewer':'Codex parent','scope':'CPU reanalysis of saved artifacts only; no new observations, model calls, environments or simulation',
        'arrays_verified':verified,'samples':rows,'old_file_count':len(old),'old_file_changes':changes,'frozen_code_changes':code_changes,'original_processes':processes,
        'counts':counts,'gpu_seconds_by_timestamps':elapsed,'gpu_seconds_reported':stage['gpu_allocation_seconds'],'explicit_render_requests_from_code_and_8_rows':24,
        'new_model_calls':0,'new_env_or_renderer_calls':0,'protocol_sha256':sha(D/'01_有限排障执行任务书.md'),
        'limitations':['rendering state/context telemetry missing','current RGB corruption does not prove historic training corruption','non-RGB numeric equality is not independent visible-pixel geometry validation','zero counters corroborated by stopped branch and missing predictions, not hardware instrumentation of Python calls']}
(D/'artifacts/parent_execution_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'arrays_verified':verified,'old_files_unchanged':len(old),'samples':len(rows),'same_processes_alive':False,'gpu_seconds':elapsed,'model_calls':0}))
