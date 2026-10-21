"""Phase 3.7 public-only readers and model/planner audit hook. No geometry imports."""
import hashlib
import json
import os
from pathlib import Path
import sys
from .diagnostic_io import parse_response


def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as stream:
        for chunk in iter(lambda:stream.read(16*1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def verify_frozen(root):
    data=json.loads((root/'diagnostics/phase3_7/inputs/frozen_public.json').read_text())
    for name,h in data['files'].items():
        p=(root/name).resolve()
        if not p.is_relative_to(root) or digest(p)!=h:raise ValueError(f'Frozen artifact changed: {name}')
    return data


def load_inputs(root, dataset):
    if dataset not in ['smoke','old16','new24']:raise ValueError('Unknown public dataset')
    seen=set();out=[]
    for line in (root/f'diagnostics/phase3_7/inputs/{dataset}.jsonl').read_text().splitlines():
        r=json.loads(line)
        if set(r)!={'query_id','image','input_image_sha256','context'} or r['query_id'] in seen:raise ValueError('Invalid/duplicate row')
        seen.add(r['query_id']);p=(root/r['image']).resolve()
        allowed=[root/'diagnostics/phase3_7/images',root/'diagnostics/phase3_6/images',root/'diagnostics/phase3_7/smoke']
        if p.parent not in allowed or p.suffix!='.png':raise ValueError('Forbidden image')
        if digest(p)!=r['input_image_sha256']:raise ValueError('Image checksum mismatch')
        if r['context']!={'units':'m','workspace_dimensions_m':[12,12],'robot_radius_m':.25}:raise ValueError('Nonneutral context')
        out.append((r,p))
    return out


def firewall(root):
    root=Path(root).resolve();events=[]
    def audit(event,args):
        if event!='open' or not isinstance(args[0],(str,bytes)):return
        p=Path(os.fsdecode(args[0])).resolve();mode=args[1];flags=args[2] if len(args)>2 else 0
        guarded=any(p.is_relative_to(root/k) for k in ['data','diagnostics','reports','outputs'])
        if not guarded:return
        writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or bool(flags&(os.O_WRONLY|os.O_RDWR))
        if writing:
            if not p.is_relative_to(root/'outputs/phase3_7'):raise PermissionError(f'Protected write: {p}')
            return
        if not any(p.is_relative_to(root/k) for k in ['diagnostics/phase3_7/inputs','diagnostics/phase3_7/images',
                                                     'diagnostics/phase3_7/smoke','diagnostics/phase3_6/images']):
            raise PermissionError(f'Private/history read denied: {p}')
        events.append(str(p.relative_to(root)))
    sys.addaudithook(audit)
    return events
