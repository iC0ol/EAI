from pathlib import Path
import json
import subprocess
import sys
import numpy as np
from PIL import Image,ImageDraw
import pytest
import yaml
from spatial_pilot.scale_rgb import extract,search,dilate_disk,ExtractionFailure
from spatial_pilot.scale_io import load_inputs,digest
from spatial_pilot.control_scenes import signature
from spatial_pilot.geometry import CollisionModel,validate_scene

ROOT=Path(__file__).resolve().parents[1]
CFG=yaml.safe_load((ROOT/'configs/phase3_7.yaml').read_text())


def labels():return list(map(json.loads,(ROOT/'diagnostics/phase3_7/private/new24_labels.jsonl').read_text().splitlines()))


def test_predeclared_balance_generation_and_novelty():
    rows=labels();assert len(rows)==24 and sum(l['passable'] for l in rows)==12
    assert {c:sum(l['category']==c for l in rows) for c in 'ABCD'}==dict.fromkeys('ABCD',6)
    assert len({l['D4_geometry_signature'] for l in rows})==24
    old=[*(ROOT/'data/scenes').glob('*/scene.json'),*(ROOT/'diagnostics/phase3_6/private/scenes').glob('*.json')]
    assert not {signature(json.loads(p.read_text())) for p in old}&{l['D4_geometry_signature'] for l in rows}
    m=json.loads((ROOT/'reports/phase3_7/generation_manifest.json').read_text())
    assert m['attempted']==m['verified']==24 and m['failed']==m['automatic_replacements']==0


@pytest.mark.parametrize('index',range(24))
def test_three_resolutions_certificates_and_clear_witnesses(index):
    l=labels()[index];s=json.loads((ROOT/f"diagnostics/phase3_7/private/scenes/{l['sample_id']}.json").read_text())
    validate_scene(s);model=CollisionModel.from_scene(s)
    assert [g['resolution_m'] for g in l['grids']]==[.1,.05,.025]
    assert all(g['passable'] is l['passable'] for g in l['grids'])
    if l['passable']:
        assert l['reference_path_min_clearance_m']>=.5
        assert all(model.segment_free(a,b) for a,b in zip(l['reference_path'],l['reference_path'][1:]))
        for g in l['grids']:assert all(model.segment_free(a,b) for a,b in zip(g['path'],g['path'][1:]))
        assert model.segment_free(s['start'],s['goal']) is (l['category']=='A')
    else:
        assert not l['negative_certificate']['raw_components']['same_component']
        if l['category']=='D':assert l['negative_certificate']['goal_enclosed_holes']


def test_public_inputs_and_identical_prompts():
    assert len(load_inputs(ROOT,'new24'))==24 and len(load_inputs(ROOT,'old16'))==16
    assert (ROOT/'diagnostics/phase3_7/inputs/old16.jsonl').read_bytes()==(ROOT/'diagnostics/phase3_6/inputs/public_inputs.jsonl').read_bytes()
    assert (ROOT/'prompts/phase3_7/poststate_reach_en_v1.txt').read_bytes()==(ROOT/'prompts/poststate_reach_en_v1.txt').read_bytes()
    old=yaml.safe_load((ROOT/'configs/phase3_6.yaml').read_text())
    for key in ['dtype','device','attention','seed','batch_size','max_new_tokens','do_sample','use_model_defaults','temperature','top_p','top_k','num_beams','min_pixels','max_pixels']:assert old[key]==CFG[key]


def synthetic(tmp_path,kind):
    im=Image.new('RGB',(600,600),'white');d=ImageDraw.Draw(im)
    d.rectangle((40,40,560,560),fill='#F3F5F8',outline='#182332',width=2)
    if kind=='barrier':d.rectangle((290,40,310,560),fill='#445060')
    elif kind=='detour':d.rectangle((250,230,350,370),fill='#DD9350')
    elif kind=='closed':
        d.rectangle((450,220,550,380),fill='#445060');d.rectangle((470,240,530,360),fill='#F3F5F8')
    for x,color in [(100,'#2475C4'),(500,'#16805B')]:d.ellipse((x-13,287,x+13,313),fill=color,outline='white',width=2)
    p=tmp_path/f'{kind}.png';im.save(p);return p


