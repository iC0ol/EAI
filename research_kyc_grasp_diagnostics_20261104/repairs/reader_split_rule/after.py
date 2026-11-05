"""Actual Dataset crop/id -> actual default_collate. No model, optimizer or loss."""
from .common import *
from .ledger import reserve
from .gates import worker_gate
import contextlib

@contextlib.contextmanager
def choices(sample,dataset,lib):
    import numpy as np
    before=lib.rng_state();lib.seed_all(sample['seed']);randint=np.random.randint;choice=np.random.choice;used=dict(time=0,camera=0)
    length=dataset.demo_lengths[sample['dataset_index']]
    def time_choice(low,high=None,size=None,dtype=int):
        if high is None and low==length and size is None and used['time']==0:used['time']+=1;return sample['t']
        return randint(low,high=high,size=size,dtype=dtype)
    def camera_choice(a,size=None,replace=True,p=None):
        window=np.arange(sample['dataset_index'],sample['dataset_index']+3,dtype=np.int64)
        if np.array_equal(a,window) and size==1 and replace is False and used['camera']==0:used['camera']+=1;return np.array([sample['camera_index']],np.int64)
        return choice(a,size=size,replace=replace,p=p)
    np.random.randint=time_choice;np.random.choice=camera_choice
    try:yield used
    finally:
        np.random.randint=randint;np.random.choice=choice;lib.restore_rng(before);require(used==dict(time=1,camera=1),'actual Dataset source draw interface differs')

def actual_guard_functions():
    # These two actual source IF nodes are the only extracted official train code.
    import ast,copy
    source=K/'train.py';tree=ast.parse(source.read_text());nodes=[n for n in ast.walk(tree) if isinstance(n,ast.If) and 'glCheckFramebufferStatus' in ast.unparse(n.test)]
    nodes=sorted(nodes,key=lambda n:n.lineno);require(len(nodes)==2,'official two guard positions changed')
    funcs=[]
    for n in nodes:
        module=ast.parse('def guard(env,gl):\n    pass\n');module.body[0].body=[copy.deepcopy(n)];ast.fix_missing_locations(module);scope={};exec(compile(module,str(source),'exec'),scope);funcs.append((scope['guard'],n.lineno))
    return funcs

