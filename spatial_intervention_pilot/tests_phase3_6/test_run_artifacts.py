"""Post-run evidence checks; run only after all official inference has finished."""
import json
from pathlib import Path

from spatial_pilot.control_io import parse_response, verify_frozen
from spatial_pilot.vlm_io import sha256

ROOT = Path(__file__).resolve().parents[1]


def records():
    return [json.loads(line) for line in (ROOT/'outputs/phase3_6/predictions.jsonl').read_text().splitlines()]


def test_one_completed_call_per_frozen_sample():
    session = json.loads((ROOT/'outputs/phase3_6/session.json').read_text())
    order = json.loads((ROOT/'diagnostics/phase3_6/inputs/order.json').read_text())
    rows = records()
    assert session['status'] == 'completed' and session['completed_queries'] == 16
    assert [r['query_id'] for r in rows] == order and len(set(order)) == 16
    assert all(r['status'] in ['ok', 'parse_error'] for r in rows)
    verify_frozen(ROOT)


def test_real_vision_and_greedy_configuration():
    session = json.loads((ROOT/'outputs/phase3_6/session.json').read_text())
    assert session['effective_generation_config']['do_sample'] is False
    assert session['effective_generation_config']['num_beams'] == 1
    assert session['explicit_generate_kwargs']['use_model_defaults'] is False
    for row in records():
        assert row['vision_forward_calls'] == 1 and row['image_token_count'] > 0
        assert row['decoding_config']['do_sample'] is False
        assert not row['hit_token_limit']
        assert row['peak_allocated_mib'] > 0 and row['inference_seconds'] > 0


def test_exact_prompt_and_raw_parse_evidence():
    template = (ROOT/'prompts/phase3_6/poststate_reach_en_v1.txt').read_text()
    public = {r['query_id']: r for r in map(json.loads, (ROOT/'diagnostics/phase3_6/inputs/public_inputs.jsonl').read_text().splitlines())}
    for row in records():
        qid = row['query_id']
        evidence = json.loads((ROOT/f'outputs/phase3_6/{qid}_input.json').read_text())
        assert evidence['prompt_text'] == template.replace('{{CONTEXT_JSON}}', json.dumps(public[qid]['context'], sort_keys=True))
        assert qid not in evidence['prompt_text']
        assert evidence['input_image_sha256'] == sha256(ROOT/public[qid]['image'])
        assert evidence['pixel_values_shape'] and evidence['image_grid_thw']
        assert (ROOT/f'outputs/phase3_6/{qid}_response.txt').read_text() == row['response_text']
        parsed = parse_response(row['response_text'], 'poststate')
        assert all(row[key] == value for key, value in parsed.items())


def test_actual_read_events_exclude_private_and_history():
    session = json.loads((ROOT/'outputs/phase3_6/session.json').read_text())
    events = session['data_read_events']
    assert len([p for p in events if p.endswith('.png')]) == 16
    assert all(p.startswith(('diagnostics/phase3_6/inputs/', 'diagnostics/phase3_6/images/')) for p in events)


def test_independent_evaluation_after_completion():
    metrics = json.loads((ROOT/'reports/phase3_6/metrics.json').read_text())
    assert metrics['total'] == 16 and metrics['evaluation']['separate_cpu_process']
    from datetime import datetime
    assert datetime.fromisoformat(metrics['evaluation']['labels_opened_at']) > datetime.fromisoformat(metrics['evaluation']['inference_finished_at'])
    cases = [json.loads(line) for line in (ROOT/'reports/phase3_6/cases.jsonl').read_text().splitlines()]
    assert metrics['correct'] == sum(c['correct'] for c in cases)
    assert metrics['always_reachable_baseline']['correct'] == metrics['always_unreachable_baseline']['correct'] == 8