@pytest.mark.parametrize('kind,answer',[('open',True),('detour',True),('barrier',False),('closed',False)])
def test_rgb_only_pipeline_on_unscored_synthetic_maps(tmp_path,kind,answer):
    grid=extract(synthetic(tmp_path,kind),{'workspace_dimensions_m':[10,10],'robot_radius_m':.25})
    assert grid['frame_px']==[40,40,560,560] and grid['scale']==52
    answers=[search(grid,a) for a in ['bfs','astar']]
    assert all(r['passable'] is answer for r in answers)
    assert all(r['end_to_end_seconds']>=r['search_seconds'] for r in answers)
    for result in answers:
        if answer:
            from spatial_pilot.scale_rgb import segment_safe
            assert all(segment_safe(grid['safe'],a,b) for a,b in zip(result['path_pixels'],result['path_pixels'][1:]))


def test_disk_contact_and_diagonal_distance():
    m=np.zeros((9,9),dtype=bool);m[4,4]=True
    d=dilate_disk(m,1)
    assert d.sum()==5 and d[4,5] and not d[5,5]
    assert dilate_disk(m,2)[4,6]


def test_extraction_failure_never_falls_back_to_oracle(tmp_path):
    p=tmp_path/'blank.png';Image.new('RGB',(768,768),'white').save(p)
    with pytest.raises(ExtractionFailure):extract(p,{'workspace_dimensions_m':[12,12],'robot_radius_m':.25})


@pytest.mark.parametrize('path',['diagnostics/phase3_7/private/new24_labels.jsonl','reports/phase3_6/metrics.json',
                               'data/public_inputs.jsonl','outputs/phase3_6/predictions.jsonl'])
def test_public_inference_firewall(path):
    code=f"from pathlib import Path;from spatial_pilot.scale_io import firewall;r=Path({str(ROOT)!r});firewall(r);(r/{path!r}).read_bytes()"
    result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
    assert result.returncode and 'PermissionError' in result.stderr


def test_historical_files_untouched():
    saved=json.loads((ROOT/'reports/phase3_7/preserved_before.json').read_text())
    assert len(saved['files'])==463 and all(digest(ROOT/n)==h for n,h in saved['files'].items())


def test_planner_has_no_private_geometry_imports():
    import ast
    source=(ROOT/'src/spatial_pilot/scale_rgb.py').read_text();tree=ast.parse(source)
    names=[n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
    assert not any(name and any(word in name for word in ['oracle','scenes','geometry','shapely']) for name in names)


def test_generator_refuses_overwrite():
    from spatial_pilot.scale_scenes import build
    with pytest.raises(FileExistsError):build(ROOT)


def test_scoring_and_paired_changes_keep_unknown_denominator():
    from spatial_pilot.scale_evaluate import metrics,paired
    truth={str(i):{'passable':i<4,'category':'ABCD'[i//2],'layout_description':'synthetic'} for i in range(8)}
    a=[{'query_id':str(i),'prediction':False,'end_to_end_seconds':1} for i in range(8)]
    m,cases=metrics(a,truth)
    assert (m['TP'],m['FP'],m['TN'],m['FN'])==(0,0,4,4) and m['accuracy']==.5
    b=[dict(r) for r in a];b[0]['prediction']=True;b[7]['prediction']=None
    n,other=metrics(b,truth)
    assert n['unknown']==1 and n['correct']==4 and n['total']==8
    p=paired(cases,other)
    assert p['4b_wrong_8b_right']==1 and p['4b_right_8b_wrong']==1
    assert n['unreachable_recognition_rate']==.75
