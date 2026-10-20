"""Simultaneous final-pose edits. Movement trajectories are deliberately out of scope."""
from copy import deepcopy
from shapely.affinity import translate
from shapely.geometry import shape
from .geometry import CollisionModel, InvalidGeometry, geo, validate_scene


class IllegalEdit(ValueError):
    pass


class ConflictingEdits(IllegalEdit):
    pass


def apply_edits(scene, names):
    if len(names) != len(set(names)):
        raise ConflictingEdits('Duplicate edit')
    edited = deepcopy(scene)
    index = {obj['id']: obj for obj in edited['objects']}
    written = set()
    for name in names:
        if name not in scene['edits']:
            raise IllegalEdit(f'Unknown edit: {name}')
        edit = scene['edits'][name]
        obj_id = edit['object_id']
        if obj_id not in index:
            raise IllegalEdit(f'Unknown object: {obj_id}')
        if obj_id in written:
            raise ConflictingEdits(f'Two edits write object {obj_id}')
        written.add(obj_id)
        source = shape(index[obj_id]['geometry'])
        target = shape(edit['target_geometry'])
        if target.is_empty or not target.is_valid:
            raise IllegalEdit(f'Invalid target footprint: {obj_id}')
        moved = translate(source, target.centroid.x-source.centroid.x,
                          target.centroid.y-source.centroid.y)
        if not moved.equals_exact(target, tolerance=1e-8, normalize=True):
            raise IllegalEdit(f'Edit must preserve the footprint and orientation: {obj_id}')
        index[obj_id]['geometry'] = deepcopy(edit['target_geometry'])
    try:
        validate_scene(edited)
    except InvalidGeometry as exc:
        if len(names) > 1:
            raise ConflictingEdits(str(exc)) from exc
        raise IllegalEdit(str(exc)) from exc
    # Original single edits must also be legal for a combination to be compatible.
    if len(names) > 1:
        for name in names:
            apply_edits(scene, [name])
    return edited


def local_effect(scene, name, quad_segs=32, epsilon=1e-6):
    """Changed configuration-space area, including newly occupied destination."""
    after = apply_edits(scene, [name])
    before_model = CollisionModel.from_scene(scene, quad_segs, epsilon)
    after_model = CollisionModel.from_scene(after, quad_segs, epsilon)
    cleared = before_model.inflated_obstacles.difference(after_model.inflated_obstacles)
    added = after_model.inflated_obstacles.difference(before_model.inflated_obstacles)
    edit = scene['edits'][name]
    source = next(o['geometry'] for o in scene['objects'] if o['id'] == edit['object_id'])
    return {
        'object_id': edit['object_id'], 'source_geometry': source,
        'target_geometry': edit['target_geometry'],
        'cleared_center_space': geo(cleared), 'newly_blocked_center_space': geo(added),
        'cleared_area_m2': cleared.area, 'newly_blocked_area_m2': added.area,
    }
