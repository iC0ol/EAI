"""Phase 3.6 controls. New layouts; the historical geometry/oracle/render stay immutable.

Designed witnesses and layout intentions are private validation assertions, never labels.
Labels are derived independently from the existing collision-checked BFS at three scales
and a second, GEOS polygon free-component calculation. Failed attempts are never replaced.
"""
import hashlib
import json
from pathlib import Path
import random
import subprocess
import time
import traceback

from PIL import Image, ImageDraw
from shapely import affinity, normalize, set_precision, to_wkb
from shapely.geometry import LineString, Point, Polygon, box, shape
from shapely.ops import unary_union
import yaml

from .diagnostic_data import render_poststate
from .geometry import CollisionModel, geo, obstacles, validate_scene
from .oracle import solve
from .render import font, png_bytes
from .vlm_io import sha256

ROOT = Path(__file__).resolve().parents[2]


def layouts():
    """Sixteen explicit constructions, not transformations of historical base scenes."""
    world = box(0, 0, 12, 12)
    elbow = unary_union([box(1, 1, 4, 10.5), box(1, 7.5, 11, 10.5)])
    triangle = Polygon([(2, 2), (10, 2), (6, 11)])
    courtyard = Polygon([(3, 2), (10, 2), (10, 10), (6, 10), (6, 7), (3, 7)])
    # Category, construction, Start, Goal, walls, colored rectangles, reference route.
    return [
        ('A', 'open horizontal traverse with peripheral island', (1.5, 6), (10.5, 6),
         [], [box(5, 9, 7, 10)], None),
        ('A', 'diagonal traverse between asymmetric corner islands', (2, 2), (10, 10),
         [], [box(1, 7, 3, 10), box(8, 1, 11, 3)], None),
        ('A', 'wide vertical aisle between full-height banks', (6, 1.5), (6, 10.5),
         [box(0, 0, 3.5, 12), box(8.5, 0, 12, 12)], [], None),
        ('A', 'shallow oblique traverse among three separated islands', (1.5, 4), (10.5, 7),
         [], [box(3, 1, 5, 2.5), box(6, 9, 9, 11), box(9, 1, 11, 2)], None),
        ('B', 'bypass a tall central block', (2, 6), (10, 6),
         [], [box(5, 3.5, 7, 8.5)], [(2, 6), (2, 2), (10, 2), (10, 6)]),
        ('B', 'right-angle corridor with one elbow', (2.5, 2.5), (9.5, 9),
         [world.difference(elbow)], [], [(2.5, 2.5), (2.5, 9), (9.5, 9)]),
        ('B', 'alternating boundary-anchored baffles', (2, 2), (10, 10),
         [box(4, 0, 5, 8), box(7, 4, 8, 12)], [],
         [(2, 2), (2, 9.5), (6, 9.5), (6, 2), (10, 2), (10, 10)]),
        ('B', 'exit open U then wrap around its exterior', (6, 6), (6, 1.5),
         [unary_union([box(3, 3, 4, 10), box(8, 3, 9, 10), box(3, 3, 9, 4)])], [],
         [(6, 6), (6, 10.9), (10.5, 10.9), (10.5, 1.5), (6, 1.5)]),
        ('C', 'full-height vertical separator', (2, 6), (10, 6),
         [box(5.6, 0, 6.4, 12)], [], None),
        ('C', 'full-width horizontal separator with upper spur', (3, 2), (9, 10),
         [unary_union([box(0, 5.6, 12, 6.4), box(3, 6.4, 4, 9)])], [], None),
        ('C', 'stepped separator joining left and right boundaries', (2, 10), (10, 2),
         [LineString([(0, 3), (4, 3), (4, 8), (8, 8), (8, 5), (12, 5)])
          .buffer(.35, cap_style=2, join_style=2).intersection(world)], [], None),
        ('C', 'diagonal band joining opposite corners', (2, 9), (10, 3),
         [Polygon([(0, 0), (0, 1.5), (10.5, 12), (12, 12), (12, 10.5), (1.5, 0)])], [], None),
        ('D', 'closed rectangular courtyard', (2, 2), (7, 7),
         [box(4, 4, 10, 10).difference(box(5, 5, 9, 9))], [], None),
        ('D', 'closed triangular enclosure', (1.3, 9), (6, 5.5),
         [triangle.difference(triangle.buffer(-.8, join_style=2))], [], None),
        ('D', 'closed polygonal annulus', (1.5, 6), (7.5, 6),
         [Point(7.5, 6).buffer(3, quad_segs=64).difference(Point(7.5, 6).buffer(2.1, quad_segs=64))], [], None),
        ('D', 'closed nonconvex stepped courtyard', (1.5, 9), (8, 5),
         [courtyard.difference(courtyard.buffer(-.8, join_style=2))], [], None),
    ]


