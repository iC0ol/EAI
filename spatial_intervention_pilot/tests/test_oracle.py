from copy import deepcopy
import pytest
from shapely.geometry import box
from spatial_pilot.geometry import CollisionModel, geo
from spatial_pilot.oracle import neighbors4, solve
from spatial_pilot.scenes import EXPECTED, FAMILIES, STATES, build_scene
from spatial_pilot.edits import apply_edits


@pytest.mark.parametrize('family,variant', [(f,v) for f in FAMILIES for v in range(2)])
def test_core_six(family, variant, verified):
    scene, result = verified(family, variant)
    assert result['status'] == 'verified'
    assert list(result['labels'].values()) == EXPECTED[family]
    assert all(s['legal'] and not s['conflict'] and s['grid_agreement'] for s in result['states'].values())


@pytest.mark.parametrize('family,variant', [(f,v) for f in FAMILIES for v in [2,3]])
def test_additional_views(family, variant, verified):
    scene, result = verified(family, variant)
    assert result['status'] == 'verified'
    assert list(result['labels'].values()) == EXPECTED[family]


@pytest.mark.parametrize('family', FAMILIES)
def test_paths_are_valid_full_segments(family, verified):
    scene, label = verified(family,0)
    for state, entry in label['states'].items():
        after = apply_edits(scene, STATES[state])
        model = CollisionModel.from_scene(after)
        for resolution in ['coarse','fine']:
            result = entry[resolution]
            assert not result['continuous_unreachability_claimed']
            if result['passable']:
                path = result['path']
                assert path[0] == scene['start'] and path[-1] == scene['goal']
                assert result['path_min_clearance_m'] > 0
                assert all(model.segment_free(a,b) for a,b in zip(path[:-1],path[1:]))
            else:
                assert result['path_min_clearance_m'] is None and result['path'] == []


def empty_scene():
    return {'workspace': geo(box(0,0,3,3)), 'walls': [], 'objects': [],
            'start': [.5,1.0], 'goal': [2.5,1.0], 'robot_radius_m': .05}


def test_no_diagonal_adjacency():
    neighbors = set(neighbors4(1,1,3,3))
    assert neighbors == {(0,1),(2,1),(1,0),(1,2)}


def test_thin_wall_blocks_edges_between_free_nodes():
    scene = empty_scene()
    scene['walls'] = [geo(box(1.45,0,1.55,3))]
    result = solve(scene,1.0)
    assert not result['passable']
    assert result['status'] == 'unreachable_on_grid'


def test_diagonally_touching_walls_cannot_be_corner_cut():
    scene = empty_scene()
    scene['start'], scene['goal'] = [.5,.5], [2.5,2.5]
    scene['walls'] = [geo(box(1.45,0,1.55,1.55)), geo(box(0,1.45,1.55,1.55))]
    assert not solve(scene,.5)['passable']


def test_exact_start_is_not_silently_snapped_out_of_collision():
    scene = empty_scene()
    scene['walls'] = [geo(box(1.45,0,1.55,3))]
    scene['start'] = [1.49,1.03]
    assert solve(scene,1.)['status'] == 'endpoint_in_collision'


def test_arbitrary_endpoints_use_checked_connectors():
    scene = empty_scene()
    scene['start'],scene['goal'] = [.43,.73], [2.47,2.13]
    result = solve(scene,.5)
    assert result['passable']
    assert result['path'][0] == scene['start'] and result['path'][-1] == scene['goal']


def test_robot_contact_is_collision():
    scene = empty_scene()
    scene['walls'] = [geo(box(1.5,0,1.6,3))]
    model = CollisionModel.from_scene(scene)
    assert not model.point_free([1.45,1])
    assert not model.point_free([.05,.5])
    assert model.point_free([1.44,1])


def test_coarse_fine_disagreement_marks_unresolved(config, monkeypatch):
    from spatial_pilot import oracle
    scene = build_scene('serial',0,config)
    def mock_solve(scene,resolution,*args):
        return {'passable': resolution == config['fine_resolution_m'],
                'path_min_clearance_m': None, 'path': []}
    monkeypatch.setattr(oracle,'solve',mock_solve)
    result = oracle.label_scene(scene,config)
    assert result['status'] == 'oracle_unresolved'
    assert all(v is None for v in result['labels'].values())


def test_actual_narrow_corridor_requires_finer_grid():
    scene = empty_scene()
    scene['start'],scene['goal'] = [.4,.73], [2.6,.73]
    scene['walls'] = [geo(box(0,0,3,.65)),geo(box(0,.81,3,3))]
    # Safe center band approximately (0.70,0.76): coarse y=0,0.5,1 cannot sample it.
    assert not solve(scene,.5)['passable']
    assert solve(scene,.05)['passable']


@pytest.mark.parametrize('family', FAMILIES)
def test_color_and_object_ids_do_not_change_geometry_labels(family, config, verified):
    scene, expected = verified(family,0)
    changed = deepcopy(scene)
    rename = {o['id']:f'neutral_{i}' for i,o in enumerate(changed['objects'])}
    for obj in changed['objects']:
        obj['id'] = rename[obj['id']]
        obj['color'] = '#00FFFF'
    for edit in changed['edits'].values():
        edit['object_id'] = rename[edit['object_id']]
    actual = [solve(apply_edits(changed,names),config['grid_resolution_m'])['passable'] for names in STATES.values()]
    assert actual == list(expected['labels'].values())


def test_swapping_candidate_ids_permutates_labels(config, verified):
    scene,expected = verified('side_effect',0)
    changed = deepcopy(scene)
    changed['edits'] = {'A': scene['edits']['B'], 'B': scene['edits']['A']}
    values = {key:solve(apply_edits(changed,names),.1)['passable'] for key,names in STATES.items()}
    assert values['A'] == expected['labels']['F_B']
    assert values['B'] == expected['labels']['F_A']
    assert values['AB'] == expected['labels']['F_AB']
