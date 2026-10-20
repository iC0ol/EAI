"""Boundary and failure tests; no GPU/model/real oracle labels are needed."""
import json
from pathlib import Path
import subprocess
import sys
import pytest
import yaml
from spatial_pilot.vlm_io import build_prompt, load_public_records, parse_response
from spatial_pilot.evaluate import evaluate_rows

ROOT = Path(__file__).resolve().parents[1]


def valid_response():
    return {'F_A':True,'F_B':False,'F_AB':None,
            'explanation':{'A':'A reason','B':'B reason','AB':'insufficient evidence'}}


def test_exact_json_and_uncertainty_preserved():
    original = valid_response()
    result = parse_response(json.dumps(original))
    assert result['parse_ok'] and result['parsed_output']==original
    assert result['parsed_output']['F_AB'] is None


@pytest.mark.parametrize('raw',[
    '```json\n'+json.dumps(valid_response())+'\n```',
    json.dumps(dict(valid_response(),F_A=1)),
    json.dumps(dict(valid_response(),F_A='true')),
    json.dumps(dict(valid_response(),extra='x')),
    '{"F_A":true,"F_A":false,"F_B":false,"F_AB":true,"explanation":{"A":"a","B":"b","AB":"c"}}',
    '{"F_A":NaN,"F_B":false,"F_AB":true,"explanation":{"A":"a","B":"b","AB":"c"}}',
])
def test_malformed_output_never_repaired(raw):
    result = parse_response(raw)
    assert not result['parse_ok'] and result['parsed_output'] is None and result['parse_error']


def test_prompt_allowlist_excludes_ids_and_injected_private_fields():
    record = json.loads((ROOT/'data/public_inputs.jsonl').read_text().splitlines()[0])
    record.update({'family':'SECRET_FAMILY','oracle_path':'SECRET_PATH','private_labels':'SECRET_LABEL'})
    text = build_prompt(record,'Fixed prompt {{PUBLIC_TASK_JSON}}')
    assert all(word not in text for word in ['SECRET_FAMILY','SECRET_PATH','SECRET_LABEL',record['sample_id']])


def test_public_reader_rejects_path_escape_and_hash_tamper(tmp_path):
    (tmp_path/'data/images').mkdir(parents=True)
    real = json.loads((ROOT/'data/public_inputs.jsonl').read_text().splitlines()[0])
    config = {'public_inputs':'data/public_inputs.jsonl','image_root':'data/images'}
    public = tmp_path/'data/public_inputs.jsonl'
    real['image'] = '../private.png'
    public.write_text(json.dumps(real)+'\n')
    with pytest.raises(ValueError,match='escapes'):
        load_public_records(tmp_path,config)
    real['image'] = 'images/public.png'
    (tmp_path/'data/images/public.png').write_bytes(b'tampered')
    public.write_text(json.dumps(real)+'\n')
    with pytest.raises(ValueError,match='hash mismatch'):
        load_public_records(tmp_path,config)


def test_audit_guard_denies_private_data_and_qc_reads(tmp_path):
    script = '''
from pathlib import Path
from spatial_pilot.vlm_io import inference_read_guard
import sys
root=Path(sys.argv[1]); (root/'data').mkdir(); (root/'reports').mkdir()
for path in [root/'data/private_labels.jsonl',root/'reports/qc.png']:
    path.write_text('hidden')
inference_read_guard(root)
for path in [root/'data/private_labels.jsonl',root/'reports/qc.png']:
    try: path.read_text()
    except PermissionError: pass
    else: raise AssertionError('Private read allowed')
'''
    result = subprocess.run([sys.executable,'-c',script,str(tmp_path)],capture_output=True,text=True)
    assert result.returncode == 0,result.stderr


def test_evaluation_keeps_failed_and_unknown_in_denominator():
    truths = [{'sample_id':sid,'status':'verified','family':'synthetic',
               'labels':{'F_A':True,'F_B':False,'F_AB':True}} for sid in ['x','y']]
    predictions = [{'sample_id':'x','status':'ok','parse_ok':True,'parsed_output':valid_response()},
                   {'sample_id':'y','status':'parse_error','parse_ok':False,'parsed_output':None}]
    result = evaluate_rows(predictions,truths,['x','y'])
    assert result['per_state']['F_A']['correct'] == 1
    assert result['per_state']['F_A']['denominator'] == 2
    assert result['per_state']['F_AB']['unknown'] == 2
    assert result['full_combination_correct'] == 0 and result['parse_failures'] == 1


def test_evaluation_rejects_duplicate_or_missing_samples():
    with pytest.raises(ValueError,match='exactly one'):
        evaluate_rows([{'sample_id':'x'},{'sample_id':'x'}],[],['x','y'])
