"""Strict public-only model input and JSON parsing. No geometry/oracle imports."""
import hashlib
import json
from pathlib import Path

PUBLIC_FIELDS = {'sample_id','image','input_image_sha256','units','robot_radius_m',
                 'task_rules','candidate_edits','candidate_geometry','image_legend'}
PREDICTION_KEYS = ('F_A','F_B','F_AB')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_public_records(project, config, selected_ids=None):
    root = Path(project).resolve()
    public_path = (root/config['public_inputs']).resolve()
    if public_path != root/'data/public_inputs.jsonl':
        raise ValueError('Only data/public_inputs.jsonl is allowed')
    image_root = (root/config['image_root']).resolve()
    if image_root != root/'data/images':
        raise ValueError('Only data/images is allowed')
    records = {}
    for line in public_path.read_text().splitlines():
        record = json.loads(line)
        if set(record) != PUBLIC_FIELDS:
            raise ValueError('Unexpected fields in public record')
        sid = record['sample_id']
        if sid in records:
            raise ValueError(f'Duplicate sample ID: {sid}')
        if selected_ids is not None and sid not in selected_ids:
            continue
        image = (public_path.parent/record['image']).resolve()
        if image.parent != image_root or image.suffix.lower() != '.png':
            raise ValueError('Image path escapes the public image directory')
        if sha256(image) != record['input_image_sha256']:
            raise ValueError(f'Image hash mismatch: {sid}')
        records[sid] = (record,image)
    if selected_ids is not None and set(records) != set(selected_ids):
        raise ValueError('Missing selected public sample')
    return records


def build_prompt(record, template):
    # Do not pass sample IDs, file paths, labels, family IDs or dataset metadata.
    context = {key:record[key] for key in ['units','robot_radius_m','task_rules',
               'candidate_edits','candidate_geometry','image_legend']}
    if template.count('{{PUBLIC_TASK_JSON}}') != 1:
        raise ValueError('Prompt template must have one public context slot')
    return template.replace('{{PUBLIC_TASK_JSON}}',json.dumps(context,ensure_ascii=True,sort_keys=True))


def parse_response(raw):
    """No JSON extraction, value coercion, repair, retry or oracle fallback."""
    try:
        def unique_object(pairs):
            out = {}
            for key,value in pairs:
                if key in out:
                    raise ValueError(f'Duplicate JSON key: {key}')
                out[key] = value
            return out
        value = json.loads(raw,object_pairs_hook=unique_object,
                           parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f'Non-JSON constant {token}')))
        if not isinstance(value,dict) or set(value) != set(PREDICTION_KEYS)|{'explanation'}:
            raise ValueError('Expected exactly F_A, F_B, F_AB, explanation')
        for key in PREDICTION_KEYS:
            if value[key] is not None and type(value[key]) is not bool:
                raise ValueError(f'{key} must be a JSON boolean or null')
        explanation = value['explanation']
        if not isinstance(explanation,dict) or set(explanation) != {'A','B','AB'}:
            raise ValueError('explanation must contain exactly A, B, AB')
        for key,text in explanation.items():
            if not isinstance(text,str) or not text.strip():
                raise ValueError(f'Invalid explanation for {key}')
        return {'parse_ok':True,'parsed_output':value,'parse_error':None}
    except (ValueError,TypeError) as exc:
        return {'parse_ok':False,'parsed_output':None,'parse_error':f'{type(exc).__name__}: {exc}'}


def inference_read_guard(project):
    """Block accidental private data/report reads in the inference process."""
    import sys
    root = Path(project).resolve()
    events = []
    def audit(event,args):
        if event != 'open' or not isinstance(args[0],(str,bytes)):
            return
        path = Path(args[0].decode() if isinstance(args[0],bytes) else args[0]).resolve()
        mode = args[1]
        flags = args[2] if len(args)>2 else 0
        import os
        writing = (isinstance(mode,str) and any(c in mode for c in 'wax+')) or bool(flags & (os.O_WRONLY|os.O_RDWR))
        if writing:
            return
        if path.is_relative_to(root/'data'):
            allowed = path == root/'data/public_inputs.jsonl' or path.is_relative_to(root/'data/images')
            events.append(str(path.relative_to(root)))
            if not allowed:
                raise PermissionError(f'Inference cannot read private data: {path}')
        if path.is_relative_to(root/'reports'):
            raise PermissionError(f'Inference cannot read reports/QC: {path}')
    sys.addaudithook(audit)
    return events
