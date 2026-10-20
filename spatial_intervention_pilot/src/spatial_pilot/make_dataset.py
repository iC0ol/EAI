"""Generate only the checkpoint-B set, preserve every failure, keep model inputs clean."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime
import hashlib
import html
import json
from pathlib import Path
import subprocess
import sys
import traceback
from zoneinfo import ZoneInfo
import yaml
from .geometry import geo
from .oracle import label_scene
from .render import edit_descriptions, montage, png_bytes, public_text, render_private, render_public
from .scenes import build_scene, FAMILIES, STATES


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def public_record(scene, image_sha):
    return {
        'sample_id': scene['sample_id'], 'image': f"images/{scene['sample_id']}.png",
        'input_image_sha256': image_sha, 'units': 'm', 'robot_radius_m': scene['robot_radius_m'],
        'task_rules': scene['task_rules'], 'candidate_edits': edit_descriptions(scene),
        'candidate_geometry': {name: {'display_id': name, 'target_geometry': edit['target_geometry']}
                               for name, edit in scene['edits'].items()},
        'image_legend': 'Solid colored rectangles are current objects A/B. Dashed A\'/B\' are proposed final footprints, not post-edit observations or movement paths.',
    }


def _revision(project):
    def git(*args):
        r = subprocess.run(['git', '-C', str(project), *args], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None
    sources = ['src','tests','scripts','configs','README.md','AGENTS.md','pyproject.toml','requirements.lock']
    return {'source_commit': git('rev-parse', 'HEAD'),
            'source_status_at_generation': git('status','--short','--',*sources)}


def generate(config, output, project=None):
    if config['variants_per_family'] != 4 or config['phase_limit'] != 2:
        raise ValueError('Only Phase 2 checkpoint B (12 samples) is enabled')
    output = Path(output)
    for sub in ['data/images', 'data/scenes', 'reports/edits', 'outputs']:
        (output/sub).mkdir(parents=True, exist_ok=True)
    scenes, labels, public, failures, checksums = [], [], [], [], {}
    rendered_text = {}
    for family in FAMILIES:
        for variant in range(4):
            try:
                scene = build_scene(family, variant, config)
                label = label_scene(scene, config)
                sid = scene['sample_id']
                original = png_bytes(render_public(scene))
                (output/f'data/images/{sid}.png').write_bytes(original)
                sha = hashlib.sha256(original).hexdigest()
                checksums[f'data/images/{sid}.png'] = sha
                full_scene = deepcopy(scene)
                full_scene['post_edit_objects'] = {state: v['final_objects'] for state,v in label['states'].items()}
                dump(output/f'data/scenes/{sid}/scene.json', full_scene)
                for state, result in label['states'].items():
                    render_private(scene, state, result['fine']).save(output/f'reports/edits/{sid}_{state}.png')
                rendered_text[sid] = public_text(scene)
                scenes.append(scene); labels.append(label)
                public.append(public_record(scene, sha))
                print(f"{sid} {family} v{variant}: {label['labels']} [{label['status']}]", flush=True)
            except Exception as exc:
                failure = {'family': family, 'variant': variant, 'seed': config['seed'],
                           'error': repr(exc), 'traceback': traceback.format_exc()}
                failures.append(failure)
                print(failure['traceback'], file=sys.stderr, flush=True)
    for path, records in [('data/public_inputs.jsonl',public), ('data/private_labels.jsonl',labels),
                          ('reports/generation_failures.jsonl',failures)]:
        (output/path).write_text(''.join(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n' for row in records))
    # No fake responses: inference has intentionally not started.
    prediction = output/'outputs/predictions.jsonl'
    if not prediction.exists():
        prediction.write_text('')
    dump(output/'reports/rendered_text.json', rendered_text)
    dump(output/'reports/input_checksums.json', checksums)
    label_index = {label['sample_id']: label for label in labels}
    if scenes:
        montage(scenes, label_index, output/'reports/qc_montage.png')
        review_html(scenes, label_index, output/'reports/scene_review.html')
    manifest = {
        'schema_version': 1, 'created_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        'config': config, 'config_sha256': hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
        'attempted': 12, 'succeeded': len(scenes), 'failed': len(failures),
        'verified': sum(label['status']=='verified' for label in labels),
        'oracle_unresolved': sum(label['status']=='oracle_unresolved' for label in labels),
        'family_counts': dict(Counter(scene['family'] for scene in scenes)),
        'core_acceptance_samples': [s['sample_id'] for s in scenes if s['core_acceptance']],
        'matched_pairs': [[s['sample_id'] for s in scenes if s['matched_pair_group']==f'pair_v{v}'] for v in range(4)],
        'python': sys.version, 'phase_completed': 2, 'vlm_status': 'not_started_awaiting_user_review',
        'model_id': None, 'model_revision': None,
        'independence_note': '12 samples are 3 families x 2 geometric parameter sets x 2 views, not 12 independent topologies.',
        **(_revision(project) if project else {}),
    }
    dump(output/'reports/generation_manifest.json', manifest)
    if failures:
        raise RuntimeError(f'{len(failures)} of 12 generation attempts failed; see generation_failures.jsonl')
    return manifest


def review_html(scenes, labels, destination):
    cards = []
    for scene in scenes:
        sid = scene['sample_id']; label = labels[sid]
        cells = ''.join(f'<td>{html.escape(k)}</td><td>{int(v) if v is not None else "unresolved"}</td>' for k,v in label['labels'].items())
        images = ''.join(f'<figure><figcaption>{state} | F={label["labels"]["F_"+state]}</figcaption>'
                         f'<a href="edits/{sid}_{state}.png"><img src="edits/{sid}_{state}.png"></a></figure>' for state in STATES)
        descriptions = ''.join(f'<li>{html.escape(k+": "+v)}</li>' for k,v in edit_descriptions(scene).items())
        cards.append(f'<article><h2>{html.escape(scene["family"])} · v{scene["variant"]} · {sid}</h2>'
                     f'<p>core={scene["core_acceptance"]}; {label["status"]}; grid 0.10 / 0.05 m</p>'
                     f'<table><tr>{cells}</tr></table><ul>{descriptions}</ul>'
                     f'<p><a href="../data/images/{sid}.png">Original model input (768 px)</a> · '
                     f'<a href="../data/scenes/{sid}/scene.json">Complete private geometry</a></p>'
                     f'<div class="states">{images}</div></article>')
    destination.write_text('<!doctype html><html lang="zh"><meta charset="utf-8"><title>Spatial Pilot — PRIVATE QC</title>'
                          '<style>body{font:16px sans-serif;background:#edf1f5;color:#182332;margin:30px;max-width:1600px}'
                          'article{background:white;padding:20px;margin:24px 0;border-radius:12px}.states{display:grid;grid-template-columns:repeat(4,1fr)}'
                          'figure{margin:8px}img{width:100%}td{padding:6px 14px;border:1px solid #ddd}table{border-collapse:collapse}</style>'
                          '<h1>Spatial Intervention Pilot — 私有几何审查</h1><p>Original inputs contain only source objects and dashed candidate targets. '
                          'The edited states and green oracle paths below are private QC, excluded from model input. '
                          'F=0 means no route on both configured grids, not continuous-space impossibility. '
                          'No VLM or robot intervention has run.</p>'+''.join(cards)+'</html>')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default=Path('configs/pilot.yaml'))
    parser.add_argument('--output', type=Path, default=Path('.'))
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text())
    manifest = generate(config, args.output, Path(__file__).resolve().parents[2])
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
