"""Independent saved-data acceptance. No GL, simulator, torch, or model imports."""
from pathlib import Path
import datetime, hashlib, json, sys
import numpy as np
from PIL import Image

R=Path(__file__).resolve().parents[1]; P=R/'render_lifecycle'
def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def alive(identity):
    try:
        s=Path('/proc/%s/stat'%identity['pid']).read_text();v=s[s.rfind(')')+2:].split()
        return int(v[19])==identity['start_ticks'] and v[0]!='Z'
    except FileNotFoundError:return False
rows=[]; events={}; images={}; hashes=0; keys={k:set() for k in ['state_sha256','T_sha256','xml_sha256']}
for mode,folder in [('baseline','worker_1_baseline'),('fix','worker_2_fix')]:
    d=P/'results'/folder;es=[json.loads(x) for x in (d/'events.jsonl').read_text().splitlines()];events[mode]=es
    entries=read(d/'entries.json');reads=read(d/'readback.json')
    for e,b in zip(entries,reads):
        name=e['entry'];assert name==b['entry'];raw=np.load(P/b['raw']['file'],allow_pickle=False)
        flipin=np.load(d/(name+'_flip_input.npy'),allow_pickle=False);flipout=np.load(d/(name+'_flip_output.npy'),allow_pickle=False)
        tensor=np.load(d/(name+'_tensor_rgb.npy'),allow_pickle=False);png=np.asarray(Image.open(d/(name+'.png')))
        with np.load(d/(name+'_saved.npz'),allow_pickle=False) as z:saved=z['rgb_float']
        with np.load(d/(name+'_common_preprocess.npz'),allow_pickle=False) as z:common=np.array_equal(z['dataset'],z['evaluator']) and np.array_equal(z['dataset'],z['custom'])
        checks=[np.array_equal(raw,flipin),np.array_equal(flipout,np.flipud(raw)),np.array_equal(np.rint(tensor.transpose(1,2,0)*255).astype('uint8'),flipout),np.array_equal(saved,tensor),np.array_equal(png,flipout),common]
        assert all(checks),(mode,name,checks)
        sentinel=np.load(d/('read_%02d_sentinel.npy'%(b['ordinal']+1)),allow_pickle=False)
        rows.append({'mode':mode,'entry':name,'five_boundaries_and_common_rgb':all(checks),'sentinel_equals_raw':bool(np.array_equal(sentinel,raw)),'sentinel_165_fraction':float(np.mean(sentinel==165)),'current_before':b['before']['current_context']})
        images[mode,name]=png
        for k in keys:keys[k].add(e[k])
    for ev in es:
        if ev['event']!='mjr_readPixels_after':continue
        m=ev['array'];p=P/m['file'];a=np.load(p,allow_pickle=False)
        assert sha(p)==m['file_sha256'] and hashlib.sha256(a.tobytes()).hexdigest()==m['sha256'];hashes+=1
assert len(rows)==8 and hashes==16 and all(len(x)==1 for x in keys.values())
b,a=events['baseline'][29:31];assert b['event']=='baseline_before_con_free' and a['event']=='baseline_after_con_free'
assert b['current_context']==a['current_context']=='w1_ctx2' and b['owner_context']==a['owner_context']=='w1_ctx1'
assert b['owner_objects']['state']==a['owner_objects']['state']=='NOT_MEASURED_WRONG_CONTEXT'
assert b['active_objects']['owner_context']==a['active_objects']['owner_context']=='w1_ctx2'
lost=[]
for category,flag in [('framebuffers','is_framebuffer'),('renderbuffers','is_renderbuffer')]:
    for name,before in b['active_objects'][category].items():
        after=a['active_objects'][category][name]
        assert before['id']==after['id'] and before[flag] and not after[flag]
        lost.append({'category':category,'name':name,'id':before['id']})
