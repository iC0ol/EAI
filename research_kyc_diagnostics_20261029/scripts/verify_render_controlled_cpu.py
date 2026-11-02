"""Parent acceptance from saved arrays/events only; no GL/model/simulator calls."""
from pathlib import Path
import hashlib, json, datetime, sys
import numpy as np
from PIL import Image
R=Path(__file__).resolve().parents[1];P=R/'render_controlled'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def active(identity):
    try:
        s=Path('/proc/%s/stat'%identity['pid']).read_text();v=s[s.rfind(')')+2:].split()
        return int(v[19])==identity['start_ticks'] and v[0]!='Z'
    except FileNotFoundError:return False
manifest=read(P/'run_manifest.json');ref=np.asarray(Image.open(manifest['reference']['reference_path']))
assert sha(Path(manifest['reference']['reference_path']))==manifest['reference']['reference_file_sha256']
frames=[];events={};imgs={};states={k:set() for k in ['state_sha256','T_sha256','xml_sha256']};hashed=0
for mode,folder in [('baseline','worker_1_baseline'),('fix','worker_2_fix')]:
    d=P/'results'/folder;es=[json.loads(x) for x in (d/'events.jsonl').read_text().splitlines()];events[mode]=es
    for b in read(d/'readback.json'):
        name=b['entry'];e=read(d/(name+'_metrics.json'));raw=np.load(P/b['raw']['file'],allow_pickle=False)
        fi=np.load(d/(name+'_flip_input.npy'),allow_pickle=False);fo=np.load(d/(name+'_flip_output.npy'),allow_pickle=False)
        t=np.load(d/(name+'_tensor_rgb.npy'),allow_pickle=False);png=np.asarray(Image.open(d/(name+'.png')))
        with np.load(d/(name+'_saved.npz'),allow_pickle=False) as z:saved=z['rgb_float']
        checks=[np.array_equal(raw,fi),np.array_equal(np.flipud(raw),fo),np.array_equal(np.rint(t.transpose(1,2,0)*255).astype('uint8'),fo),np.array_equal(saved,t),np.array_equal(png,fo)]
        assert all(checks);sent=np.load(d/('read_%02d_sentinel.npy'%(b['ordinal']+1)),allow_pickle=False)
        ok=not(mode=='baseline' and name=='after')
        assert np.array_equal(sent,raw)==ok
        if ok:assert np.array_equal(png,ref) and all(x['gl']['errors']['codes']==[0] for x in [b['before'],b['after']])
        else:assert np.all(sent==165) and b['before']['current_context'] is None and not np.array_equal(png,ref)
        imgs[mode,name]=png
        frames.append({'mode':mode,'entry':name,'five_boundaries_exact':all(checks),'reference_equal':bool(np.array_equal(png,ref)),'sentinel_equal_raw':bool(np.array_equal(sent,raw)),'sentinel_165_fraction':float(np.mean(sent==165))})
        for k in states:states[k].add(e[k])
    for ev in es:
        if ev['event']=='mjr_readPixels_after':
            m=ev['array'];a=np.load(P/m['file'],allow_pickle=False);assert sha(P/m['file'])==m['file_sha256'] and hashlib.sha256(a.tobytes()).hexdigest()==m['sha256'];hashed+=1
    fixture=read(d/'fixture.json');result=read(d/'result.json');guard=read(d/'guard_counts.json')
    assert fixture['renderer_count']==fixture['context_count']==2 and not fixture['A_sim_is_env_sim'] and fixture['B_sim_is_env_sim']
    assert result['all_contexts_destroyed'] and result['fixture_strong_refs_remaining']==0 and not result['fatal']
    assert all(all(x[k]==1 for k in ['first_entries','first_completed','con_free_attempts','con_free_returns','context_destroy_successes']) and x['skipped_RUNNING']==0 for x in guard.values())
assert hashed==8 and len(frames)==4 and all(len(v)==1 for v in states.values())
def changes(b,a,namespace):
    lost=[]
    for cat,flag in [('framebuffers','is_framebuffer'),('renderbuffers','is_renderbuffer')]:
        for name,x in b[namespace][cat].items():
            y=a[namespace][cat][name];assert x['id']==y['id'] and x[flag] and not y[flag];lost.append(name)
    return lost