def candidates(cfg):
    out = []
    for index, (category, name, start, goal, walls, objects, route) in enumerate(layouts()):
        sid = 'c_' + hashlib.sha256(f"phase3.6/{cfg['generation_seed']}/{index}".encode()).hexdigest()[:16]
        scene = {'sample_id': sid, 'seed': cfg['generation_seed'], 'workspace': geo(box(0, 0, 12, 12)),
                 'robot_radius_m': cfg['robot_radius_m'], 'start': list(start), 'goal': list(goal),
                 'walls': [geo(w) for w in walls], 'objects': [
                     {'id': f'o{j}', 'geometry': geo(o), 'color': '#DD9350'} for j, o in enumerate(objects)],
                 'render': {'size_px': cfg['image_size_px']}}
        out.append((scene, {'category': category, 'layout_description': name,
                           'reference_path': [list(p) for p in (route or [start, goal])] if category in 'AB' else None}))
    return out


def component_evidence(scene, inflated=False):
    """An independent polygon decomposition, with no grid or intended-category input."""
    model = CollisionModel.from_scene(scene)
    free = (model.safe_workspace.difference(model.inflated_obstacles) if inflated else
            model.workspace.difference(model.raw_obstacles))
    def polygons(g):
        if g.geom_type == 'Polygon':
            return [g]
        return [p for child in g.geoms for p in polygons(child)] if hasattr(g, 'geoms') else []
    parts = polygons(free)
    memberships = {key: [i for i, p in enumerate(parts) if p.contains(Point(scene[key]))]
                   for key in ['start', 'goal']}
    if any(len(v) != 1 for v in memberships.values()):
        raise ValueError('Endpoint has no unique free polygon component')
    return {'method': 'GEOS polygon difference and connected polygon components',
            'configuration_space_buffered': inflated, 'component_count': len(parts),
            'start_component': memberships['start'][0], 'goal_component': memberships['goal'][0],
            'same_component': memberships['start'] == memberships['goal'],
            'formal_continuous_space_proof': False}


def signature(scene):
    """Canonical collision geometry + endpoints under square D4 symmetries and S/G swap."""
    raw = obstacles(scene)
    variants = []
    for reflected in [False, True]:
        for angle in [0, 90, 180, 270]:
            def transform(g):
                if reflected:
                    g = affinity.scale(g, xfact=-1, yfact=1, origin=(6, 6))
                return set_precision(affinity.rotate(g, angle, origin=(6, 6)), 1e-7)
            wall = to_wkb(normalize(transform(raw))).hex()
            points = sorted(tuple(transform(Point(scene[k])).coords)[0] for k in ['start', 'goal'])
            variants.append(json.dumps([wall, points], sort_keys=True))
    return hashlib.sha256(min(variants).encode()).hexdigest()


