"""Phase 3.5 model-facing input, strict parsing and read firewall. No oracle imports."""
import hashlib
import json
from pathlib import Path
import sys
import os

FIELDS = ('start','goal','walls','other_original')


def strict_json(raw):
    def unique(pairs):
        out={}
        for key,value in pairs:
            if key in out:
                raise ValueError(f'Duplicate JSON key: {key}')
            out[key]=value
        return out
    def invalid(token):
        raise ValueError(f'Non-JSON constant: {token}')
    return json.loads(raw,object_pairs_hook=unique,parse_constant=invalid)


def parse_response(raw,kind):
    try:
        value = strict_json(raw)
        def boolean_or_null(v):
            if v is not None and type(v) is not bool:
                raise ValueError('Expected boolean or null')
        if not isinstance(value,dict):
            raise ValueError('Expected JSON object')
        if kind=='poststate':
            if set(value)!={'passable','explanation'}:
                raise ValueError('Expected passable and explanation')
            boolean_or_null(value['passable'])
        elif kind=='overlap':
            if set(value)!={'A','B','AB_targets','explanation'}:
                raise ValueError('Expected A, B, AB_targets and explanation')
            for name in ['A','B']:
                if not isinstance(value[name],dict) or set(value[name])!=set(FIELDS):
                    raise ValueError('Invalid target-overlap fields')
                for v in value[name].values():
                    boolean_or_null(v)
            boolean_or_null(value['AB_targets'])
        else:
            raise ValueError('Unknown diagnostic kind')
        if not isinstance(value['explanation'],str) or not value['explanation'].strip():
            raise ValueError('Expected nonempty explanation')
        return {'parse_ok':True,'parsed_output':value,'parse_error':None}
    except (ValueError,TypeError) as exc:
        return {'parse_ok':False,'parsed_output':None,'parse_error':f'{type(exc).__name__}: {exc}'}


def load_inputs(root,kind):
    root=Path(root).resolve()
    path=root/f'diagnostics/phase3_5/inputs/{kind}.jsonl'
    rows=[]
    seen=set()
    for line in path.read_text().splitlines():
        row=json.loads(line)
        if set(row)!={'query_id','image','input_image_sha256','context'} or row['query_id'] in seen:
            raise ValueError('Invalid or duplicate diagnostic input')
        seen.add(row['query_id'])
        image=(root/row['image']).resolve()
        allowed=root/('diagnostics/phase3_5/images' if kind=='poststate' else 'data/images')
        if image.parent!=allowed or image.suffix!='.png':
            raise ValueError('Image outside allowed input directory')
        if hashlib.sha256(image.read_bytes()).hexdigest()!=row['input_image_sha256']:
            raise ValueError('Image SHA256 mismatch')
        expected_context=({'units','workspace_dimensions_m','robot_radius_m'} if kind=='poststate' else
            {'units','robot_radius_m','candidate_edits','candidate_geometry','image_legend'})
        if set(row['context'])!=expected_context:
            raise ValueError('Unexpected context fields')
        rows.append((row,image))
    return rows


def read_firewall(root):
    root=Path(root).resolve()
    events=[]
    def audit(event,args):
        if event!='open' or not isinstance(args[0],(str,bytes)):
            return
        path=Path(os.fsdecode(args[0])).resolve()
        mode=args[1]; flags=args[2] if len(args)>2 else 0
        guarded = any(path.is_relative_to(root/p) for p in ['data','diagnostics','reports','outputs'])
        if not guarded:
            return
        writing=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or bool(flags&(os.O_WRONLY|os.O_RDWR))
        if writing:
            if not path.is_relative_to(root/'outputs/phase3_5'):
                raise PermissionError(f'Diagnostic inference cannot modify protected artifacts: {path}')
            return
        allowed = any(path.is_relative_to(root/p) for p in ['diagnostics/phase3_5/inputs',
                   'diagnostics/phase3_5/images','data/images'])
        if not allowed:
            raise PermissionError(f'Diagnostic inference cannot read: {path}')
        events.append(str(path.relative_to(root)))
    sys.addaudithook(audit)
    return events
