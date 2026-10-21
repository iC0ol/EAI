"""Phase 3.6 inference boundary. No geometry, private labels or history imports."""
import hashlib
import json
import os
from pathlib import Path
import sys

from .diagnostic_io import parse_response


def verify_frozen(root):
    root = Path(root).resolve()
    frozen = json.loads((root/'diagnostics/phase3_6/inputs/frozen_public.json').read_text())
    for name, expected in frozen['files'].items():
        path = (root/name).resolve()
        if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Frozen inference artifact changed: {name}')
    return frozen


def load_inputs(root):
    root = Path(root).resolve()
    rows = []; seen = set()
    for line in (root/'diagnostics/phase3_6/inputs/public_inputs.jsonl').read_text().splitlines():
        row = json.loads(line)
        if set(row) != {'query_id', 'image', 'input_image_sha256', 'context'} or row['query_id'] in seen:
            raise ValueError('Invalid/duplicate public input')
        seen.add(row['query_id'])
        image = (root/row['image']).resolve()
        if image.parent != root/'diagnostics/phase3_6/images' or image.suffix != '.png':
            raise ValueError('Image outside Phase 3.6 clean images')
        if hashlib.sha256(image.read_bytes()).hexdigest() != row['input_image_sha256']:
            raise ValueError('Image hash mismatch')
        if row['context'] != {'units': 'm', 'workspace_dimensions_m': [12, 12], 'robot_radius_m': .25}:
            raise ValueError('Unexpected context: only neutral metric information is permitted')
        rows.append((row, image))
    order = json.loads((root/'diagnostics/phase3_6/inputs/order.json').read_text())
    if [r['query_id'] for r, _ in rows] != order:
        raise ValueError('Frozen sample order mismatch')
    return rows


def read_firewall(root):
    root = Path(root).resolve()
    events = []
    def audit(event, args):
        if event != 'open' or not isinstance(args[0], (str, bytes)):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        mode = args[1]; flags = args[2] if len(args) > 2 else 0
        guarded = any(path.is_relative_to(root/p) for p in ['data', 'diagnostics', 'reports', 'outputs'])
        if not guarded:
            return
        writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or bool(flags & (os.O_WRONLY | os.O_RDWR))
        if writing:
            if not path.is_relative_to(root/'outputs/phase3_6'):
                raise PermissionError(f'Inference cannot modify protected artifacts: {path}')
            return
        if not any(path.is_relative_to(root/p) for p in ['diagnostics/phase3_6/inputs', 'diagnostics/phase3_6/images']):
            raise PermissionError(f'Inference cannot read private/baseline/history artifacts: {path}')
        events.append(str(path.relative_to(root)))
    sys.addaudithook(audit)
    return events
