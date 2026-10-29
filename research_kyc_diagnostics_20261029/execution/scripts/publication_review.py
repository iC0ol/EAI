"""Explicit publication allowlist and secret/size checks; no broad git add."""
from diag_common import *
import re
import subprocess
import numpy as np

def main():
    relative=E.relative_to(W)
    raw=subprocess.check_output(['git','ls-files','--others','--exclude-standard','-z','--',str(relative)],cwd=W)
    names=[n for n in raw.decode().split('\0') if n]
    paths=[];excluded=[]
    for name in names:
        p=W/name;rel=p.relative_to(E)
        allow=p.name=='.gitignore' or (len(rel.parts)==1 and p.suffix in ['.json','.jsonl','.md']) or (
            rel.parts[0] in ['scripts','inputs','results','stages'] and p.suffix in ['.py','.json','.jsonl','.npz','.png'])
        if not allow or any(x in rel.parts for x in ['cache','tmp','logs','local_only','__pycache__']):excluded.append(name);continue
        assert p.stat().st_size<10*2**20,(name,'not small')
        if p.suffix=='.npz':
            with np.load(p,allow_pickle=False) as z:
                for key in z:
                    assert z[key].dtype.kind in 'fbiu', (name,key,'non-numeric payload')
        paths.append(name)
    patterns=[r'\bsk-[A-Za-z0-9_-]{20,}',r'\bgh[pousr]_[A-Za-z0-9]{20,}',
              r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----',r'(?i)authorization:\s*bearer\s+[^\s\"\']+']
    hits=[]
    for name in paths:
        p=W/name
        if p.suffix in ['.py','.json','.jsonl','.md']:
            content=p.read_text()
            if any(re.search(pattern,content) for pattern in patterns):hits.append(name)
    assert not hits,hits
    assert sum((W/p).stat().st_size for p in paths)<100*2**20
    extra=str(relative/'publication_review.json')
    if extra not in paths:paths.append(extra)
    result={'utc':utc(),'scope':'only executor-authored execution directory; parent research documents remain unstaged',
            'files':sorted(paths),'excluded_untracked':excluded,'credential_pattern_hits':hits,
            'bytes_before_this_manifest':sum((W/p).stat().st_size for p in paths if (W/p).exists()),
            'per_file_cap_bytes':10*2**20,'raw_cli_xml_runtime_cache_third_party_assets_excluded':True,
            'target_repository':'https://github.com/iC0ol/EAI','target_branch':'research/u-gate0-v3-overnight'}
    write(E/'publication_review.json',result)
    write(D/'orchestration/executor_git_status.json',{'utc':utc(),'state':'READY_TO_STAGE_EXECUTOR_PATHS',
          'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip(),
          'index_owner':'executor until once-only callback; parent no Git index operations',
          'public_scope':str(relative),'files_count':len(paths),'publication_plan_sha256':sha(E/'publication_review.json')})
    print(json.dumps({'public_files':len(paths),'bytes':result['bytes_before_this_manifest'],'credential_hits':hits,'excluded':excluded}))

if __name__=='__main__':main()
