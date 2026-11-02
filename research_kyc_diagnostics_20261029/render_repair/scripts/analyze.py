"""Saved data only; validates boundaries, lifecycle events and preservation."""
from repair_common import *
import numpy as np
from PIL import Image
def main():
    out=P/'results/worker_2';events=[json.loads(s) for s in (out/'events.jsonl').read_text().splitlines()]
    reads=read(out/'readback.json');entries=read(out/'entries.json')
    summary=[]
    for row in entries:
        label=row['entry'];raw=np.load(P/next(r['raw']['file'] for r in reads if r['entry']==label))
        flipin=np.load(out/(label+'_flip_input.npy'));flipout=np.load(out/(label+'_flip_output.npy'))
        tensor=np.load(out/(label+'_float_tensor_rgb.npy'))
        with np.load(out/(label+'_saved.npz')) as z:saved=z['rgb_float']
        png=np.asarray(Image.open(out/(label+'.png')))
        checks={'raw_equals_flip_input':np.array_equal(raw,flipin),'flip_output_exact':np.array_equal(np.flip(raw,0),flipout),
          'tensor_to_flip_exact':np.array_equal(np.rint(tensor.transpose(1,2,0)*255).astype(np.uint8),flipout),
          'saved_tensor_exact':np.array_equal(tensor,saved),'png_exact':np.array_equal(png,flipout)}
        assert all(checks.values())
        r=next(r for r in reads if r['entry']==label)
        summary.append({'entry':label,'checks':{k:bool(v) for k,v in checks.items()},'context_before':r['before'],
            'context_after':r['after'],'sentinel':r['sentinel'],'common_raw_rgb_preprocessing':row['common_raw_rgb_preprocessing']})
    selected=[{'index_zero_based':i,**e} for i,e in enumerate(events) if e['entry']=='INIT' and e['event'] in
       ['after_make_env','before_Dataset','free_enter','free_exit','eglDestroyContext_enter','eglDestroyContext_exit','eglReleaseThread_enter','eglReleaseThread_exit','after_Dataset']]
    write(P/'analysis.json',{'utc':utc(),'state':'PARTIAL_REPAIR_FAILED','entries':summary,'initial_lifecycle_chain':selected,
       'initial_normal_control':'NOT_RUN; no healthy readback obtained','raw_fault_reproduced':True,'repair_context_binding_effective':True,
       'repair_image_restoration':False,'independent_valid_worker_repetition':'NOT_RUN; worker1 failed before env/render; worker2 only valid rendering process',
       'observed_trigger':'old ctx1 free interval occurred while ctx2 current; eglReleaseThread enter ctx2 and exit no current during Dataset construction',
       'buffer_trigger_boundary':'FBO was complete after make_env/before Dataset but undefined on old EGL free entry. The preceding MjrContext.con.free call was not individually traced; cross-context FBO deletion is a hypothesis, not proven.',
       'no_normal_control_boundary':'sentinel remains165 on both baseline/repair; combine no-current/FBO errors with raw corruption; do not infer normal-buffer write history from sentinel alone',
       'GL_error_query_boundary':'queries consume error flags and may generate errors; codes describe monitored query+call intervals, not exclusive attribution',
       'historic_0_of_32_cause':'UNKNOWN'})
    ims=[np.asarray(Image.open(out/(label+'.png'))) for label in ['baseline_dataset','baseline_evaluator','baseline_custom','repair_dataset','repair_evaluator','repair_custom']]
    Image.fromarray(np.concatenate([np.concatenate(ims[:3],1),np.concatenate(ims[3:],1)],0)).save(out/'comparison.png')
    baseline=read(P/'local_only/old_execution_baseline.json');diff=[]
    for name,b in baseline.items():
        f=D/'execution'/name
        if not f.exists() or {'bytes':f.stat().st_size,'mtime_ns':f.stat().st_mtime_ns,'sha256':sha(f)}!=b:diff.append(name)
    frozen=read(P/'run_manifest.json');sources={f:sha(Path(f))==h for f,h in frozen['sources'].items()}
    code=read(P/'engineering_recovery_code.json')['scripts'];code_ok={name:sha(P/'scripts'/name)==h for name,h in code.items()}
    alive=[]
    for worker in read(P/'completion.json')['worker_processes']:
        ident=worker['child_identity'];now=proc(ident['pid'])
        alive.append(bool(now and now['start_ticks']==ident['start_ticks'] and now['state']!='Z'))
    write(P/'integrity.json',{'utc':utc(),'old_execution_files_checked':len(baseline),'old_execution_differences':diff,
       'source_hashes_unchanged':sources,'executed_recovery_code_unchanged':code_ok,'original_worker_alive':alive,
       'protocol_sha256':sha(P/'01_渲染微诊断与最小修复任务书.md'),'new_disk_bytes':sum(p.stat().st_size for p in P.rglob('*') if p.is_file())})
    assert not diff and all(sources.values()) and all(code_ok.values()) and not any(alive)
    print({'boundaries_verified':len(summary)*5,'old_execution_files_unchanged':len(baseline),'repair':'FAILED','old_cause':'UNKNOWN'})
if __name__=='__main__':main()
