"""Small, explicit geometric templates, with controlled paired transformations."""
from copy import deepcopy
import hashlib
import random
from shapely.affinity import affine_transform
from shapely.geometry import box, LineString, mapping, shape
from shapely.ops import unary_union
from .geometry import geo, validate_scene

FAMILIES = ('serial', 'parallel', 'side_effect')
EXPECTED = {'serial': [False, False, False, True],
            'parallel': [False, True, True, True],
            'side_effect': [False, True, False, False]}
STATES = {'NONE': [], 'A': ['A'], 'B': ['B'], 'AB': ['A', 'B']}


def _polygons(geom):
    if geom.geom_type == 'Polygon':
        return [geo(geom)]
    return [geo(g) for g in geom.geoms if g.geom_type == 'Polygon']


def build_scene(family, variant, config):
    if family not in FAMILIES or variant not in range(4):
        raise ValueError('Checkpoint B supports exactly three families and four variants')
    seed = config['seed']
    base = variant % 2
    halfwidth = 0.8 + base * 0.1
    mid = 6.0 + base * 0.4
    world = box(0, 0, 12, 12)
    if family == 'parallel':
        lines = [[(1.5, 3), (10.5, 3)], [(1.5, 9), (10.5, 9)],
                 [(1.5, 3), (1.5, 9)], [(10.5, 3), (10.5, 9)]]
    else:
        lines = [[(1.5, 6), (1.5, 3), (mid, 3), (mid, 9), (10.5, 9), (10.5, 6)]]
    corridors = [LineString(line).buffer(halfwidth, cap_style='square', join_style='mitre')
                 for line in lines]
    # Dead-end parking pockets are on one side of each gate, so they do not
    # accidentally provide a bypass around an initially blocked passage.
    pockets = [box(2.1, 0.1, 3.3, 3 + halfwidth),
               box(8.7, 9 - halfwidth, 9.9, 11.9)]
    free_region = unary_union(corridors + pockets).intersection(world)
    height = 2 * halfwidth - 0.1

    def gate(cx, cy):
        return geo(box(cx - .35, cy - height/2, cx + .35, cy + height/2))

    gate_a, park_a = gate(4, 3), gate(2.7, 1.05)
    gate_b, park_b = gate(8, 9), gate(9.3, 10.95)
    rng = random.Random(seed + variant * 1009)
    colors = ['#E79536', '#916DCC']
    if variant % 2:
        colors.reverse()
    ids = ['crate_k', 'crate_m']
    rng.shuffle(ids)
    identity = hashlib.sha256(f'{seed}/{family}/{variant}'.encode()).hexdigest()[:12]
    scene = {
        'schema_version': 1, 'sample_id': f's_{identity}',
        'family': family, 'family_id': f'{family}_layout_{base}',
        'base_layout': base, 'variant': variant,
        'core_acceptance': variant < 2, 'matched_pair_group': f'pair_v{variant}' if family != 'side_effect' else None,
        'seed': seed, 'rng_seed': seed + variant * 1009, 'units': 'm', 'workspace': geo(world),
        'walls': _polygons(world.difference(free_region)),
        'objects': [
            {'id': ids[0], 'display_id': 'A', 'color': colors[0], 'geometry': gate_a},
            {'id': ids[1], 'display_id': 'B', 'color': colors[1],
             'geometry': park_b if family == 'side_effect' else gate_b},
        ],
        'start': [1.5, 6], 'goal': [10.5, 6],
        'robot_radius_m': config['robot_radius_m'],
        'robot_model': 'holonomic circular footprint; hypothetical final geometry only',
        'task_rules': {
            'task': 'Reach Goal from Start inside the workspace without robot contact with walls or objects.',
            'edits': 'Only listed final-pose translations are allowed. Object interiors may not overlap walls or each other. Boundary contact of objects is allowed.',
            'motion': 'A circular robot may translate in any planar direction; no heading or differential-drive constraint.',
            'intervention': 'Editing movement trajectories and the physical ability to move an object are not evaluated.',
        },
        'edits': {
            'A': {'object_id': ids[0], 'target_geometry': park_a},
            'B': {'object_id': ids[1], 'target_geometry': gate_b if family == 'side_effect' else park_b},
        },
        'counterbalance': {'rotation_deg': 0, 'mirror_x': False, 'palette_index': variant % 2, 'id_order': ids},
        'render': {'size_px': config['image_size_px'], 'version': config['render_version']},
    }
    # Variants 2,3 are controlled views of layouts 0,1, not independent evidence.
    matrices = [[1, 0, 0, 1, 0, 0], [0, -1, 1, 0, 12, 0],
                [-1, 0, 0, 1, 12, 0], [0, 1, 1, 0, 0, 0]]
    matrix = matrices[variant]
    scene = transform_scene(scene, matrix)
    scene['counterbalance'].update({'rotation_deg': [0, 90, 0, 90][variant], 'mirror_x': variant >= 2})
    validate_scene(scene)
    return scene


def transform_scene(scene, matrix):
    out = deepcopy(scene)
    def tx(g):
        return geo(affine_transform(shape(g), matrix))
    out['workspace'] = tx(scene['workspace'])
    out['walls'] = [tx(w) for w in scene['walls']]
    for obj in out['objects']:
        obj['geometry'] = tx(obj['geometry'])
    for edit in out['edits'].values():
        edit['target_geometry'] = tx(edit['target_geometry'])
    from shapely.geometry import Point
    for key in ['start', 'goal']:
        out[key] = list(affine_transform(Point(scene[key]), matrix).coords[0])
    return out


def all_scenes(config):
    if config['variants_per_family'] != 4:
        raise ValueError('Review checkpoint is capped at 12 samples; use four variants per family')
    return [build_scene(family, v, config) for family in FAMILIES for v in range(4)]