def main(stage):
    worker_gate(stage)
    from .runtime_safety import isolation,torch_guards
    isolation()
    from .builders import configuration,audit_runtime,make_physics,training_setup,close_physics
    from .model_runtime import ModelRuntime
    from .roots import physics,digest_array
    import torch,numpy as np,random
    from torch.utils.data._utils.collate import default_collate
    modules,provenance,args,stats=configuration();torch_guards(torch);modelguard=ModelRuntime(save_inputs=False);lib=modules['experiment_lib']
    audit=audit_runtime(strict=False,owner_release=False);env=None;datasets=None;rows=[];batches=[];guard_rows=[];error=None;state='PARTIAL';fault_seen=False;split_faults={'validation':False,'train':False}
    try:
        env=make_physics(lib,audit,0)
        import OpenGL.GL as gl  # matches official explicit import placement, after env construction
        datasets=training_setup(env);initial_geometry=physics(env);write(audit.out/'initial_model_geometry.json',initial_geometry)
        (audit.out/'initial_generated_model.xml').write_text(env.model.get_xml())
        guard_functions=actual_guard_functions();plan=read(P/'sample_plan.json')['samples']
        for split,guard_index in [('validation',0),('train',1)]:
            split_fault=False; audit.label('OFFICIAL_GUARD_'+str(guard_index))
            before=physics(env);counts_before=read(P/'scope_state.json')['phase_counts'].get(stage,{}).copy()
            if stage=='c-official':guard_functions[guard_index][0](env,gl)
            counts_after=read(P/'scope_state.json')['phase_counts'].get(stage,{}).copy()
            (audit.out/('guard_position_'+str(guard_index)+'_generated_model.xml')).write_text(env.model.get_xml())
            guard_rows.append(dict(position=guard_index,official_source_line=guard_functions[guard_index][1],actual_guard_executed=stage=='c-official',before_geometry=before,after_geometry=physics(env),resets_added=counts_after.get('resets',0)-counts_before.get('resets',0)))
            items=[];item_rows=[];dataset=datasets[split]
            for sample in [x for x in plan if x['split']==split]:
                label=stage+'_'+sample['id'];audit.label(label);audit.persist_arrays=sample['save_raw'];captured={};original_transform=dataset.transforms
                def transform(image):
                    pre=image.detach().cpu().numpy().copy();draws=[];original_randint=random.randint
                    def draw(a,b):
                        value=original_randint(a,b);draws.append(dict(low=a,high=b,value=value));return value
                    random.randint=draw
                    try:out=original_transform(image)
                    finally:random.randint=original_randint
                    captured.update(pre=pre,post=out.detach().cpu().numpy().copy(),crop_draws=draws)
                    return out
                dataset.transforms=transform
                try:
                    reserve('getitems','reader',label)
                    with choices(sample,dataset,lib) as used:item=dataset[sample['dataset_index']]
                finally:dataset.transforms=original_transform
                frame=audit.frames[label]
                raw=audit.last_arrays['normal'].copy();sentinel=audit.last_arrays['sentinel'].copy()
                pre=captured['pre'];post=captured['post'];source_state=dataset.demo_states[sample['dataset_index']][sample['t']].copy();source_actions=dataset.demo_actions[sample['dataset_index']][sample['t']:].copy()
                require(np.array_equal(env.sim.get_state().flatten(),source_state.astype(np.float64)),'state/time correspondence changed during Dataset read')
                rgb_pre=np.flip(raw,0).transpose(2,0,1).astype(np.float32)/np.float32(255)
                require(np.array_equal(pre[:3],rgb_pre),'native uint8/flip/pre-crop tensor boundary mismatch')
                actual={k:v.detach().cpu().numpy().copy() for k,v in item.items()};require(all(np.isfinite(v).all() for v in actual.values()),'nonfinite actual Dataset tensor')
                require(np.array_equal(post,actual['image'][0]),'actual crop output not returned by Dataset')
                padded=np.zeros((dataset.max_seq_length,7),np.float32);valid=min(len(source_actions),dataset.max_seq_length);padded[:valid]=source_actions[:valid]
                expected_actions=(padded-stats['action_mean'])/stats['action_std'];expected_mask=np.arange(dataset.max_seq_length)>=valid
                require(np.array_equal(actual['actions'],expected_actions) and np.array_equal(actual['is_pad'],expected_mask),'action/time/padding label mismatch')
                draws=captured['crop_draws'];crop=None
                if split=='train':
                    require(len(draws)==3,'actual RandomCrop randint count changed');crop=dict(side=draws[0]['value'],top=draws[1]['value'],left=draws[2]['value'],interpolation='actual torchvision nearest',draws=draws)
                else:require(not draws,'validation id transform unexpectedly sampled crop')
                if crop is not None:
                    ix=np.floor(np.arange(256)*crop['side']/256).astype(int)
                    yy=crop['top']+ix[:,None];xx=crop['left']+ix[None,:]
                    mapped_normal=np.flip(raw,0)[yy,xx,:];mapped_sentinel=np.flip(sentinel,0)[yy,xx,:]
                else:mapped_normal=np.flip(raw,0);mapped_sentinel=np.flip(sentinel,0)
                reconstructed=mapped_normal.transpose(2,0,1).astype(np.float32)/np.float32(255)
                require(np.array_equal(reconstructed,post[:3]),'CPU nearest mapping does not match actual crop output')
                sentinel_post=mapped_sentinel.transpose(2,0,1).astype(np.float32)/np.float32(255)
                nondeterminism_survives_crop=not np.array_equal(post[:3],sentinel_post)
                geometry=physics(env);has_fault=not frame['readback_healthy'];fault_seen=fault_seen or has_fault;split_fault=split_fault or has_fault;split_faults[split]=split_fault
                representative=sample['save_full_tensor'] or has_fault
                transform_file=None
                if representative:
                    f=audit.out/(sample['id']+'_pre_post_transform.npz');save_npz(f,pre_transform=pre,post_transform_RGB3=post[:3],source_state=source_state,source_actions_raw=source_actions,actual_actions=actual['actions'],actual_is_pad=actual['is_pad']);transform_file=str(f.relative_to(P))
                    from PIL import Image
                    Image.fromarray(np.flip(raw,0)).save(audit.out/(sample['id']+'_raw.png'));Image.fromarray(np.rint(post[:3].transpose(1,2,0)*255).clip(0,255).astype(np.uint8)).save(audit.out/(sample['id']+'_actual_crop.png'))
                row=dict(id=sample['id'],sample=sample,label=label,source_state=digest_array(source_state),source_state_values=source_state.tolist(),source_actions=digest_array(source_actions),source_first_raw_action=source_actions[0].tolist(),source_demo_XML_available=False,actual_T=dataset.camera_poses[sample['camera_index']],actual_K=dataset._get_camera_intrinsics().tolist(),actual_geometry=geometry,frame=frame,pre_transform=digest_array(pre),post_transform=digest_array(post),actual_item_tensors={k:digest_array(v) for k,v in actual.items()},crop=crop,native_uint8_to_pre_crop_exact=True,post_crop_is_actual_item_exact=True,action_time_mask_exact=True,controlled_draws=dict(used),representative_transform_arrays=transform_file,all_item_arrays_retained_as_exact_collate_slice=True,current_input_health_fault_observed=has_fault,normal_to_actual_crop_CPU_reconstruction_exact=True,normal_sentinel_nondeterminism_survives_actual_crop=nondeterminism_survives_crop)
                items.append(item);item_rows.append(row);rows.append(row);write(P/(stage+'_progress.json'),dict(state='PARTIAL',items=rows,guards=guard_rows))
                if has_fault:break  # first health fault stops only this split, after saving actual item
            require(items,'empty reader audit batch');batch=default_collate(items);arrays={k:v.detach().cpu().numpy().copy() for k,v in batch.items()}
            for i,(item,row) in enumerate(zip(items,item_rows)):
                require(all(np.array_equal(arrays[k][i],v.detach().cpu().numpy()) for k,v in item.items()),'actual default_collate changed item')
                row['collate_slice']=dict(file=str((audit.out/('batch_'+split+'.npz')).relative_to(P)),index=i,all_tensors_exact=True)
            f=audit.out/('batch_'+split+'.npz');save_npz(f,**arrays)
            batches.append(dict(split=split,file=str(f.relative_to(P)),sha256=sha(f),sample_ids=[r['id'] for r in item_rows],tensor_metadata={k:digest_array(v) for k,v in arrays.items()},actual_default_collate=True,model_call=False,batch_size=len(items)))
            del batch,arrays,items
            # Enter the next predeclared split even after a validation health fault.
        require(modelguard.guard.policy_entries==modelguard.guard.internal_entries==0,'ACT attempted during training-reader audit')
        state='CURRENT_INPUT_HEALTH_FAULT_CAPTURED_PENDING_REVIEW' if fault_seen else 'COMPLETE_SAMPLED_READER_HEALTH_PENDING_PIXEL_REVIEW'
    except BaseException as exc:error=type(exc).__name__+': '+str(exc);raise
    finally:
        cleanup=None
        try:close_physics(env,audit,[] if datasets is None else [datasets['train'],datasets['validation']])
        except BaseException as exc:cleanup=type(exc).__name__+': '+str(exc);state='PARTIAL'
        events=[json.loads(x) for x in (audit.out/'events.jsonl').read_text().splitlines()] if (audit.out/'events.jsonl').exists() else []
        target=[i for i,e in enumerate(events) if e['event']=='natural_renderer_release_enter' and e.get('releasing_owner') and e.get('previous_context') and e['releasing_owner']!=e['previous_context'] and e['entry']!='CLEANUP']
        result=dict(utc=utc(),state=state,error=error,cleanup_error=cleanup,items=rows,batches=batches,guards=guard_rows,validation_fault=split_faults['validation'],train_fault=split_faults['train'],split_first_fault_stop_rule=True,natural_target_window='OBSERVED' if target else 'NOT_REPRODUCED',natural_target_indices=target,owner_aware_fix_installed=False,forced_GC_or_destructor=False,current_health_fault_with_actual_item_and_collate_saved=fault_seen and bool(batches),readback_nondeterminism_propagated_to_crop_and_collate=any(x.get('normal_sentinel_nondeterminism_survives_actual_crop') and x.get('collate_slice') for x in rows),readback_nondeterminism_propagated_to_actual_train_tensor=any(x['sample']['split']=='train' and x.get('normal_sentinel_nondeterminism_survives_actual_crop') and x.get('collate_slice') for x in rows),GL_fault_alone_does_not_prove_bad_pixel_content=True,pixel_stripes_blankness_and_duplicates='parent actual-array/image review required',history_of_training_corruption='UNPROVEN_NO_HISTORIC_RGB_FBO_LOGS',no_loss_used=True,ACT=0,optimizer_created=False,provenance=provenance,full_item_output_storage='each item exactly recoverable from actual collated tensor slice; selected representatives also stored separately to avoid44 duplicated9channel tensors')
        if stage=='c-official' and (P/'c-local_result.json').exists():
            local=read(P/'c-local_result.json');pairs=[]
            for row in rows:
                other=next((x for x in local['items'] if x['id']==row['id']),None)
                if other:pairs.append(dict(id=row['id'],same_source_state=other['source_state']==row['source_state'],same_controlled_sample=other['sample']==row['sample'],same_actual_geometry=other['actual_geometry']==row['actual_geometry'],same_raw=other['frame']['raw_sha256']==row['frame']['raw_sha256'],same_post_crop=other['post_transform']==row['post_transform'],pure_guard_effect_interpretable=other['actual_geometry']==row['actual_geometry']))
            result['matched_arm_comparisons']=pairs
        write(P/(stage+'_result.json'),result)
        if cleanup and error is None:raise RuntimeError(cleanup)
