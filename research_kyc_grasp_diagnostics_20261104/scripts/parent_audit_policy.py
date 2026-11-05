"""Independent CPU reanalysis of completed B originals. No model/simulator."""
from pathlib import Path
from collections import Counter
import json,hashlib,numpy as np
from PIL import Image,ImageDraw
P=Path(__file__).resolve().parents[1];R=P.parent/'research_expansion_20261029/reproduction'
def read(n):return json.loads((P/n).read_text())
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
s=read('stages/policy-b.json');v=read('policy_result.json');stats=json.loads((R/'manifests/dataset_stats.json').read_text());ref=read('artifacts/parent_policy-b_recomputation.json');pairs=[];blocks=[]
assert s['exit_code']==0 and s['reason']=='EXITED' and not Path('/proc/'+str(s['identity']['pid'])).exists()
for r in v['rollouts']:
 tr=[json.loads(l) for l in (P/r['trajectory']).read_text().splitlines()];d=np.asarray([x['delta'] for x in tr]);chunks=[]
 assert all(r['restore'][k] for k in ['state_exact','physical_model_exact','controller_exact'])
 for q in r['queries']:
  m=q['model'];file=P/m['output_npz'];assert sha(file)==m['output_sha256'] and m['official_policy_return_bit_equal_internal'] and all(m['input_hashes'][k]==m['internal_input_hashes'][k] for k in ['qpos','cam_extrinsics'])
  assert m['policy_input_keys']==['cam_extrinsics','image','qpos']
  with np.load(file,allow_pickle=False) as z:
   raw=z['raw_chunk'];norm=z['normalized_chunk'];assert raw.dtype==np.float32 and raw.shape==(30,7)
   recompute=norm.astype(np.float32)*np.asarray(stats['action_std'],np.float32)+np.asarray(stats['action_mean'],np.float32)
   assert np.array_equal(recompute,raw) and np.isfinite(raw).all();chunks.append(raw.copy())
   blocks.append(dict(id=m['id'],source_file=m['output_npz'],source_sha256=m['output_sha256'],shape=list(raw.shape),dtype=str(raw.dtype),raw_chunk=raw.tolist()))
 assert np.array_equal(d,np.concatenate(chunks).astype(np.float64)) and len(tr)==150
 x0=np.asarray(r['initial_EEF']);cube0=np.asarray(r['initial_cube']);dx=np.asarray(r['final_EEF'])-x0;desired=cube0-x0
 cos=float(np.dot(dx,desired)/(np.linalg.norm(dx)*np.linalg.norm(desired)))
 rec=next(x for x in ref['trajectories'] if x['id']==r['id']);assert rec['success']==r['success'] and rec['minimum_EEF_cube_distance_m']==r['minimum_EEF_cube_distance_m']
 rec.update(condition=r['condition'],initial_EEF=r['initial_EEF'],initial_cube=r['initial_cube'],EEF_displacement_m=dx.tolist(),toward_initial_cube_cosine=cos,initial_distance_m=float(np.linalg.norm(desired)),sum_predicted_delta_xyz=np.sum(np.concatenate(chunks)[:,:3].astype(np.float64),axis=0).tolist(),positive_gripper_command_fraction=float(np.mean(d[:,-1]>0)),query_mean_xyz=[np.mean(c[:,:3],axis=0).tolist() for c in chunks],all_five_chunk_values_equal_executed_prefixes=True,FP32_denormalization_exact=True,qpos_T_outer_internal_hashes_equal=True,image_hash_change_expected_official_RGB_normalization=True)
 pairs.append(rec)
rb=read('results/policy-b/readbacks.json');assert len(rb)==48
for n,z in rb.items():
 assert sha(P/z['file'])==z['sha256']
 with np.load(P/z['file'],allow_pickle=False) as a:
  assert np.array_equal(a['normal'],a['sentinel']) and hashlib.sha256(a['normal'].tobytes()).hexdigest()==z['raw_sha256']
  png=P/f'results/policy-b/{n}.png'
  if png.exists():assert np.array_equal(np.asarray(Image.open(png)),a['normal'][::-1])
ev=[json.loads(l) for l in (P/'results/policy-b/events.jsonl').read_text().splitlines()];counts=dict(Counter(e['event'] for e in ev))
for e in ev:
 if e['event'].startswith('mjr_readPixels'):
  assert e['current_present'] and e['gl']['errors']['codes']==[0] and e['gl']['read_bound_object']['status']==e['gl']['draw_bound_object']['status']==36053
  assert all(x['is_framebuffer'] for x in e['active_objects']['framebuffers'].values()) and all(x['is_renderbuffer'] for x in e['active_objects']['renderbuffers'].values())
assert counts['mjr_render_before']==48 and counts['mjr_readPixels_before']==96
(P/'review_packets').mkdir(exist_ok=True)
with (P/'review_packets/policy_raw_blocks.jsonl').open('w') as f:
 for b in blocks:f.write(json.dumps(b,separators=(',',':'))+'\n')
out=dict(stage=s,trajectories=pairs,all48_raw_readbacks_exact=True,read_event_GL_health_valid=True,event_counts=counts,all40_FP32_prediction_blocks_recomputed_and_equal_to1200_executed_deltas=True,all40_qpos_T_outer_internal_hashes_equal=True,image_hashes_change_at_official_normalization=True,full_9channel_input_arrays_not_saved_by_frozen_storage_plan=True,worker_inactive=True,source_files={n:sha(P/n) for n in ['policy_result.json','stages/policy-b.json','roots/manifest.json','policy_strict_load.json','model_events.jsonl']})
(P/'artifacts/parent_policy_b_acceptance.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
# A readable visual index of the actual first and final B frames.
sheet=Image.new('RGB',(1024,1104),'white');draw=ImageDraw.Draw(sheet)
for ri,r in enumerate(sorted(v['rollouts'],key=lambda x:(x['root'],x['condition']!='train'))):
 names=[r['queries'][0]['model']['id'],r['id']+'_final']
 for j,n in enumerate(names):
  x=(ri%2)*512+j*256;y=(ri//2)*276;sheet.paste(Image.open(P/f'results/policy-b/{n}.png'),(x,y+20));draw.text((x+3,y+4),n,fill='black')
sheet.save(P/'figures/policy_b_contact_sheet.png')
print(json.dumps({'B_GPU_seconds':s['GPU_seconds'],'cumulative_GPU_seconds':s['cumulative_GPU_seconds'],'success_train':sum(x['success'] for x in pairs if x['condition']=='train'),'success_dev':sum(x['success'] for x in pairs if x['condition']=='dev'),'all_prediction_execution_and_RGB_checks':True,'trajectories':[{k:x[k] for k in ['id','minimum_EEF_cube_distance_m','EEF_displacement_m','sum_predicted_delta_xyz','toward_initial_cube_cosine','positive_gripper_command_fraction','tracking_error_median']} for x in pairs]},ensure_ascii=False))
