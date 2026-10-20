from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
from spatial_pilot.make_dataset import public_record
from spatial_pilot.render import center, png_bytes, public_text, render_private, render_public
from spatial_pilot.scenes import FAMILIES, all_scenes, build_scene


def test_fixed_seed_scene_and_render_are_reproducible(config):
    first = all_scenes(config)
    second = all_scenes(config)
    assert first == second
    for a,b in zip(first,second):
        assert png_bytes(render_public(a)) == png_bytes(render_public(b))


def test_seed_is_recorded_and_affects_sample_identity(config):
    other = dict(config,seed=config['seed']+1)
    assert build_scene('serial',0,config)['sample_id'] != build_scene('serial',0,other)['sample_id']


def test_public_inputs_have_no_private_labels_or_family(config):
    forbidden = ['family', 'F_A', 'F_B', 'F_AB', 'oracle', 'passable', 'verified', 'serial', 'parallel', 'side_effect']
    for scene in all_scenes(config):
        record = public_record(scene,'a'*64)
        encoded = json.dumps(record)
        assert all(term not in encoded for term in forbidden)
        assert 'scene.json' not in encoded
        assert len(record['candidate_edits']) == 2


def test_public_images_ignore_answers_paths_ids_and_file_labels(config,verified):
    for family in FAMILIES:
        scene,label = verified(family,0)
        public = render_public(scene)
        altered = deepcopy(scene)
        altered.update({'sample_id':'secret_filename_serial_F_A_1','family':'SECRET ANSWER',
                        'labels':label['labels'],'oracle_path':[[0,0],[12,12]],
                        'post_edit_objects':label['states']['AB']['final_objects']})
        assert png_bytes(public) == png_bytes(render_public(altered))
        assert public.size == (768,768) and public.mode == 'RGB'
        assert public.info == {}
        text = ' '.join(public_text(scene))
        assert scene['sample_id'] not in text and family not in text
        assert all(token not in text.lower() for token in ['oracle','f_a','answer','passable'])


def test_proposed_and_actual_new_obstacle_are_drawn(config,verified):
    scene,label = verified('side_effect',0)
    btarget = scene['edits']['B']['target_geometry']
    # Pixel center of B's new final pose must have its actual solid fill in private B view.
    image = render_private(scene,'B',label['states']['B']['fine'])
    cx,cy = center(btarget)
    px = round(72+cx/12*624+8)  # avoid the overlaid letter
    py = round(44+(12-cy)/12*624+12)
    from PIL import ImageColor
    obj = next(o for o in scene['objects'] if o['display_id']=='B')
    assert image.getpixel((px,py)) == ImageColor.getrgb(obj['color'])
    assert "B'" in public_text(scene)


def test_generation_failure_is_counted_and_preserved(config,tmp_path,monkeypatch):
    from spatial_pilot import make_dataset
    def fail(*args):
        raise RuntimeError('deliberate failure for audit test')
    monkeypatch.setattr(make_dataset,'build_scene',fail)
    with pytest.raises(RuntimeError,match='12 of 12'):
        make_dataset.generate(config,tmp_path)
    manifest = json.loads((tmp_path/'reports/generation_manifest.json').read_text())
    failures = (tmp_path/'reports/generation_failures.jsonl').read_text().splitlines()
    assert manifest['attempted'] == manifest['failed'] == len(failures) == 12
    assert manifest['succeeded'] == 0
    assert all('traceback' in json.loads(line) for line in failures)


def test_serialized_artifacts_roundtrip_and_hashes(config,verified):
    # Validate the actual delivery once it exists, without using it to compute expected truth.
    root = Path(__file__).resolve().parents[1]
    path = root/'data/public_inputs.jsonl'
    if not path.exists():
        pytest.skip('Delivery generated only after the six core geometry tests')
    public = [json.loads(line) for line in path.read_text().splitlines()]
    private = [json.loads(line) for line in (root/'data/private_labels.jsonl').read_text().splitlines()]
    assert len(public) == len(private) == 12
    assert {p['sample_id'] for p in public} == {p['sample_id'] for p in private}
    from spatial_pilot.edits import apply_edits
    from spatial_pilot.scenes import STATES
    for p,l in zip(public,private):
        original = (root/'data'/p['image']).read_bytes()
        assert hashlib.sha256(original).hexdigest() == p['input_image_sha256']
        saved = json.loads((root/f'data/scenes/{p["sample_id"]}/scene.json').read_text())
        scene,label = verified(l['family'],saved['variant'])
        assert l == label
        assert original == png_bytes(render_public(saved))
        for state in STATES:
            assert saved['post_edit_objects'][state] == apply_edits(saved,STATES[state])['objects']
