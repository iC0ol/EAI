"""Final evidence audit. Execute only after Part A/B inference and evaluation."""
from datetime import datetime
import json
from pathlib import Path
from spatial_pilot.scale_io import digest,parse_response,verify_frozen

ROOT=Path(__file__).resolve().parents[1]


def rows(name):return list(map(json.loads,(ROOT/f'outputs/phase3_7/{name}/predictions.jsonl').read_text().splitlines()))


def test_exactly_once_formal_runs_and_real_visual_encoding():
    frozen=verify_frozen(ROOT)
    for name,datasets,count in [('vlm8b_a',['old16','new24'],40),('vlm4b_new',['new24'],24)]:
        session=json.loads((ROOT/f'outputs/phase3_7/{name}/session.json').read_text())
        records=rows(name)
        assert session['status']=='completed' and session['completed_queries']==count
        assert [r['query_id'] for r in records]==sum([frozen['order'][d] for d in datasets],[])
        assert len({r['query_id'] for r in records})==count
        assert session['actual_parameter_dtypes']==['torch.bfloat16'] and session['quantization'] is None
        assert session['effective_generation_config']['do_sample'] is False and session['explicit_generate_kwargs']['use_model_defaults'] is False
        assert all(r['vision_forward_calls']==1 and r['image_token_count']>0 for r in records)


def test_exact_neutral_prompts_and_raw_answer_parses():
    template=(ROOT/'prompts/phase3_7/poststate_reach_en_v1.txt').read_text()
    for name in ['vlm8b_a','vlm4b_new']:
        for r in rows(name):
            evidence=json.loads((ROOT/f"outputs/phase3_7/{name}/{r['query_id']}_input.json").read_text())
            context={'units':'m','workspace_dimensions_m':[12,12],'robot_radius_m':.25}
            assert evidence['prompt_text']==template.replace('{{CONTEXT_JSON}}',json.dumps(context,sort_keys=True))
            assert r['query_id'] not in evidence['prompt_text']
            parsed=parse_response(r['response_text'],'poststate')
            assert all(r[k]==v for k,v in parsed.items())
            assert (ROOT/f"outputs/phase3_7/{name}/{r['query_id']}_response.txt").read_text()==r['response_text']


def test_actual_read_events_only_public_current_inputs():
    for name in ['vlm8b_a','vlm4b_new','rgb']:
        s=json.loads((ROOT/f'outputs/phase3_7/{name}/session.json').read_text())
        assert s['data_read_events']
        assert all(p.startswith(('diagnostics/phase3_7/inputs/','diagnostics/phase3_7/images/','diagnostics/phase3_7/smoke/','diagnostics/phase3_6/images/')) for p in s['data_read_events'])


def test_rgb_and_astar_share_graph_and_reachability():
    records=rows('rgb');assert len(records)==80
    pairs={}
    for r in records:pairs.setdefault(r['query_id'],{})[r['algorithm']]=r
    assert len(pairs)==40
    for pair in pairs.values():
        assert set(pair)=={'bfs','astar'}
        assert pair['bfs']['passable'] is pair['astar']['passable']
        assert pair['bfs']['image_sha256']==pair['astar']['image_sha256']
        assert pair['bfs']['extraction_seconds']==pair['astar']['extraction_seconds']
        for r in pair.values():
            if r['search_seconds'] is not None:assert abs(r['end_to_end_seconds']-r['extraction_seconds']-r['search_seconds'])<1e-8


def test_evaluation_after_both_models_and_rgb_complete():
    m=json.loads((ROOT/'reports/phase3_7/part_a_b_metrics.json').read_text())
    opened=datetime.fromisoformat(m['evaluated_at'])
    for name in ['vlm8b_a','vlm4b_new','rgb']:
        session=json.loads((ROOT/f'outputs/phase3_7/{name}/session.json').read_text())
        assert opened>datetime.fromisoformat(session['finished_at'])
    assert m['private_labels_opened_after_all_inference']


def test_private_freeze_and_old4b_unchanged():
    frozen=json.loads((ROOT/'reports/phase3_7/frozen_run.json').read_text())
    assert all(digest(ROOT/n)==h for n,h in frozen['private_files'].items())
    assert digest(ROOT/'outputs/phase3_6/predictions.jsonl')==frozen['private_files']['outputs/phase3_6/predictions.jsonl']


def test_all_predicted_rgb_paths_checked_afterward_without_repair():
    audits=json.loads((ROOT/'reports/phase3_7/posthoc_segmentation_path_audit.json').read_text())
    assert len(audits)==40 and all(a['post_inference_only'] for a in audits)
    for a in audits:
        for method in ['bfs','astar']:
            if a[method]['predicted_passable']:assert 'path_collision_free_in_private_geometry' in a[method]
