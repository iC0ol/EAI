"""Summarize existing traces/logs and provenance; no model loading or simulation."""
import json,subprocess,platform,os,csv,math,datetime,difflib
from common import ROOT,read_json,atomic_json,utc,sha
import numpy as np
def rows(p):return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []
def main():
    dev=rows(ROOT/'results/dev_rollouts.jsonl');independent=[x for x in dev if x['tag'] is None];fixed=[];actions=[]
    for row in rows(ROOT/'results/dev_fixed_observation.jsonl'):
        p=np.load(ROOT/row['raw_chunks_path']);a=p['clean'];b=p['persistent-10'];d=b-a
        fixed.append({'root_id':row['root_id'],'first_clean_action':a[0].tolist(),'translation_delta_chunk_L2_m':float(np.linalg.norm(d[:,:3])),'rotation_delta_chunk_L2_rad':float(np.linalg.norm(d[:,3:6])),'gripper_sign_disagreement_fraction':float(np.mean((a[:,6]>=0)!=(b[:,6]>=0))),'gripper_max_abs_difference':float(np.max(np.abs(d[:,6]))),'translation_cumsum_delta_final_xyz_m':d[:,:3].sum(0).tolist()})
    for x in independent:
        p=np.load(ROOT/x['trace_path']);a=p['actions'];actions.append(a)
    allactions=np.concatenate(actions) if actions else None
    first=np.array([x['first_clean_action'] for x in fixed])
    trace={'utc':utc(),'independent_dev_roots':len(independent),'policy_rollouts_including_repeat':len(dev),'total_environment_steps':sum(x['steps'] for x in dev),'first_action_across_root_std_raw':first.std(0).tolist() if len(first) else None,'dev_executed_action_mean':allactions.mean(0).tolist() if allactions is not None else None,'dev_executed_action_std':allactions.std(0).tolist() if allactions is not None else None,'sum_translation_xyz_per_root_mean_m':np.mean([a[:,:3].sum(0) for a in actions],axis=0).tolist() if actions else None,'caution':'summed target-pose increments and action-vector differences are not measured EEF displacement or task success','fixed_metadata10':{'gripper_sign_disagreement_fraction_mean':float(np.mean([x['gripper_sign_disagreement_fraction'] for x in fixed])) if fixed else None,'roots_with_any_gripper_sign_disagreement':sum(x['gripper_sign_disagreement_fraction']>0 for x in fixed),'rows':fixed},'no_new_model_calls':True,'no_new_rollouts':True}
    atomic_json(ROOT/'results/offline_action_audit.json',trace)
    with (ROOT/'results/dev_per_root.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['root_id','success','steps','any_reach','any_grasp','max_object_height_m','action_l2_mean','seconds'])
        for x in independent:w.writerow([x[k] for k in ['root_id','success','steps','any_reach','any_grasp','max_object_height_m','action_l2_mean','seconds']])
    # Summaries of the genuine 60003 training updates, not fresh evaluations.
    training=rows(ROOT/'logs/training_steps.jsonl');val=rows(ROOT/'logs/validation.jsonl')
    with (ROOT/'results/training_curve.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['last_update_in_bin','completed_epochs','n_updates','mean_loss','mean_l1','mean_kl','mean_step_seconds'])
        for j in range(0,len(training),300):
            a=training[j:j+300];w.writerow([a[-1]['update'],a[-1]['completed_epochs'],len(a),*[(sum(x[k] for x in a)/len(a)) for k in ['loss','l1','kl','seconds']]])
    atomic_json(ROOT/'results/loss_summary.json',{'utc':utc(),'updates':len(training),'validation_passes':len(val),'first_train_loss':training[0]['loss'],'last_train_loss':training[-1]['loss'],'last1000_mean_train_loss':float(np.mean([x['loss'] for x in training[-1000:]])),'last1000_mean_train_l1':float(np.mean([x['l1'] for x in training[-1000:]])),'last_validation':val[-1],'caution':'loss reduction alone did not establish task learning'})
    files=['PROTOCOL.md','source_manifest.json','environment_origin.json','requirements.freeze','dependency_install.json','manifests/dataset_asset.json','manifests/imagenet_weights.json','frozen_training_plan.json','manifests/frozen_roots.json','manifests/C_config.json','checkpoint_manifest.json','checkpoints/C_latest.pt','checkpoints/C_previous.pt']
    sources=['vendor/kyc/policy_robosuite/train.py','vendor/kyc/policy_robosuite/utils.py','vendor/kyc/policy_robosuite/eval.py','vendor/kyc/policy_robosuite/cam_embedding.py','vendor/kyc/policy_robosuite/models/act.py','vendor/kyc/policy_robosuite/models/backbone.py','vendor/kyc/policy_robosuite/models/detr_vae.py','vendor/kyc/reproduce/paper_runs.yaml','vendor/robosuite/robosuite/wrappers/action_wrapper.py','vendor/robosuite/robosuite/environments/manipulation/lift_rand.py']
    manifest={'utc':utc(),'assets':[{ 'path':x,'bytes':(ROOT/x).stat().st_size,'sha256':sha(ROOT/x)} for x in files if (ROOT/x).exists()],'third_party_sources':[{ 'path':x,'sha256':sha(ROOT/x)} for x in sources],'root_snapshots':[{ 'path':str(p.parent.relative_to(ROOT)),**read_json(p)} for p in sorted((ROOT/'root_states').rglob('manifest.json'))],'third_party_source_edits':'none; import official ACT and Dataset directly; custom runner/evaluator around them','transient_download_credentials':'not retained; public Drive canonical URL/ID and asset hash retained','runtime_dependency_policy':'copied existing local runtime/packages to a new directory; no source environment modified; pip changes confined to env/'}
    atomic_json(ROOT/'asset_manifest.json',manifest)
    hw={'utc':utc(),'platform':platform.platform(),'python':platform.python_version(),'logical_cpus':os.cpu_count(),'actual_job_affinity':read_json(ROOT/'cpu_affinity.json'),'cpu':subprocess.check_output(['lscpu','-J'],text=True),'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.used,driver_version','--format=csv'],text=True),'initial_read_only_observation':{'gpu_memory_used_MiB':581,'MemAvailable_approx_GiB':23,'disk_available_approx_GiB':185,'source':'initial tool inventory, before preparation; not inferred from final snapshot'}}
    atomic_json(ROOT/'manifests/hardware.json',hw)
    # Full upstream mirror is excluded; repair affected the new harness only.
    current=(ROOT/'scripts/validate_semantics.py').read_text();before=current.replace("    replay=[json.loads(x) for x in (out/'expert_replays.jsonl').read_text().splitlines()] if (out/'expert_replays.jsonl').exists() else []\n","    replay=[]\n").replace("        if any(x['demo']==i for x in replay):continue\n",'').replace('        if i==1:\n','        if i==0:\n')
    old="""            rgb=render(env,T);Image.fromarray(rgb).save(out/'expert_demo0_final.png')
            rootxml=env.sim.model.get_xml();(out/'replay_model.xml').write_text(rootxml)
            state=env.sim.get_state().flatten().copy();env.reset_from_xml_string(rootxml);env.sim.set_state_from_flattened(state);env.sim.forward();rgb2=render(env,T)
            repeat={'same_xml_state_render_identical':bool(np.array_equal(rgb,rgb2)),'image_max_abs_difference':int(np.max(np.abs(rgb.astype(int)-rgb2.astype(int)))),'xml_sha256':sha(out/'replay_model.xml'),'state_shape':state.shape}
            atomic_json(out/'restore_check.json',repeat)
"""
    start=before.index('            rootxml=env.model.get_xml();');end=before.index("            assert repeat['same_xml_state_render_identical']",start);before=before[:start]+old+before[end:]
    diff=''.join(difflib.unified_diff(before.splitlines(True),current.splitlines(True),fromfile='harness_before_repair01.py',tofile='scripts/validate_semantics.py'))
    (ROOT/'patches/repair01_initial_root_restore.diff').write_text(diff)
    print('OFFLINE_AUDIT_COMPLETE',utc(),flush=True)
if __name__=='__main__':main()
