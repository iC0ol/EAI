from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import pytest
from PIL import Image,ImageColor
from shapely.geometry import box
from spatial_pilot.diagnostic_data import render_poststate,query_id
from spatial_pilot.diagnostic_geometry import pair_overlap,radius_capacity,perturbed,overlap_truth
from spatial_pilot.diagnostic_io import parse_response,load_inputs
from spatial_pilot.diagnostic_evaluate import pair_classification,match_queries,metrics
from spatial_pilot.edits import apply_edits
from spatial_pilot.geometry import geo
from spatial_pilot.render import png_bytes

ROOT=Path(__file__).resolve().parents[1]


def first_scene():
    return json.loads((ROOT/'data/scenes/s_80e62d24efbf/scene.json').read_text())


def test_derivative_inputs_are_separate_and_complete():
    rows=load_inputs(ROOT,'poststate')
    assert len(rows)==24 and len(load_inputs(ROOT,'overlap'))==6
    for row,path in rows:
        assert path.parent==ROOT/'diagnostics/phase3_5/images'
        assert set(row['context'])=={'units','workspace_dimensions_m','robot_radius_m'}
        assert not any(word in json.dumps(row) for word in ['family','oracle','F_A','F_AB','serial','parallel','side_effect'])


def test_images_have_no_answer_metadata_or_route_color():
    for row,path in load_inputs(ROOT,'poststate'):
        with Image.open(path) as image:
            assert image.size==(768,768) and image.mode=='RGB' and image.info=={}
            assert (22,160,133) not in {color for count,color in image.getcolors(768*768)}


def test_poststate_renderer_ignores_all_private_metadata_and_candidate_annotations():
    scene=apply_edits(first_scene(),['A','B'])
    changed=deepcopy(scene)
    changed.update({'family':'SECRET','labels':{'F_AB':True},'oracle_path':[[0,0],[12,12]],
                    'sample_id':'SECRET_FILENAME','edits':{},'state':'AB'})
    for obj in changed['objects']:
        obj['id']='SECRET_ID';obj['display_id']='SECRET_LABEL'
    assert png_bytes(render_poststate(scene))==png_bytes(render_poststate(changed))


def test_actual_target_is_solid_and_old_pose_cleared():
    scene=apply_edits(first_scene(),['A'])
    image=render_poststate(scene)
    def pixel(x,y):return image.getpixel((round(72+x/12*624),round(44+(12-y)/12*624)))
    a=next(o for o in scene['objects'] if o['display_id']=='A')
    assert pixel(2.7,1.05)==ImageColor.getrgb(a['color'])
    assert pixel(4,3)==ImageColor.getrgb('#F3F5F8')


@pytest.mark.parametrize('raw',[
    '```json\n{"passable":true,"explanation":"ok"}\n```',
    '{"passable":1,"explanation":"ok"}',
    '{"passable":true,"explanation":"ok","answer":1}',
    '{"passable":true,"passable":false,"explanation":"ok"}',
])
def test_poststate_malformed_answers_are_preserved_as_errors(raw):
    result=parse_response(raw,'poststate')
    assert not result['parse_ok'] and result['parsed_output'] is None and result['parse_error']


def test_null_remains_unknown_and_overlap_schema_is_strict():
    assert parse_response('{"passable":null,"explanation":"uncertain"}','poststate')['parsed_output']['passable'] is None
    value={'A':dict.fromkeys(['start','goal','walls','other_original'],False),
           'B':dict.fromkeys(['start','goal','walls','other_original'],False),
           'AB_targets':False,'explanation':'No overlap.'}
    assert parse_response(json.dumps(value),'overlap')['parse_ok']
    value['B']['walls']='false'
    assert not parse_response(json.dumps(value),'overlap')['parse_ok']


def test_overlap_positive_separated_and_boundary_only_controls():
    a=box(0,0,1,1)
    assert pair_overlap(a,box(.5,.5,1.5,1.5))['overlap']
    assert not pair_overlap(a,box(2,2,3,3))['overlap']
    touch=pair_overlap(a,box(1,0,2,1))
    assert not touch['overlap'] and touch['touches_without_area']


