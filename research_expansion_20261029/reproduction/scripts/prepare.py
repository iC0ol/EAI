"""Copy a separate local environment; fetch only fixed official source archives."""
import pathlib,urllib.request,tarfile,shutil,subprocess,os,time,json
from common import ROOT,utc,atomic_json,append_json,sha,own_env
def download(url,dest,limit):
    dest=pathlib.Path(dest)
    if dest.exists():return
    for attempt in range(3):
        n=0;temp=dest.with_suffix(dest.suffix+'.partial')
        try:
            with urllib.request.urlopen(url,timeout=60) as x, temp.open('wb') as out:
                while True:
                    b=x.read(1<<20)
                    if not b:break
                    n+=len(b)
                    if n>limit:raise RuntimeError('per-asset download limit')
                    out.write(b)
            temp.replace(dest);append_json(ROOT/'downloads.jsonl',{'url':url,'path':str(dest.relative_to(ROOT)),'bytes':n,'sha256':sha(dest),'utc':utc(),'attempt':attempt,'state':'COMPLETE'});return
        except Exception as e:
            append_json(ROOT/'downloads.jsonl',{'url':url,'bytes':n,'utc':utc(),'attempt':attempt,'state':'FAILED','error':str(e)})
            if attempt==2:raise
            time.sleep(5)
def unpack(archive,dest):
    if dest.exists():return
    with tarfile.open(archive) as t:
        base=t.getmembers()[0].name.split('/')[0]
        for m in t.getmembers():
            if m.name.startswith('/') or '..' in pathlib.Path(m.name).parts:raise ValueError('unsafe archive')
        t.extractall(ROOT/'vendor')
    (ROOT/'vendor'/base).rename(dest)
def main():
    for d in ['logs','cache','cache/pip','cache/torch','tmp','assets','vendor','stages','patches','checkpoints','results','manifests']: (ROOT/d).mkdir(parents=True,exist_ok=True)
    if not (ROOT/'env/bin/python').exists():
        source=pathlib.Path('/home/asus/EAI/u_consistency_pilot')
        shutil.copytree(source/'.runtime/python311',ROOT/'runtime/python311',symlinks=True)
        subprocess.run([str(ROOT/'runtime/python311/bin/python3.11'),'-m','venv',str(ROOT/'env')],check=True,env=own_env())
        subprocess.run(['cp','-a','--reflink=auto',str(source/'.venv-v3/lib/python3.11/site-packages')+'/.',str(ROOT/'env/lib/python3.11/site-packages')],check=True,env=own_env())
        atomic_json(ROOT/'environment_origin.json',{'utc':utc(),'method':'independent copy (reflink when supported), no shared writable package files','source_read_only':str(source/'.venv-v3'),'runtime':str(ROOT/'runtime/python311'),'network_bytes':0})
    assets=[('kyc','https://codeload.github.com/ripl/CamPoseOpensource/tar.gz/e0647105a0f3946581d253c55dc9fd1218fa0974',250<<20),('robosuite','https://codeload.github.com/ripl/robosuite/tar.gz/0df3a5f5782937fa2e8fa923910d616b73310b8d',500<<20)]
    for name,url,limit in assets:
        a=ROOT/'assets'/f'{name}.tar.gz';download(url,a,limit)
        unpack(a,ROOT/'vendor'/name)
    atomic_json(ROOT/'source_manifest.json',{'kyc':{'url':assets[0][1],'commit':'e0647105a0f3946581d253c55dc9fd1218fa0974','archive_sha256':sha(ROOT/'assets/kyc.tar.gz')},'robosuite':{'url':assets[1][1],'commit':'0df3a5f5782937fa2e8fa923910d616b73310b8d','archive_sha256':sha(ROOT/'assets/robosuite.tar.gz')}})
    print('PREPARE_SOURCE_ENV_COMPLETE',utc(),flush=True)
if __name__=='__main__':main()