assert len(lost)==7
assert events['baseline'][34]['current_context']=='w1_ctx2' and events['baseline'][35]['current_context'] is None
acquisition_end=max(i for i,e in enumerate(events['fix']) if e['event']=='entry_after')
destructors=[i for i,e in enumerate(events['fix']) if e['event']=='owner_bound_before_con_free']
assert destructors and all(i>acquisition_end for i in destructors)
restores=[i for i,e in enumerate(events['fix']) if e['event']=='previous_restored'];assert not restores
for i,j in [(59,60),(75,76)]:
    before,after=events['fix'][i],events['fix'][j]
    assert before['owner_context']==before['current_context']==after['current_context']
    assert before['owner_objects']['state']==after['owner_objects']['state']=='MEASURED_IN_OWNER_CONTEXT'
    for category,flag in [('framebuffers','is_framebuffer'),('renderbuffers','is_renderbuffer')]:
        for name,x in before['owner_objects'][category].items():
            y=after['owner_objects'][category][name];assert x['id']==y['id'] and x[flag] and not y[flag]
fixed_equal=all(np.array_equal(images['fix','early'],images['fix',k]) for k in ['dataset','evaluator','custom']);assert fixed_equal
assert np.array_equal(images['baseline','early'],images['fix','early'])
baseline=read(P/'local_only/old_directory_baseline.json');old_changes=[]
for name,m in baseline.items():
    p=R/name
    if not p.exists() or p.stat().st_size!=m['bytes'] or p.stat().st_mtime_ns!=m['mtime_ns'] or sha(p)!=m['sha256']:old_changes.append(name)
assert not old_changes
manifest=read(P/'run_manifest.json')
assert all(sha(Path(k))==v for k,v in manifest['sources'].items())
assert all(sha(P/'scripts'/k)==v for k,v in manifest['scripts'].items())
assert sha(P/'PROTOCOL.md')==manifest['protocol_sha256']
complete=read(P/'completion.json');workers=complete['worker_processes'];assert workers[0]['ended_epoch']<workers[1]['started_epoch']
assert all(not alive(w['identity']) and w['exit_code']==0 for w in workers)
assert not alive(read(P/'supervisor_identity.json'))
seconds=sum(w['ended_epoch']-w['started_epoch'] for w in workers)
assert abs(seconds-complete['gpu_allocation_seconds'])<.01 and seconds<300
counts=read(P/'counts.json');assert counts=={'workers':2,'make_env':2,'renders':8,'readPixels':16,'ACT':0,'env_steps':0,'rollouts':0,'optimizer_updates':0}
# A targeted CPU-only negative example of a registry miss. Existing fake's
# 'unknown' string did not represent the real adapter's nonnull/key=None case.
sys.path.insert(0,str(P/'scripts'))
from test_owned_release import API,renderer
from owned_release import release_owned
class UnregisteredPrevious(API):
    def capture(self):
        return {'key':None if self.current=='unregistered' else self.current,'context':999 if self.current=='unregistered' else (1 if self.current else 0),'display':11,'draw':12,'read':13}
fake=UnregisteredPrevious('unregistered');obj=renderer(fake);release_owned(obj,fake)
unknown_gap={'initial_nonnull_context_with_unknown_key':True,'final_current':fake.current,'release_state':obj._owned_release_state,'failure_count':len(fake.failures),'con_free_calls':fake.con_calls,'actual_GL_calls':0}
assert obj._owned_release_state=='DONE' and fake.current is None and not fake.failures
out={'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'model_sim_GL_calls':0,'frames':rows,'raw_metadata_hashes':hashes,'same_state_T_XML':True,'baseline_resource_loss_window':[29,30],'current_resource_losses':lost,'baseline_release_current_window':[34,35],'fix_last_image_event':acquisition_end,'fix_owner_release_events':destructors,'real_live_previous_restores':0,'healthy_frames_caused_by_repair':'NOT_ESTABLISHED','fixed_images_and_baseline_early_bit_equal':fixed_equal,'old_files_checked':len(baseline),'old_changes':old_changes,'frozen_source_and_code_sha_match':True,'gpu_seconds_from_timestamps':seconds,'reported_gpu_seconds':complete['gpu_allocation_seconds'],'counts':counts,'processes_exited':True,'unregistered_previous_cpu_regression':unknown_gap,'decision':'PARTIAL; baseline mechanism directly supported, equivalent repair intervention missing'}
(R/'artifacts/parent_render_lifecycle_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'frames':len(rows),'old_files':len(baseline),'seconds':seconds,'resource_losses':len(lost),'real_live_previous_restores':0,'new_cpu_edge_case_reproduced':True}))
