"""CPU-only independent acceptance from saved trajectories; no simulator imports."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
P=Path(__file__).resolve().parents[1]
arg=argparse.ArgumentParser();arg.add_argument('phase',choices=['expert-a','policy-b']);a=arg.parse_args()
def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
plan=read(P/'root_plan.json')['roots']; root_files=read(P/'roots/manifest.json')['files']
assert all(sha(P/n)==v for n,v in root_files.items())
rows=[]
for file in sorted((P/'results'/a.phase).glob('*_steps.jsonl')):
 tr=[json.loads(l) for l in file.read_text().splitlines()];label=file.name.removesuffix('_steps.jsonl');root=int(label.split('root')[1].split('_')[0]); rp=plan[root]
 prev=np.asarray(read(P/f'roots/root_{root}/control.json')['wrapper_abs_pose']);delta=[];ee=[];dist=[];targets=[];heights=[]
 for i,x in enumerate(tr):
  d=np.asarray(x['delta']);expected=np.r_[prev+d[:6],d[-1]];actual=np.asarray(x['absolute_target']); assert np.array_equal(expected,actual),(label,i,'accumulation')
  prev=actual[:6].copy();e=np.asarray(x['eef_pos']);c=np.asarray(x['cube_position']);v=float(np.linalg.norm(e-c))
  assert abs(v-x['distance_m'])<1e-12 and x['reach']==(v<.05)
  assert x['success']==x['reward_equals_one']==(x['reward']==1) and not x['done']
  assert x['success']==(c[2]>.84),('official Lift height threshold',label,i,c[2])
  assert x['gripper_command']==d[-1] and len(x['gripper_state']['qpos'])==2
  assert abs(x['target_translation_tracking_error_m']-np.linalg.norm(e-actual[:3]))<1e-12
  for arm in x['gripper_state']['by_arm'].values():assert arm['actual_named_sim_joints_verified']
  delta.append(d);ee.append(e);dist.append(v);targets.append(actual);heights.append(c[2])
 delta=np.asarray(delta);ee=np.asarray(ee);targets=np.asarray(targets)
 rec=dict(id=label,root=root,steps=len(tr),source_file=str(file.relative_to(P)),source_sha256=sha(file),success=any(x['success'] for x in tr),reach=any(x['reach'] for x in tr),grasp=any(x['grasp'] for x in tr),minimum_EEF_cube_distance_m=min(dist),maximum_cube_height_m=max(heights),final_EEF=ee[-1].tolist(),final_cube=tr[-1]['cube_position'],initial_step_EEF=ee[0].tolist(),first_absolute_target=targets[0].tolist(),last_absolute_target=targets[-1].tolist(),accumulation_exact=True,success_height_and_reward_agree=True,gripper_command_range=[float(delta[:,-1].min()),float(delta[:,-1].max())],gripper_qpos_min=np.asarray([x['gripper_state']['qpos'] for x in tr]).min(0).tolist(),gripper_qpos_max=np.asarray([x['gripper_state']['qpos'] for x in tr]).max(0).tolist(),tracking_error_median=float(np.median([x['target_translation_tracking_error_m'] for x in tr])),tracking_error_max=float(max(x['target_translation_tracking_error_m'] for x in tr)))
 if a.phase=='expert-a':
  with np.load(P/rp['expert_file'],allow_pickle=False) as z:
   assert np.array_equal(delta,z['actions'][:len(tr)]);errors=np.linalg.norm(ee-z['reference_next_eef'][:len(tr)],axis=1)
   rec.update(expert_actions_exact=True,expert_EEF_deviation_max_m=float(errors.max()),expert_EEF_deviation_mean_m=float(errors.mean()),expected_expert_steps=rp['expert_steps'])
 rows.append(rec)
result=dict(phase=a.phase,reviewer='Codex independent saved-data recomputation; CPU only',trajectories=rows,observed_count=len(rows),total_steps=sum(x['steps'] for x in rows),success_count=sum(x['success'] for x in rows),reach_count=sum(x['reach'] for x in rows),grasp_count=sum(x['grasp'] for x in rows),missing_trajectories_not_filled=True)
(P/f'artifacts/parent_{a.phase}_recomputation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
