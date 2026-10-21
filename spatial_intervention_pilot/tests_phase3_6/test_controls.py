"""Dedicated control audit, including safety boundary and scoring counterexamples."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image
import pytest
import yaml

from spatial_pilot.control_evaluate import score
from spatial_pilot.control_io import load_inputs, parse_response
from spatial_pilot.control_scenes import candidates, component_evidence, signature
from spatial_pilot.diagnostic_data import render_poststate
from spatial_pilot.geometry import CollisionModel
from spatial_pilot.vlm_io import sha256

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT/'configs/phase3_6.yaml').read_text())


def labels():
    return [json.loads(line) for line in (ROOT/'diagnostics/phase3_6/private/private_labels.jsonl').read_text().splitlines()]


def test_generation_complete_no_hidden_replacement():
    m = json.loads((ROOT/'reports/phase3_6/generation_manifest.json').read_text())
    assert (m['status'], m['attempted'], m['verified'], m['failed'], m['automatic_replacements']) == ('completed', 16, 16, 0, 0)
    attempts = [json.loads(line) for line in (ROOT/'diagnostics/phase3_6/private/generation_attempts.jsonl').read_text().splitlines()]
    assert len(attempts) == 16 and all(a['status'] == 'verified' for a in attempts)


def test_balance_and_unique_constructions():
    values = labels()
    assert len(values) == 16 and sum(l['passable'] for l in values) == 8
    assert {k: sum(l['category'] == k for l in values) for k in 'ABCD'} == dict.fromkeys('ABCD', 4)
    assert len({l['layout_description'] for l in values}) == 16
    signatures = {l['D4_geometry_signature'] for l in values}
    assert len(signatures) == 16
    old = {signature(json.loads(p.read_text())) for p in (ROOT/'data/scenes').glob('*/scene.json')}
    assert not (signatures & old)


@pytest.mark.parametrize('index', range(16))
def test_geometry_witnesses_components_and_grid_agreement(index):
    value = labels()[index]
    scene, info = candidates(CFG['geometry'])[index]
    saved = json.loads((ROOT/f"diagnostics/phase3_6/private/scenes/{scene['sample_id']}.json").read_text())
    assert scene == saved and value['category'] == info['category']
    assert [g['resolution_m'] for g in value['grids']] == [.1, .05, .025]
    assert all(g['passable'] is value['passable'] for g in value['grids'])
    model = CollisionModel.from_scene(scene)
    assert component_evidence(scene, True)['same_component'] is value['passable']
    for grid in value['grids']:
        if grid['passable']:
            assert grid['path'][0] == scene['start'] and grid['path'][-1] == scene['goal']
            assert all(model.segment_free(a, b) for a, b in zip(grid['path'], grid['path'][1:]))
        else:
            assert grid['status'] == 'unreachable_on_grid' and not grid['continuous_unreachability_claimed']
    if value['category'] in 'AB':
        assert value['reference_path_min_clearance_m'] >= .5
        assert model.path_clearance(value['reference_path']) == value['reference_path_min_clearance_m']
        assert all(model.segment_free(a, b) for a, b in zip(value['reference_path'], value['reference_path'][1:]))
        assert model.segment_free(scene['start'], scene['goal']) is (value['category'] == 'A')
    else:
        assert not component_evidence(scene, False)['same_component']
        assert value['negative_certificate']
        if value['category'] == 'D':
            assert value['negative_certificate']['goal_enclosed_holes'] >= 1


def test_input_images_exact_clean_renderer_and_neutral_context():
    rows = load_inputs(ROOT)
    assert len(rows) == 16
    mapping = {s['sample_id']: s for s, _ in candidates(CFG['geometry'])}
    for row, path in rows:
        with Image.open(path) as im:
            assert im.size == (768, 768) and not im.info
            assert im.tobytes() == render_poststate(mapping[row['query_id']]).tobytes()
        assert set(row['context']) == {'units', 'workspace_dimensions_m', 'robot_radius_m'}
        assert row['query_id'] not in json.dumps(row['context'])


def test_prompt_and_model_parameters_unchanged():
    old = yaml.safe_load((ROOT/'configs/phase3_5.yaml').read_text())
    for key in ['model_id', 'model_revision', 'model_local_dir', 'dtype', 'device', 'attention', 'seed',
                'batch_size', 'max_new_tokens', 'do_sample', 'use_model_defaults', 'temperature',
                'top_p', 'top_k', 'num_beams', 'min_pixels', 'max_pixels']:
        assert CFG[key] == old[key]
    assert sha256(ROOT/CFG['prompts']['poststate']['path']) == sha256(ROOT/old['prompts']['poststate']['path'])


@pytest.mark.parametrize('raw', ['{"passable":"false","explanation":"x"}', '{"passable":0,"explanation":"x"}',
                                     '```json\n{"passable":false,"explanation":"x"}\n```',
                                     '{"passable":false,"passable":true,"explanation":"x"}',
                                     '{"passable":NaN,"explanation":"x"}'])
def test_no_format_repair(raw):
    assert not parse_response(raw, 'poststate')['parse_ok']


def test_scoring_balanced_constant_predictions_and_unknowns():
    truth = [{'sample_id': str(i), 'category': 'ABCD'[i//4], 'passable': i < 8} for i in range(16)]
    pred = [{'query_id': str(i), 'parse_ok': True, 'parsed_output': {'passable': False, 'explanation': 'x'},
             'response_text': '{}'} for i in range(16)]
    m, cases = score(pred, truth)
    assert m['correct'] == 8 and m['constant_unreachable'] and m['parse_success_rate'] == 1
    assert m['confusion_matrix_truth_rows_prediction_columns']['reachable']['unreachable'] == 8
    assert m['confusion_matrix_truth_rows_prediction_columns']['unreachable']['unreachable'] == 8
    assert m['always_reachable_baseline']['correct'] == m['always_unreachable_baseline']['correct'] == 8
    pred[8].update(parse_ok=False, parsed_output=None, parse_error='broken')
    m, _ = score(pred, truth)
    assert m['total'] == 16 and m['correct'] == 7 and m['prediction_unknown'] == 1
    with pytest.raises(ValueError):
        score(pred+pred[:1], truth)


@pytest.mark.parametrize('relative', ['diagnostics/phase3_6/private/private_labels.jsonl', 'data/public_inputs.jsonl',
                                     'reports/phase3_5/phase3_5_diagnostic.md', 'outputs/phase3/core/predictions.jsonl',
                                     'reports/phase3_6/scene_overview.png'])
def test_model_firewall_denies_private_and_history(relative):
    code = ('from pathlib import Path; from spatial_pilot.control_io import read_firewall; '
            f'r=Path({str(ROOT)!r}); read_firewall(r); (r/{relative!r}).read_bytes()')
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    assert result.returncode != 0 and 'PermissionError' in result.stderr


def test_generation_refuses_overwrite():
    from spatial_pilot.control_scenes import build
    with pytest.raises(FileExistsError):
        build(ROOT)


def test_baselines_byte_identical():
    before = json.loads((ROOT/'reports/phase3_6/preserved_before.json').read_text())
    assert all(sha256(ROOT/name) == h for name, h in before['files'].items())
