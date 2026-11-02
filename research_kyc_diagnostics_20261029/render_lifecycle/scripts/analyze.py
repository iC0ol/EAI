"""CPU-only reconstruction and owner/context-separated causal evidence audit."""
from lc_common import *
import numpy as np
from PIL import Image

def transitions(before,after):
    changes=[]
    if before.get('owner_context')!=after.get('owner_context'):return changes
    for category,flag in [('framebuffers','is_framebuffer'),('renderbuffers','is_renderbuffer')]:
        for name,value in before.get(category,{}).items():
            new=after.get(category,{}).get(name,{})
            if value['id']==new.get('id') and value.get(flag) and new.get(flag) is False:
                changes.append({'kind':category,'name':name,'id':value['id'],'before':True,'after':False})
    return changes
def main():
    summary=[];object_pairs=[];restores=[];images=[];normal_hashes={};events_by_mode={};boundaries=0
    for wid,mode in [(1,'baseline'),(2,'fix')]:
        out=P/f'results/worker_{wid}_{mode}';events=[json.loads(v) for v in (out/'events.jsonl').read_text().splitlines()]
        events_by_mode[mode]=events;readback=read(out/'readback.json');entries=read(out/'entries.json');row_images=[];normal_hashes[mode]={}
        for row in entries:
            label=row['entry'];rb=next(v for v in readback if v['entry']==label)
            raw=np.load(P/rb['raw']['file']);flipin=np.load(out/(label+'_flip_input.npy'));flipout=np.load(out/(label+'_flip_output.npy'))
            tensor=np.load(out/(label+'_tensor_rgb.npy'))
            with np.load(out/(label+'_saved.npz')) as z:saved=z['rgb_float'].copy()
            png=np.asarray(Image.open(out/(label+'.png')))
            checks={'raw_flip_input':np.array_equal(raw,flipin),'flip_exact':np.array_equal(np.flip(raw,0),flipout),
                'tensor_roundtrip':np.array_equal(np.rint(tensor.transpose(1,2,0)*255).astype(np.uint8),flipout),
                'saved_exact':np.array_equal(tensor,saved),'png_exact':np.array_equal(png,flipout)}
            assert all(checks.values());boundaries+=len(checks)
            with np.load(out/(label+'_common_preprocess.npz')) as z:common=bool(np.array_equal(z['dataset'],z['evaluator']) and np.array_equal(z['dataset'],z['custom']))
            assert common
            summary.append({'condition':mode,'entry':label,'boundary_checks':{k:bool(v) for k,v in checks.items()},
                'common_raw_rgb_equal':common,'before_context':rb['before']['current_context'],'after_context':rb['after']['current_context'],
                'before_gl':rb['before']['gl'],'after_gl':rb['after']['gl'],'sentinel':rb['sentinel'],
                'state_sha256':row['state_sha256'],'T_sha256':row['T_sha256'],'xml_sha256':row['xml_sha256'],'pixel_sha256':row['pixel_sha256']})
            normal_hashes[mode][label]=row['pixel_sha256'];row_images.append(png)
        images.append(np.concatenate(row_images,axis=1))
        for i,b in enumerate(events):
            name='baseline_before_con_free' if mode=='baseline' else 'owner_bound_before_con_free'
            aftername='baseline_after_con_free' if mode=='baseline' else 'owner_bound_after_con_free'
            if b['event']!=name:continue
            following=next(((j,a) for j,a in enumerate(events[i+1:],i+1) if a['event']==aftername and a['owner_context']==b['owner_context']),None)
            if following is None:continue
            j,a=following
            namespace='active_objects' if mode=='baseline' else 'owner_objects'
            object_pairs.append({'condition':mode,'before_index':i,'after_index':j,'entry':b['entry'],
               'owner_context':b['owner_context'],'current_before':b['current_context'],'current_after':a['current_context'],
               'measured_namespace':namespace,'owner_measurement_before':b['owner_objects']['state'],
               'before_objects':b[namespace],'after_objects':a[namespace],'valid_to_invalid':transitions(b[namespace] or {},a[namespace] or {})})
        for i,e in enumerate(events):
            if e['event']=='previous_restored':
                restores.append({'condition':mode,'event_index':i,'current_context':e['current_context'],'active_objects':e['active_objects'],'gl':e['gl']})
    Image.fromarray(np.concatenate(images,axis=0)).save(P/'results/condition_comparison.png')
    same_fix=len(set(normal_hashes['fix'].values()))==1
    early_match=normal_hashes['baseline']['early']==normal_hashes['fix']['early']
    result={'utc':utc(),'state':'BOTH_CONDITIONS_COMPLETE_PENDING_PARENT_VISUAL_ACCEPTANCE','summary':summary,'object_pairs':object_pairs,'previous_restorations':restores,
       'five_boundaries_per_frame_verified':boundaries,'fixed_all_four_normal_images_bit_equal':same_fix,'baseline_early_matches_fixed_early_bit_equal':early_match,
       'all_states_equal':len({r['state_sha256'] for r in summary})==1,'all_T_equal':len({r['T_sha256'] for r in summary})==1,
       'all_xml_equal':len({r['xml_sha256'] for r in summary})==1,'condition_replication':'one process baseline, one process fix; not statistical repeat',
       'historic_checkpoint_failure_cause':'UNKNOWN','model_or_rollout_added':False,'GL_query_caveat':'queries may introduce/clear errors; non-current owner is not measured; FBO0 status is not assigned to offFBO'}
    fixed_events=events_by_mode['fix']
    image_end=max(i for i,e in enumerate(fixed_events) if e['event']=='entry_after')
    release_before_images_done=[i for i,e in enumerate(fixed_events[:image_end+1]) if e['event']=='owner_bound_before_con_free']
    result.update(causal_validation='PARTIAL: fixed old renderer was released only during final cleanup, not during image acquisition',
       fixed_owner_release_during_image_acquisition_indices=release_before_images_done,
       fixed_image_acquisition_last_event_index=image_end,
       real_GL_live_other_previous_restore_count=len(restores),
       live_other_previous_restore_validation='CPU_MOCK_ONLY; NOT_EXERCISED_IN_REAL_GL' if not restores else 'see events',
       healthy_images_caused_by_fix='NOT_ESTABLISHED: no fixed destructor executed before healthy frames completed',
       failure_trigger_phase_by_condition={m:[{'before_event_index':x['before_index'],'entry':x['entry'],'owner':x['owner_context']} for x in object_pairs if x['condition']==m] for m in ['baseline','fix']})
    write(P/'analysis.json',result)
    frozen=read(P/'run_manifest.json');old=read(P/'local_only/old_directory_baseline.json');diff=[]
    for name,meta in old.items():
        file=D/name
        if not file.exists() or {'bytes':file.stat().st_size,'mtime_ns':file.stat().st_mtime_ns,'sha256':sha(file)}!=meta:diff.append(name)
    source_ok={f:sha(Path(f))==h for f,h in frozen['sources'].items()};code_ok={f:sha(P/'scripts'/f)==h for f,h in frozen['scripts'].items()}
    processes=[]
    for r in read(P/'completion.json')['worker_processes']:
        now=proc(r['identity']['pid']);processes.append({'pid':r['identity']['pid'],'original_process_alive':bool(now and now['start_ticks']==r['identity']['start_ticks'] and now['state']!='Z')})
    write(P/'integrity.json',{'utc':utc(),'old_files_checked':len(old),'old_changes':diff,'source_hashes_unchanged':source_ok,'frozen_executed_code_unchanged':code_ok,
       'workers':processes,'protocol_sha256':sha(P/'PROTOCOL.md'),'new_disk_bytes':sum(f.stat().st_size for f in P.rglob('*') if f.is_file()),
       'postprocess_script_sha256':sha(P/'scripts/analyze.py')})
    assert not diff and all(source_ok.values()) and all(code_ok.values()) and not any(x['original_process_alive'] for x in processes)
    assert same_fix and early_match and result['all_states_equal'] and result['all_T_equal'] and result['all_xml_equal']
    print(json.dumps({'boundaries_verified':boundaries,'fixed_images_bit_equal':same_fix,'early_images_match':early_match,
       'baseline_current_object_loss_pairs':len([p for p in object_pairs if p['condition']=='baseline' and p['valid_to_invalid']]),
       'fixed_owner_object_release_pairs':len([p for p in object_pairs if p['condition']=='fix' and p['valid_to_invalid']]),
       'previous_restorations':len(restores),'old_files_unchanged':len(old)}))
if __name__=='__main__':main()