def validate_control(scene, info, cfg):
    validate_scene(scene)
    model = CollisionModel.from_scene(scene, cfg['buffer_quad_segs'], cfg['contact_epsilon_m'])
    if not all(model.point_free(scene[k]) for k in ['start', 'goal']):
        raise ValueError('Start/Goal in collision')
    grids = [solve(scene, res, cfg['buffer_quad_segs'], cfg['contact_epsilon_m']) for res in cfg['resolutions_m']]
    if len({g['passable'] for g in grids}) != 1:
        raise ValueError('oracle_unresolved: resolutions disagree')
    truth = grids[0]['passable']
    components = component_evidence(scene, True)
    raw_components = component_evidence(scene, False)
    if components['same_component'] != truth:
        raise ValueError('oracle_unresolved: polygon topology and BFS disagree')
    # Intent is an assertion after both independent methods have produced their answers.
    if truth != (info['category'] in 'AB'):
        raise ValueError('Generation failed its intended control condition')
    direct = model.segment_free(scene['start'], scene['goal'])
    reference_clearance = None
    certificate = None
    if truth:
        route = info['reference_path']
        if route[0] != scene['start'] or route[-1] != scene['goal']:
            raise ValueError('Witness endpoints differ')
        if not all(model.segment_free(a, b) for a, b in zip(route, route[1:])):
            raise ValueError('Reference path collides')
        reference_clearance = model.path_clearance(route)
        if reference_clearance < cfg['positive_reference_clearance_min_m']:
            raise ValueError('Positive control has insufficient reference clearance')
        if direct != (info['category'] == 'A'):
            raise ValueError('Straight/detour condition failed')
    else:
        if raw_components['same_component']:
            raise ValueError('Negative lacks raw-geometry separation evidence')
        raw = obstacles(scene)
        edges = {'left': LineString([(0, 0), (0, 12)]), 'right': LineString([(12, 0), (12, 12)]),
                 'bottom': LineString([(0, 0), (12, 0)]), 'top': LineString([(0, 12), (12, 12)])}
        touched = [k for k, edge in edges.items() if raw.intersects(edge)]
        closed_holes = [Polygon(r) for w in scene['walls'] for p in
                        ([shape(w)] if shape(w).geom_type == 'Polygon' else shape(w).geoms) for r in p.interiors]
        enclosing = [h for h in closed_holes if h.contains(Point(scene['goal'])) and not h.covers(Point(scene['start']))]
        certificate = {'raw_components': raw_components, 'boundary_contacts': touched,
                       'goal_enclosed_holes': len(enclosing),
                       'scope': 'Explicit input polygons and GEOS topology evidence; not a formal verified proof. '
                                'Grid failure alone is never used as a continuous-space proof.'}
        if info['category'] == 'C' and not ({'left', 'right'} <= set(touched) or {'top', 'bottom'} <= set(touched)):
            raise ValueError('Separator not attached to opposite workspace boundaries')
        if info['category'] == 'D' and not enclosing:
            raise ValueError('Goal lacks closed enclosing wall ring')
    return {'sample_id': scene['sample_id'], **info, 'status': 'verified', 'passable': truth,
            'straight_segment_free': direct, 'reference_path_min_clearance_m': reference_clearance,
            'grids': grids, 'components': components, 'negative_certificate': certificate}


def qc_image(scene, label):
    image = render_poststate(scene)
    d = ImageDraw.Draw(image)
    def xy(p):
        return (72 + p[0]*52, 44 + (12-p[1])*52)
    if label['passable']:
        d.line([xy(p) for p in label['grids'][-1]['path']], fill='#932ED1', width=3)
        d.line([xy(p) for p in label['reference_path']], fill='#00A344', width=4)
    d.text((32, 700), f"PRIVATE QC | {label['category']} | reachable={label['passable']}", font=font(17), fill='#111827')
    margin = label['reference_path_min_clearance_m']
    d.text((32, 730), f"reference clearance={margin:.3f}m" if margin is not None else 'raw free components separated; no path',
           font=font(16), fill='#111827')
    return image


