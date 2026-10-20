from copy import deepcopy
import pytest
from shapely.geometry import box, shape
from spatial_pilot.edits import ConflictingEdits, IllegalEdit, apply_edits
from spatial_pilot.geometry import geo
from spatial_pilot.scenes import FAMILIES, build_scene


@pytest.mark.parametrize('family,variant', [(f,v) for f in FAMILIES for v in range(4)])
def test_compatible_edits_commute(family, variant, config):
    scene = build_scene(family,variant,config)
    original = deepcopy(scene)
    ab = apply_edits(scene,['A','B'])
    ba = apply_edits(scene,['B','A'])
    sequential = apply_edits(apply_edits(scene,['A']),['B'])
    assert ab['objects'] == ba['objects'] == sequential['objects']
    assert scene == original


@pytest.mark.parametrize('offset', [(-10,-10),(1,7)])
def test_illegal_destination_not_zero_label(offset, config):
    from shapely.affinity import translate
    scene = build_scene('serial',0,config)
    target = translate(shape(scene['objects'][0]['geometry']),*offset)
    scene['edits']['A']['target_geometry'] = geo(target)
    with pytest.raises(IllegalEdit):
        apply_edits(scene,['A'])


def test_shape_change_cannot_masquerade_as_translation(config):
    scene = build_scene('serial',0,config)
    scene['edits']['A']['target_geometry'] = geo(box(2.4,.5,3.0,1.5))
    with pytest.raises(IllegalEdit,match='preserve'):
        apply_edits(scene,['A'])


def test_unknown_edit_and_unknown_object_are_errors(config):
    scene = build_scene('serial',0,config)
    with pytest.raises(IllegalEdit,match='Unknown edit'):
        apply_edits(scene,['C'])
    scene['edits']['A']['object_id'] = 'missing'
    with pytest.raises(IllegalEdit,match='Unknown object'):
        apply_edits(scene,['A'])


def test_same_object_writes_conflict(config):
    scene = build_scene('serial',0,config)
    scene['edits']['B'] = deepcopy(scene['edits']['A'])
    with pytest.raises(ConflictingEdits):
        apply_edits(scene,['A','B'])


def test_valid_individual_edits_can_conflict_jointly(config):
    scene = build_scene('serial',0,config)
    scene['edits']['B']['target_geometry'] = deepcopy(scene['edits']['A']['target_geometry'])
    apply_edits(scene,['A']); apply_edits(scene,['B'])
    with pytest.raises(ConflictingEdits,match='Overlapping'):
        apply_edits(scene,['A','B'])


def test_duplicate_edit_is_not_ignored(config):
    with pytest.raises(ConflictingEdits):
        apply_edits(build_scene('serial',0,config),['A','A'])


def test_illegal_edit_does_not_enter_oracle_as_false(config):
    from spatial_pilot.oracle import label_scene
    scene = build_scene('serial',0,config)
    scene['edits']['A']['target_geometry'] = geo(box(-1,-1,1,1))
    with pytest.raises(IllegalEdit):
        label_scene(scene,config)


@pytest.mark.parametrize('variant',range(4))
def test_new_blockage_has_geometry_and_route_effect(variant,verified):
    scene,label = verified('side_effect',variant)
    effect = label['local_effects']['B']
    assert effect['newly_blocked_area_m2'] > 0
    assert not shape(effect['newly_blocked_center_space']).is_empty
    assert effect['introduces_route_blockage_after_other_edit']
    assert label['labels']['F_A'] is True and label['labels']['F_AB'] is False
    actual = next(o['geometry'] for o in apply_edits(scene,['B'])['objects'] if o['display_id']=='B')
    assert actual == scene['edits']['B']['target_geometry']


@pytest.mark.parametrize('variant', range(4))
def test_pairs_have_same_local_edit_geometry(variant,config):
    serial = build_scene('serial',variant,config)
    parallel = build_scene('parallel',variant,config)
    assert serial['objects'] == parallel['objects']
    assert serial['edits'] == parallel['edits']
    assert serial['start'] == parallel['start'] and serial['goal'] == parallel['goal']
    assert serial['walls'] != parallel['walls']