def test_overlap_oracle_has_positive_controls_without_new_model_samples():
    scene={'robot_radius_m':.25,'start':[2.25,2.25],'goal':[.25,3.25],
           'walls':[geo(box(0,3.8,4,4))],
           'objects':[{'id':'a','geometry':geo(box(.5,.5,1,1))},
                      {'id':'b','geometry':geo(box(2,2,2.5,2.5))}],
           'edits':{'A':{'object_id':'a','target_geometry':geo(box(2,2,2.5,2.5))},
                    'B':{'object_id':'b','target_geometry':geo(box(.6,.6,1.1,1.1))}}}
    truth=overlap_truth(scene)['answers']
    assert truth['A']['start'] and truth['A']['other_original']
    assert truth['B']['other_original'] and not truth['A']['goal'] and not truth['AB_targets']


def test_radius_capacity_brackets_known_straight_corridor():
    scene={'workspace':geo(box(0,0,4,2)),'walls':[],'objects':[],
           'start':[1,1],'goal':[3,1],'robot_radius_m':.25}
    result=radius_capacity(scene,.1,low=.001,high=1.2,tolerance=.005)
    assert result['status']=='bracketed'
    assert .99<result['max_radius_feasible_lower_m']<1.0
    assert .995<result['max_radius_infeasible_upper_m']<1.005
    assert not result['continuous_channel_width_claimed']


def test_perturbation_never_mutates_original_geometry():
    scene=first_scene();old=deepcopy(scene)
    changed=perturbed(scene,1.05,.02)
    assert scene==old and changed['robot_radius_m']==pytest.approx(.27)


def test_inference_firewall_blocks_truth_old_predictions_and_overwrites(tmp_path):
    script='''
from pathlib import Path
import sys
from spatial_pilot.diagnostic_io import read_firewall
root=Path(sys.argv[1])
blocked=['data/private_labels.jsonl','data/scenes/x/scene.json','reports/x.json','outputs/phase3/core/predictions.jsonl','diagnostics/phase3_5/private/query_map.json']
for name in blocked:
 p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('hidden')
allowed=root/'diagnostics/phase3_5/inputs/poststate.jsonl';allowed.parent.mkdir(parents=True,exist_ok=True);allowed.write_text('public')
read_firewall(root)
assert allowed.read_text()=='public'
for name in blocked:
 for mode in ['r','w']:
  try: (root/name).open(mode)
  except PermissionError: pass
  else: raise AssertionError('Protected artifact access allowed: '+name)
'''
    result=subprocess.run([sys.executable,'-c',script,str(tmp_path)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_query_ids_are_opaque_and_reproducible():
    value=query_id('poststate','s_80e62d24efbf','AB')
    assert value==query_id('poststate','s_80e62d24efbf','AB')
    assert 'AB' not in value and '80e62d' not in value


def test_pair_comparison_distinguishes_recovery_persistence_and_regression():
    assert pair_classification(False,True,True)=='phase3_wrong_poststate_correct'
    assert pair_classification(False,False,True)=='both_wrong'
    assert pair_classification(True,False,True)=='phase3_correct_poststate_wrong'
    assert pair_classification(True,True,True)=='both_correct'
    assert pair_classification(None,False,False)=='unknown_in_one_or_both'


def test_evaluation_does_not_discard_missing_or_duplicate_queries():
    with pytest.raises(ValueError,match='exactly one'):
        match_queries([{'query_id':'x'},{'query_id':'x'}],{'x':{},'y':{}})


def test_unknown_predictions_stay_in_metric_denominator():
    result=metrics([{'correct':True},{'correct':False}])
    assert result=={'correct':1,'denominator':2,'accuracy':.5}


def test_model_and_generation_parameters_match_phase3():
    import yaml
    old=yaml.safe_load((ROOT/'configs/vlm_smoke.yaml').read_text())
    new=yaml.safe_load((ROOT/'configs/phase3_5.yaml').read_text())
    for key in ['model_id','model_revision','model_local_dir','dtype','device','attention','seed','batch_size',
                'max_new_tokens','do_sample','use_model_defaults','temperature','top_p','top_k','num_beams','min_pixels','max_pixels']:
        assert old[key]==new[key]
