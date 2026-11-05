"""CPU-only inspection of actual saved Dataset -> collate tensors and HDF5."""
from pathlib import Path
from collections import Counter,defaultdict
import json,hashlib,argparse
import numpy as np,h5py
from PIL import Image,ImageDraw
P=Path(__file__).resolve().parents[1];R=P.parent/'research_expansion_20261029/reproduction'
p=argparse.ArgumentParser();p.add_argument('phase',choices=['c-local','c-official']);phase=p.parse_args().phase
read=lambda n:json.loads((P/n).read_text()); sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest(); digest=lambda a:hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
v=read(phase+'_result.json');st=read('stages/'+phase+'.json');stats=json.loads((R/'manifests/dataset_stats.json').read_text());mean=np.asarray(stats['action_mean'],np.float32);std=np.asarray(stats['action_std'],np.float32)
assert st['exit_code']==0 and not Path('/proc/'+str(st['identity']['pid'])).exists()
batches={};rows=[];imgs={};raws=0;representatives=0;sheet=Image.new('RGB',(1024,((len(v['items'])+3)//4)*276),'white');draw=ImageDraw.Draw(sheet)
for b in v['batches']:
 assert sha(P/b['file'])==b['sha256']
 with np.load(P/b['file'],allow_pickle=False) as z:batches[b['file']]={k:z[k].copy() for k in z.files}
 for k,x in batches[b['file']].items():assert digest(x)==b['tensor_metadata'][k]['sha256'] and np.isfinite(x).all()
with h5py.File(R/'assets/liftrand_eef_delta.hdf5','r') as h:
 for j,row in enumerate(v['items']):
  sample=row['sample'];item={k:a[row['collate_slice']['index']] for k,a in batches[row['collate_slice']['file']].items()}
  for k,a in item.items():assert digest(a)==row['actual_item_tensors'][k]['sha256']
  d=h[f"data/demo_{sample['demo_id']}"];t=sample['t'];state=d['states'][t].astype(np.float32);actions=d['actions'][t:].astype(np.float32)
  assert digest(state)==row['source_state']['sha256'] and np.array_equal(state,np.asarray(row['source_state_values'],np.float32)) and digest(actions)==row['source_actions']['sha256']
  pad=np.zeros_like(item['actions']);n=min(len(actions),len(pad));pad[:n]=actions[:n]
  assert np.array_equal((pad-mean)/std,item['actions']) and np.array_equal(np.arange(len(pad))>=n,item['is_pad'])
  image=item['image'][0];assert digest(image)==row['post_transform']['sha256'];crop=row['crop'];raw_file=row['frame'].get('file');raw_checked=False
  def crop_map(a):
   if crop is None:return a
   ix=np.floor(np.arange(256)*crop['side']/256).astype(int);return a[:,crop['top']+ix[:,None],crop['left']+ix[None,:]]
  if raw_file:
   with np.load(P/raw_file,allow_pickle=False) as z:
    assert np.array_equal(z['normal'],z['sentinel']);raw=z['normal'];assert digest(raw)==row['frame']['raw_sha256']
    rgb=raw[::-1].transpose(2,0,1).astype(np.float32)/np.float32(255);assert np.array_equal(crop_map(rgb),image[:3]);raw_checked=True;raws+=1
  if row['representative_transform_arrays']:
   with np.load(P/row['representative_transform_arrays'],allow_pickle=False) as z:
    assert digest(z['pre_transform'])==row['pre_transform']['sha256'] and np.array_equal(crop_map(z['pre_transform']),image)
    assert np.array_equal(z['post_transform_RGB3'],image[:3]);representatives+=1
  rgb8=np.rint(image[:3].transpose(1,2,0)*255).clip(0,255).astype(np.uint8);sheet.paste(Image.fromarray(rgb8),((j%4)*256,(j//4)*276+20));draw.text(((j%4)*256+3,(j//4)*276+4),row['id'],fill='black');imgs[row['id']]=image.copy()
  rows.append(dict(id=row['id'],all_actual_item_tensors_match_saved_collate_hashes=True,HDF5_state_actions_time_mask_exact=True,source_scene_XML_identity='UNAVAILABLE',raw_to_crop_recomputed=raw_checked,RGB_min=float(image[:3].min()),RGB_max=float(image[:3].max()),RGB_std=float(image[:3].std()),image_sha256=digest(image)))
repeats=[]
for row in v['items']:
 orig=row['sample'].get('repeat_of')
 if orig:
  equal=np.array_equal(imgs[row['id']],imgs[orig]);assert equal;repeats.append(dict(id=row['id'],repeat_of=orig,actual_full9channel_tensors_bit_equal=equal))
ev=[json.loads(l) for l in (P/f'results/{phase}/events.jsonl').read_text().splitlines()];counts=dict(Counter(x['event'] for x in ev));reads=[x for x in ev if x['event'].startswith('mjr_readPixels')]
assert counts['mjr_render_before']==len(v['items']) and counts['mjr_readPixels_before']==2*len(v['items'])
for e in reads:assert e['current_present'] and e['gl']['errors']['codes']==[0] and e['gl']['draw_bound_object']['status']==e['gl']['read_bound_object']['status']==36053
out=dict(phase=phase,stage=st,items=rows,raw_array_pairs_independently_recomputed=raws,full9channel_prepost_representatives_recomputed=representatives,repeat_comparisons=repeats,unique_post_images=len(set(x['image_sha256'] for x in rows)),within_sampled_window_no_GL_or_tensor_fault=True,all_actual_post_crop_RGB_visually_reviewable_in_contact_sheet=True,native_target_window=v['natural_target_window'],guard_executed=[g['actual_guard_executed'] for g in v['guards']],guard_resets=[g['resets_added'] for g in v['guards']],event_counts=counts,unpersisted_raws_verified_only_by_runtime_hash_and_health_metadata=True)
if phase=='c-official':
 loc=read('c-local_result.json');comp=[]
 for b in v['batches']:
  lb=next(x for x in loc['batches'] if x['split']==b['split'])
  with np.load(P/lb['file'],allow_pickle=False) as z:comp.append(dict(split=b['split'],all_actual_collated_tensors_bit_equal=all(np.array_equal(z[k],a) for k,a in batches[b['file']].items())))
 out['actual_cross_arm_batch_comparisons']=comp
(P/f'artifacts/parent_{phase}_acceptance.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');sheet.save(P/f'figures/{phase}_actual_collate_RGB.png');print(json.dumps({k:x for k,x in out.items() if k not in ['items','event_counts','stage']},ensure_ascii=False))