b,a=events['baseline'][31:33];assert b['owner_context']==a['owner_context']=='w1_ctx1' and b['current_context']==a['current_context']=='w1_ctx2'
assert b['owner_objects']['state']==a['owner_objects']['state']=='NOT_MEASURED_WRONG_CONTEXT'
assert b['active_objects']['owner_context']==a['active_objects']['owner_context']=='w1_ctx2';lost=changes(b,a,'active_objects');assert len(lost)==7
b,a=events['fix'][33:35];assert b['owner_context']==b['current_context']==a['current_context']=='w2_ctx1';assert len(changes(b,a,'owner_objects'))==7
f=events['fix'];assert f[46]['event']=='restore_native_return' and f[46]['returned'] and f[46]['current_context']=='w2_ctx2'
assert f[47]['event']=='previous_restored' and f[47]['entry']=='CONTROLLED_RELEASE_A' and f[47]['current_context']=='w2_ctx2'
assert f[52]['event']=='controlled_A_release_exit' and not f[52]['A_live'] and f[52]['B_live'] and f[52]['lock_locked']
original=read(P/'results/worker_2_fix/fixture.json')['B_original_ids']
for i in [47,52]:
    obj=f[i]['active_objects'];assert obj['owner_context']=='w2_ctx2' and obj['ids']==original
    assert all(x['is_framebuffer'] for x in obj['framebuffers'].values()) and all(x['is_renderbuffer'] for x in obj['renderbuffers'].values())
assert not any('eglMakeCurrent' in e['event'] or 'constructor' in e['event'] or 'constructed' in e['event'] for e in f[53:61])
assert np.array_equal(imgs['fix','before'],imgs['fix','after'])
old=read(P/'local_only/old_directory_baseline.json');bad=[]
for name,v in old.items():
    p=R/name
    if not p.exists() or p.stat().st_size!=v['bytes'] or p.stat().st_mtime_ns!=v['mtime_ns'] or sha(p)!=v['sha256']:bad.append(name)
assert not bad
assert all(sha(Path(k))==v for k,v in manifest['sources'].items()) and all(sha(P/'scripts'/k)==v for k,v in manifest['scripts'].items())
assert sha(P/'PROTOCOL.md')==manifest['protocol_sha256']
complete=read(P/'completion.json');ws=complete['worker_processes'];assert ws[0]['ended_epoch']<ws[1]['started_epoch']
assert all(w['exit_code']==0 and not active(w['identity']) for w in ws) and not active(read(P/'supervisor_identity.json'))
seconds=sum(w['ended_epoch']-w['started_epoch'] for w in ws);assert abs(seconds-complete['gpu_allocation_seconds'])<.01 and seconds<180
assert read(P/'counts.json')=={'workers':2,'make_env':2,'renders':4,'readPixels':8,'ACT':0,'env_steps':0,'rollouts':0,'optimizer_updates':0}
sys.path.insert(0,str(P/'scripts'))
from test_owned_release import API,renderer
from owned_release import release_owned
class Unknown(API):
    def capture(self):return {'key':None,'context':999,'display':11,'draw':0,'read':0}
fake=Unknown();obj=renderer(fake)
try:release_owned(obj,fake)
except RuntimeError:pass
else:raise AssertionError('unknown raw context accepted')
assert fake.con_calls==fake.gl_calls==0 and 'bind_owner' not in fake.log and fake.failures and obj._owned_release_state=='ERROR'
out={'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'new_GL_sim_model_calls':0,'verdict':'LOCAL_CONTROLLED_PASS','frames':frames,'raw_array_hashes_verified':hashed,'boundary_comparisons':20,'state_T_XML_equal':True,'baseline_loss_window':[31,32],'baseline_B_resources_lost':lost,'fix_owner_free_window':[33,34],'fix_native_restore_event':46,'fix_previous_restored_event':47,'fix_B_original_objects_preserved_event':52,'fix_after_equals_before':True,'same_fixture_exactly_once_cleanup_verified':True,'baseline_after_diff_fraction':float(np.mean(imgs['baseline','after']!=ref)),'baseline_after_exact_vertical_flip':bool(np.array_equal(imgs['baseline','after'],np.flipud(ref))),'baseline_after_memory_origin':'UNKNOWN; no valid new GL readback','old_files_checked':len(old),'old_changes':bad,'source_frozen_code_sha_match':True,'gpu_seconds_from_timestamps':seconds,'reported_gpu_seconds':complete['gpu_allocation_seconds'],'processes_exited':True,'unknown_nonnull_CPU_regression':'PASS: visible rejection before bind/free','scope':'fixed sample0 and controlled release fixture only','historic_0_of_32_cause':'UNKNOWN'}
(R/'artifacts/parent_render_controlled_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:out[k] for k in ['verdict','raw_array_hashes_verified','old_files_checked','gpu_seconds_from_timestamps','unknown_nonnull_CPU_regression']}))
