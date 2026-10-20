"""Finite-resolution, four-neighbor BFS. Failure never asserts continuous impossibility."""
from collections import deque
from math import floor, ceil
import numpy as np
from .edits import apply_edits, local_effect
from .geometry import CollisionModel
from .scenes import STATES


def neighbors4(x, y, nx, ny):
    for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        xx, yy = x + dx, y + dy
        if 0 <= xx < nx and 0 <= yy < ny:
            yield xx, yy


def solve(scene, resolution, quad_segs=32, epsilon=1e-6):
    if not np.isfinite(resolution) or resolution <= 0:
        raise ValueError('Resolution must be finite and positive')
    model = CollisionModel.from_scene(scene, quad_segs, epsilon)
    bounds = model.workspace.bounds
    xs = np.arange(bounds[0], bounds[2] + resolution * .01, resolution)
    ys = np.arange(bounds[1], bounds[3] + resolution * .01, resolution)
    nx, ny = len(xs), len(ys)
    grid_x, grid_y = np.meshgrid(xs, ys)
    free = model.free_points(grid_x, grid_y)
    coords = np.stack([grid_x, grid_y], axis=-1)
    result = {'passable': False, 'status': 'unreachable_on_grid', 'resolution_m': resolution,
              'connectivity': 4, 'grid_shape': [ny, nx], 'explored_nodes': 0,
              'path': [], 'path_min_clearance_m': None,
              'effective_buffer_radius_m': model.effective_radius,
              'continuous_unreachability_claimed': False}
    if not model.point_free(scene['start']) or not model.point_free(scene['goal']):
        result['status'] = 'endpoint_in_collision'
        return result

    def edge_mask(first, second, candidates):
        mask = np.zeros(candidates.shape, dtype=bool)
        mask[candidates] = model.free_segments(first[candidates], second[candidates])
        return mask
    horizontal = edge_mask(coords[:, :-1], coords[:, 1:], free[:, :-1] & free[:, 1:])
    vertical = edge_mask(coords[:-1], coords[1:], free[:-1] & free[1:])

    def connectors(point):
        px, py = (point[0]-bounds[0])/resolution, (point[1]-bounds[1])/resolution
        choices = []
        for xx in sorted(set([floor(px), ceil(px)])):
            for yy in sorted(set([floor(py), ceil(py)])):
                if 0 <= xx < nx and 0 <= yy < ny and free[yy, xx] and model.segment_free(point, coords[yy, xx]):
                    choices.append((xx, yy))
        return choices
    sources = connectors(scene['start'])
    targets = set(connectors(scene['goal']))
    if not sources or not targets:
        result['status'] = 'endpoint_has_no_grid_connector'
        return result
    queue = deque(sources)
    parent = {p: None for p in sources}
    found = None
    while queue:
        x, y = queue.popleft()
        result['explored_nodes'] += 1
        if (x, y) in targets:
            found = (x, y)
            break
        for xx, yy in neighbors4(x, y, nx, ny):
            if (xx, yy) in parent:
                continue
            allowed = horizontal[y, min(x, xx)] if y == yy else vertical[min(y, yy), x]
            if allowed:
                parent[(xx, yy)] = (x, y)
                queue.append((xx, yy))
    if found is not None:
        nodes = []
        while found is not None:
            x, y = found
            nodes.append([float(xs[x]), float(ys[y])])
            found = parent[found]
        path = [scene['start']] + list(reversed(nodes)) + [scene['goal']]
        path = [p for i, p in enumerate(path) if i == 0 or not np.allclose(p, path[i-1], atol=1e-10, rtol=0)]
        result.update({'passable': True, 'status': 'reachable_on_grid', 'path': path,
                       'path_min_clearance_m': model.path_clearance(path)})
    return result


def label_scene(scene, config):
    labels = {}
    states = {}
    unresolved = False
    for state, names in STATES.items():
        after = apply_edits(scene, names)  # invalid/conflict is an exception, not False.
        coarse = solve(after, config['grid_resolution_m'], config['buffer_quad_segs'], config['contact_epsilon_m'])
        fine = solve(after, config['fine_resolution_m'], config['buffer_quad_segs'], config['contact_epsilon_m'])
        agrees = coarse['passable'] == fine['passable']
        unresolved |= not agrees
        labels[f'F_{state}'] = coarse['passable'] if agrees else None
        margin = fine['path_min_clearance_m']
        states[state] = {
            'legal': True, 'conflict': False, 'grid_agreement': agrees,
            'boundary_sensitive': margin is not None and margin < config['boundary_margin_trigger_m'],
            'coarse': coarse, 'fine': fine,
            'final_objects': after['objects'],
        }
    effects = {name: local_effect(scene, name, config['buffer_quad_segs'], config['contact_epsilon_m'])
               for name in ['A', 'B']}
    # Derived by actual reachability, with no reference to the template family.
    for name, other in [('A', 'B'), ('B', 'A')]:
        effects[name]['introduces_route_blockage_from_none'] = labels['F_NONE'] is True and labels[f'F_{name}'] is False
        effects[name]['introduces_route_blockage_after_other_edit'] = labels[f'F_{other}'] is True and labels['F_AB'] is False
    return {
        'sample_id': scene['sample_id'], 'family': scene['family'], 'family_id': scene['family_id'],
        'core_acceptance': scene['core_acceptance'], 'matched_pair_group': scene['matched_pair_group'],
        'seed': scene['seed'], 'status': 'oracle_unresolved' if unresolved else 'verified',
        'labels': labels, 'states': states, 'local_effects': effects,
        'oracle_scope': 'finite grid only; no claim of continuous-space unreachability or edit execution feasibility',
    }
