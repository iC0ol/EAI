"""Provenance and schema corrections; CPU metadata only, no new observations."""
from diag_common import *
import subprocess
import h5py

def main():
    rows=[]
    for manifest,root in [('official_kyc_tree.json',R/'vendor/kyc'),('official_robosuite_blobs.json',R/'vendor/robosuite')]:
        obj=read(E/'inputs'/manifest)
        for x in obj['entries']:
            p=root/x['path']
            if not p.exists():
                rows.append({'path':str(p.relative_to(R)),'exists':False});continue
            raw=p.read_bytes()
            blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\x00'+raw).hexdigest()
            rows.append({'path':str(p.relative_to(R)),'remote_git_blob_sha1':x['sha'],
                         'local_git_blob_sha1':blob,'matches':blob==x['sha'],'sha256':sha(p)})
    write(E/'results/source_blob_audit.json',{'utc':utc(),'rows':rows,
          'mismatches':[v for v in rows if not v.get('matches',False)]})
    assert all(v.get('matches',False) for v in rows)
    paths=['02_联合研究最终报告.md','notes/04_复现结果独立审查.md','reproduction/FINAL_REPORT.md',
           'reproduction/PROTOCOL.md','reproduction/RECOVERY.md','reproduction/results/dev_summary.json',
           'reproduction/results/offline_action_audit.json','reproduction/manifests/C_config.json',
           'reproduction/scripts/run_experiment.py','reproduction/scripts/evaluate.py','reproduction/scripts/experiment_lib.py']
    old=[]
    for path in paths:
        rel='research_expansion_20261029/'+path
        blob=subprocess.check_output(['git','show','a03f16da9110f219be49a0994140c7617a6b45ff:'+rel],cwd=W)
        h=hashlib.sha256(blob).hexdigest()
        old.append({'path':rel,'git_commit_sha256':h,'local_sha256':sha(W/rel),'matches':h==sha(W/rel)})
    write(E/'results/old_11_source_audit.json',{'commit':'a03f16da9110f219be49a0994140c7617a6b45ff','rows':old})
    assert all(v['matches'] for v in old)
    versions=read(E/'results/versions.json')
    corrected={'utc':utc(),'supersedes_fields_in':'results/versions.json',
               'kyc_commit':'e0647105a0f3946581d253c55dc9fd1218fa0974',
               'robosuite_commit':'0df3a5f5782937fa2e8fa923910d616b73310b8d',
               'wrong_values_preserved':{k:versions[k] for k in ['kyc_commit','robosuite_commit']},
               'reason':'vendor trees were extracted from fixed codeload archives and have no .git; git rev-parse traversed to EAI parent. Independent remote Git blob checks above establish relevant source identity.',
               'observations_or_forward_calls_added':0,'scientific_gate_affected':False}
    write(E/'results/version_provenance_correction.json',corrected)
    schema=read(E/'results/data_schema.json')
    with h5py.File(R/'assets/liftrand_eef_delta.hdf5','r') as f:
        obs={group:list(f[f'data/demo_0/{group}']) for group in ['obs','next_obs']}
    write(E/'results/schema_clarification.json',{'utc':utc(),'demo0_obs_fields':obs,
          'supersedes_shorthand':schema['stored_rgb_or_xml'],
          'correct_description':'demo includes states/actions plus obs/next_obs/rewards/dones/starting_abs_action; obs contains no stored RGB. No demo XML attribute. Dataset reconstruction reads states/actions.',
          'observations_or_forward_calls_added':0})
    print(json.dumps({'official_blobs_verified':len(rows),'old_files_verified':len(old),'cuda_or_env_used':False}))

if __name__=='__main__':main()
