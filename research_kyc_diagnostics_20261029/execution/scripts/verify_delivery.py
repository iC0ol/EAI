"""CPU-only file preservation, code and resource reconciliation."""
from diag_common import *
import subprocess
import shutil
import numpy as np

def main():
    baseline=read(E/'local_only/old_file_baseline.json')
    differences=[]
    for name,meta in baseline.items():
        p=R/name
        if not p.exists():differences.append({'path':name,'reason':'MISSING'});continue
        current={'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns,'sha256':sha(p)}
        if current!=meta:differences.append({'path':name,'before':meta,'after':current})
    code=read(E/'code_manifest_stage1.json')['scripts']
    code_changes={p:{'frozen':h,'now':sha(E/p)} for p,h in code.items() if sha(E/p)!=h}
    r=read(E/'results/input_comparisons.json')
    arrays=[]
    for row in r['samples']:
        j=row['sample']['sample'];p=E/f'inputs/sample_{j:02d}.npz'
        assert sha(p)==row['npz_sha256']
        with np.load(p) as z:
            for key,meta in row['tensor_metadata'].items():
                raw=np.ascontiguousarray(z[key])
                assert hashlib.sha256(raw.tobytes()).hexdigest()==meta['sha256'],(j,key)
        arrays.append({'sample':j,'arrays_verified':len(row['tensor_metadata']),'file_sha256':sha(p)})
    counts=read(E/'counts.json');assert counts['total_policy_attempts']==0 and counts['optimizer_updates']==0
    gpu=[]
    raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv'],text=True)
    for name in ['supervisor_identity.json','active_child.json']:
        obj=read(E/name);obj=obj.get('identity',obj)
        now=proc(obj['pid'])
        gpu.append({'file':name,'recorded_identity':obj,'current_identity':now,
                    'original_process_live':bool(now and now['start_ticks']==obj['start_ticks'] and now['state']!='Z')})
    result={'utc':utc(),'old_files_checked':len(baseline),'old_file_differences':differences,
            'stage1_frozen_code_changes':code_changes,'input_file_array_hashes':arrays,
            'gpu_allocation_seconds':read(E/'stages/stage1.json')['gpu_allocation_seconds'],
            'counts':counts,'original_processes':gpu,'gpu_processes_after':raw,
            'new_disk_bytes':sum(p.stat().st_size for p in E.rglob('*') if p.is_file()),
            'disk_free_bytes':shutil.disk_usage(E).free,'protocol_sha256':sha(D/'01_有限排障执行任务书.md'),
            'classification_boundary':'D/IMPLEMENTATION-LIMITED; new rendering fault observed; historic checkpoint failure not causally located'}
    write(E/'delivery_integrity.json',result)
    assert not differences and not code_changes and all(not x['original_process_live'] for x in gpu)
    assert result['protocol_sha256']==PROTOCOL_SHA
    print(json.dumps({'old_files_unchanged':len(baseline),'arrays_verified':sum(x['arrays_verified'] for x in arrays),
                      'model_attempts':0,'gpu_seconds':result['gpu_allocation_seconds'],'new_disk_bytes':result['new_disk_bytes']}))

if __name__=='__main__':main()