def montage(images, captions, path):
    canvas = Image.new('RGB', (4*384, 4*414), 'white')
    d = ImageDraw.Draw(canvas)
    for i, (im, caption) in enumerate(zip(images, captions)):
        x, y = (i % 4)*384, (i//4)*414
        canvas.paste(im.resize((384, 384)), (x, y))
        d.text((x+8, y+388), caption, font=font(13), fill='#111827')
    path.write_bytes(png_bytes(canvas))


def build(root=ROOT):
    root = Path(root)
    cfg = yaml.safe_load((root/'configs/phase3_6.yaml').read_text())['geometry']
    target = root/'diagnostics/phase3_6'
    target.mkdir(exist_ok=False)
    for sub in ['images', 'inputs', 'private/scenes']:
        (target/sub).mkdir(parents=True, exist_ok=False)
    report = root/'reports/phase3_6'
    (report/'private_qc').mkdir(exist_ok=False)
    attempts = []; labels = []; public = []; clean = []; qc = []
    started = time.perf_counter()
    historical = {signature(json.loads(p.read_text())) for p in (root/'data/scenes').glob('*/scene.json')}
    seen = set()
    try:
        for scene, info in candidates(cfg):
            sid = scene['sample_id']
            attempt = {'attempt': len(attempts)+1, 'sample_id': sid, 'category': info['category'], 'status': 'running'}
            attempts.append(attempt)
            try:
                (target/f'private/scenes/{sid}.json').write_text(json.dumps(scene, sort_keys=True, indent=2)+'\n')
                sig = signature(scene)
                if sig in historical or sig in seen:
                    raise ValueError('Duplicate/rotated/mirrored collision layout and endpoints')
                seen.add(sig)
                label = validate_control(scene, info, cfg)
                label['D4_geometry_signature'] = sig
                im = render_poststate(scene); content = png_bytes(im)
                relative = f'diagnostics/phase3_6/images/{sid}.png'
                (root/relative).write_bytes(content)
                public.append({'query_id': sid, 'image': relative, 'input_image_sha256': hashlib.sha256(content).hexdigest(),
                               'context': {'units': 'm', 'workspace_dimensions_m': [12, 12], 'robot_radius_m': .25}})
                q = qc_image(scene, label); (report/f'private_qc/{sid}.png').write_bytes(png_bytes(q))
                labels.append(label); clean.append(im); qc.append(q)
                attempt['status'] = 'verified'
                print(json.dumps({'sample_id': sid, 'category': info['category'], 'passable': label['passable'],
                                  'reference_clearance_m': label['reference_path_min_clearance_m']}), flush=True)
            except Exception as exc:
                attempt.update({'status': 'failed', 'error': repr(exc), 'traceback': traceback.format_exc()})
                raise  # Stop, preserve evidence, no automatic replacement/retry.
        if len(labels) != 16 or sum(x['passable'] for x in labels) != 8:
            raise ValueError('Incorrect sample count or label balance')
        random.Random(cfg['generation_seed']).shuffle(public)
        (target/'inputs/public_inputs.jsonl').write_text(''.join(json.dumps(r, sort_keys=True)+'\n' for r in public))
        (target/'inputs/order.json').write_text(json.dumps([r['query_id'] for r in public], indent=2)+'\n')
        (target/'private/private_labels.jsonl').write_text(''.join(json.dumps(r, sort_keys=True)+'\n' for r in labels))
        montage(clean, [f"{l['category']} / {l['sample_id']}" for l in labels], report/'scene_overview.png')
        montage(qc, [f"PRIVATE / {l['sample_id']}" for l in labels], report/'private_path_overview.png')
    finally:
        (target/'private/generation_attempts.jsonl').write_text(''.join(json.dumps(a, sort_keys=True)+'\n' for a in attempts))
        manifest = {'attempted': len(attempts), 'verified': sum(a['status']=='verified' for a in attempts),
                    'failed': sum(a['status']=='failed' for a in attempts), 'not_attempted': 16-len(attempts),
                    'automatic_replacements': 0, 'seed': cfg['generation_seed'],
                    'status': 'completed' if len(labels)==16 else 'stopped',
                    'seconds': time.perf_counter()-started,
                    'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()}
        (report/'generation_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
