"""Upload existing reviewed Git objects through gh, preserving exact hashes.

Does not move any branch, rewrite commits, expose credentials, or alter the index.
Used only because large ordinary Git HTTPS pushes repeatedly returned HTTP 408.
"""
from pathlib import Path
import argparse, base64, datetime, json, re, subprocess, time

ROOT=Path(__file__).resolve().parents[2]
D=Path(__file__).resolve().parents[1]
REPO='iC0ol/EAI'
def git(*a): return subprocess.check_output(['git',*a],cwd=ROOT)
def identity(v):
    m=re.fullmatch(r'(.*) <([^>]*)> (\d+) ([+-])(\d\d)(\d\d)',v)
    assert m
    minutes=(int(m[5])*60+int(m[6]))*(1 if m[4]=='+' else -1)
    stamp=datetime.datetime.fromtimestamp(int(m[3]),datetime.timezone(datetime.timedelta(minutes=minutes))).isoformat()
    return {'name':m[1],'email':m[2],'date':stamp}
def commit_payload(sha):
    header,message=git('cat-file','commit',sha).decode('utf-8').split('\n\n',1)
    fields={};parents=[]
    for line in header.splitlines():
        k,v=line.split(' ',1)
        if k=='parent':parents.append(v)
        else:
            assert k in ('tree','author','committer'), 'unsupported commit header; preserve object rather than rewrite'
            fields[k]=v
    return {'tree':fields['tree'],'parents':parents,'author':identity(fields['author']),
            'committer':identity(fields['committer']),'message':message}
def api(kind,payload,expected):
    start=time.monotonic()
    p=subprocess.run(['gh','api','--method','POST',f'repos/{REPO}/git/{kind}','--input','-'],
                     input=json.dumps(payload),text=True,capture_output=True,timeout=120)
    if p.returncode:
        raise RuntimeError(f'{kind} {expected}: exit{p.returncode} {p.stderr[:400]} {p.stdout[:400]}')
    r=json.loads(p.stdout)
    assert r['sha']==expected,(kind,expected,r.get('sha'),'no branch update performed')
    return {'sha':expected,'kind':kind,'seconds':time.monotonic()-start,'verified_exact_hash':True}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base',required=True);parser.add_argument('--head',required=True)
    parser.add_argument('--verify-base-only',action='store_true');a=parser.parse_args()
    for v in [a.base,a.head]: assert re.fullmatch('[0-9a-f]{40}',v)
    assert subprocess.run(['git','merge-base','--is-ancestor',a.base,a.head],cwd=ROOT).returncode==0
    print(json.dumps({'base_commit_exact_upload_check':api('commits',commit_payload(a.base),a.base)}),flush=True)
    if a.verify_base_only:return
    record=D/'logs'/f'object_upload_{a.head}.json'
    state=json.loads(record.read_text()) if record.exists() else {'base':a.base,'head':a.head,'objects':{},'branch_moved':False}
    def save():
        tmp=record.with_suffix('.tmp');tmp.write_text(json.dumps(state,indent=2)+'\n');tmp.replace(record)
    ids=[line.split(' ',1)[0] for line in git('rev-list','--objects',f'{a.base}..{a.head}').decode().splitlines()]
    kinds={x:git('cat-file','-t',x).decode().strip() for x in ids}
    def upload(x):
        if x in state['objects']:return
        kind=kinds[x]
        if kind=='blob':
            raw=git('cat-file','blob',x);payload={'content':base64.b64encode(raw).decode(),'encoding':'base64'};endpoint='blobs'
        elif kind=='tree':
            entries=[]
            for row in git('ls-tree','-z',x).split(b'\0'):
                if not row:continue
                meta,name=row.split(b'\t',1);mode,typ,sha=meta.decode().split()
                if sha in kinds:upload(sha)
                entries.append({'path':name.decode('utf-8'),'mode':mode.zfill(6),'type':typ,'sha':sha})
            payload={'tree':entries};endpoint='trees'
        elif kind=='commit':
            payload=commit_payload(x)
            for p in payload['parents']:
                if p in kinds:upload(p)
            if payload['tree'] in kinds:upload(payload['tree'])
            endpoint='commits'
        else:raise RuntimeError('unsupported object type '+kind)
        r=api(endpoint,payload,x);state['objects'][x]=r;save()
        print(json.dumps({'uploaded':len(state['objects']),'total':len(ids),**r}),flush=True)
    upload(a.head)
    assert len(state['objects'])==len(ids)
    state['state']='ALL_OBJECTS_VERIFIED_NO_REF_UPDATE';save();print(json.dumps({'complete':True,'head':a.head,'objects':len(ids),'branch_moved':False}),flush=True)

if __name__=='__main__':main()
