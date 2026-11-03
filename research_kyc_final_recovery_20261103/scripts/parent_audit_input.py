"""Parent offline acceptance: saved bytes only, no torch/GL/environment imports."""
from pathlib import Path
import collections, datetime, hashlib, json
import numpy as np
from PIL import Image

P=Path(__file__).resolve().parents[1]
D=P.parent/'research_kyc_diagnostics_20261029'
read=lambda name:json.loads((P/name).read_text())
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def alive(identity):
    try:
        values=(Path('/proc')/str(identity['pid'])/'stat').read_text().rsplit(')',1)[1].split()
        return int(values[19])==identity['start_ticks'] and values[0]!='Z'
    except OSError:return False
result=read('input_result.json');manifest=read('candidate_manifest.json')
stage=read('stages/s1-input.json');state=read('recovery_state.json')
assert result['state']=='COMPLETE_HEALTHY_PENDING_PARENT' and result['failure'] is None
assert stage==state['stages']['s1-input'] and stage['exit_code']==0 and stage['reason']=='EXITED'
assert state['active_lease'] is None and not alive(stage['identity'])
assert not (P/'terminal_stop.json').exists() and not list((P/'results/input').glob('*fatal*'))
actual={str(f.relative_to(P)) for d in [P/'inputs',P/'results/input'] for f in d.rglob('*') if f.is_file()}
assert actual==set(result['input_files'])
assert all(sha(P/f)==h for f,h in result['input_files'].items())
assert all(sha(P/f)==h for f,h in manifest['files'].items())
assert result['source_hashes']==manifest['sources']
assert all(sha(Path(f))==h for f,h in manifest['sources'].items())
readbacks=read('results/input/readback.json');assert len(readbacks)==12
frames=[];contexts=set();ids=set()
for label,row in readbacks.items():
    raw=np.load(P/row['normal']['file'],allow_pickle=False)
    sentinel=np.load(P/row['sentinel']['file'],allow_pickle=False)
    assert raw.shape==(256,256,3) and raw.dtype==np.uint8 and np.array_equal(raw,sentinel)
    assert row['original_lock_held'] and row['independent_buffer']
    assert np.unique(raw).size>2
    for e in row['normal_events']+row['sentinel_events']:
        a=e['active_objects'];assert e['current_context'] and e['current_present']
        assert e['gl']['errors']['codes']==[0] and a['state']=='MEASURED_IN_OWNER_CONTEXT'
        assert a['owner_context']==e['current_context']
        assert len(a['framebuffers'])==3 and all(v['is_framebuffer'] for v in a['framebuffers'].values())
        assert len(a['renderbuffers'])==4 and all(v['is_renderbuffer'] for v in a['renderbuffers'].values())
        contexts.add(e['current_context']);ids.add(json.dumps(a['ids'],sort_keys=True))
    pre=np.load(P/f'results/input/{label}_flip_input.npy',allow_pickle=False)
    post=np.load(P/f'results/input/{label}_flip_output.npy',allow_pickle=False)
    tensor=np.load(P/f'results/input/{label}_tensor_rgb.npy',allow_pickle=False)
    with np.load(P/f'results/input/{label}_saved.npz',allow_pickle=False) as z:saved=z['rgb_float'].copy()
    png=np.asarray(Image.open(P/f'results/input/{label}.png'))
    assert np.array_equal(raw,pre) and np.array_equal(raw[::-1],post)
    assert np.array_equal(tensor,post.transpose(2,0,1).astype(np.float32)/np.float32(255))
    assert np.array_equal(tensor,saved) and np.array_equal(png,np.rint(saved.transpose(1,2,0)*255).astype(np.uint8))
    frames.append(dict(label=label,raw_equals_independent_sentinel=True,five_boundaries_equal=True,
                       pixel_sha256=hashlib.sha256(png.tobytes()).hexdigest()))
assert len(contexts)==len(ids)==1
samples=[]
for row in result['samples']:
    j=row['sample']
    with np.load(P/row['input_npz'],allow_pickle=False) as z,np.load(D/f'execution/inputs/sample_{j:02d}.npz',allow_pickle=False) as old:
        assert all(np.isfinite(z[k]).all() for k in z.files)
        assert np.array_equal(z['canonical_raw'][::-1],z['rgb_uint8'])
        assert np.array_equal(z['rgb_uint8'],np.asarray(Image.open(P/f'results/input/s{j:02d}_dataset.png')))
        diffs={}
        for key,shape in [('image',(1,1,9,256,256)),('qpos',(1,7)),('cam_extrinsics',(1,2,4,4))]:
            base=z['official_'+key];assert base.shape==shape and base.dtype==np.float32
            for prefix in ['custom','dataset']:
                value=z[prefix+'_'+key];assert value.shape==shape and value.dtype==np.float32
                assert np.allclose(base,value,atol=1e-7,rtol=1e-6)
                diffs[prefix+'_'+key]=float(np.max(np.abs(base.astype(float)-value.astype(float))))
        rgb=z['rgb_uint8'].transpose(2,0,1).astype(np.float32)/np.float32(255)
        assert np.array_equal(z['official_image'][0,0,:3],rgb)
        for newkey,oldkey in [('source_state_f32','source_state_f32'),('T','T_given'),('expert_raw_chunk','expert_raw_chunk'),('actions_full','normalized_actions_full'),('is_pad_full','mask_full')]:
            assert np.array_equal(z[newkey],old[oldkey])
        assert np.array_equal(z['valid_mask'],~old['mask_chunk'])
        samples.append(dict(sample=j,all_finite=True,source_arrays_exact=True,entry_maxabs=diffs,valid_steps=int(z['valid_mask'].sum())))
assert [x['sample'] for x in samples]==[0,1,4,5]
assert all(x['pixel_sha256']=='688297023a217d9874c347fdd0a6821def4d0a57d6abc8899014c63860976c37' for x in frames if x['label'].startswith('s00_'))
ledger=[json.loads(x) for x in (P/'call_ledger.jsonl').read_text().splitlines()]
counts=dict(collections.Counter(x['kind'] for x in ledger if x['phase']=='s1-input'))
assert counts==dict(workers=1,make_env=1,renders=12,readPixels=24)
events=[json.loads(x) for x in (P/'results/input/events.jsonl').read_text().splitlines()]
types=collections.Counter(x['event'] for x in events)
assert types['mjr_render_before']==types['mjr_render_after']==12
assert types['mjr_readPixels_before']==types['mjr_readPixels_after']==24
report=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),reviewer='Codex parent',
    kind='independent offline byte/array recomputation; no GPU execution',input_files=90,
    file_set_and_hashes_exact=True,candidate_and_sources_unchanged=True,frames=frames,samples=samples,
    counts=counts,GPU_seconds=stage['GPU_seconds'],cumulative_GPU_seconds=state['GPU_seconds'],
    original_worker_inactive=True,active_lease=None,all_contexts_destroyed_reported=result['all_contexts_destroyed'],
    natural_target_window=result['natural_target_window'],scientific_ACT_observations=0,
    contact_sheet='artifacts/parent_input_contact_sheet.png',actual_images_viewed='separate manual visual decision in notes/07',
    input_result_sha256=sha(P/'input_result.json'),stage_sha256=sha(P/'stages/s1-input.json'))
(P/'artifacts/parent_input_acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['frames','samples']},ensure_ascii=False,indent=2))
print('max_entry_difference',max(v for s in samples for v in s['entry_maxabs'].values()))
