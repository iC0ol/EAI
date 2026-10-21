"""Separate CPU post-inference evaluation. Never imported by model inference."""
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics

from .control_io import verify_frozen
from .vlm_io import sha256

ROOT = Path(__file__).resolve().parents[2]


def score(predictions, labels):
    by_id = {r['query_id']: r for r in predictions}
    if len(by_id) != len(predictions) or set(by_id) != {r['sample_id'] for r in labels}:
        raise ValueError('Duplicate/missing/extra predictions')
    cases = []
    for label in labels:
        row = by_id[label['sample_id']]
        pred = row['parsed_output']['passable'] if row['parse_ok'] else None
        if type(pred) not in [bool, type(None)]:
            raise ValueError('Prediction not boolean/null')
        cases.append({'sample_id': label['sample_id'], 'category': label['category'],
                      'layout_description': label.get('layout_description'), 'truth': label['passable'],
                      'prediction': pred, 'correct': pred is label['passable'], 'parse_ok': row['parse_ok'],
                      'parse_error': row.get('parse_error'), 'explanation': (row.get('parsed_output') or {}).get('explanation'),
                      'response_text': row['response_text'], 'inference_seconds': row.get('inference_seconds'),
                      'reference_path_min_clearance_m': label.get('reference_path_min_clearance_m'),
                      'straight_segment_free': label.get('straight_segment_free')})
    n = len(cases)
    confusion = {truth: {pred: sum(c['truth'] is (truth == 'reachable') and
                                  (('unknown' if c['prediction'] is None else 'reachable' if c['prediction'] else 'unreachable') == pred)
                                  for c in cases) for pred in ['reachable', 'unreachable', 'unknown']}
                 for truth in ['reachable', 'unreachable']}
    categories = {cat: {'correct': sum(c['correct'] for c in cases if c['category'] == cat),
                        'total': sum(c['category'] == cat for c in cases)} for cat in 'ABCD'}
    metrics = {'total': n, 'correct': sum(c['correct'] for c in cases), 'accuracy': sum(c['correct'] for c in cases)/n,
               'categories': categories, 'confusion_matrix_truth_rows_prediction_columns': confusion,
               'parse_success': sum(c['parse_ok'] for c in cases), 'parse_success_rate': sum(c['parse_ok'] for c in cases)/n,
               'prediction_reachable': sum(c['prediction'] is True for c in cases),
               'prediction_unreachable': sum(c['prediction'] is False for c in cases),
               'prediction_unknown': sum(c['prediction'] is None for c in cases),
               'constant_unreachable': all(c['prediction'] is False for c in cases),
               'all_obvious_straight_recognized': categories['A']['correct'] == categories['A']['total'],
               'always_reachable_baseline': {'correct': sum(c['truth'] for c in cases), 'total': n},
               'always_unreachable_baseline': {'correct': sum(not c['truth'] for c in cases), 'total': n},
               'unknown_and_parse_errors_kept_in_denominator': True}
    return metrics, cases


def main(root=ROOT):
    root = Path(root); out = root/'outputs/phase3_6'; report = root/'reports/phase3_6'
    session = json.loads((out/'session.json').read_text())
    if session['status'] != 'completed' or session['completed_queries'] != 16:
        raise ValueError('All 16 inferences must finish before private labels may be opened')
    # Validate freezes before opening any truth. This process never executes the model.
    verify_frozen(root)
    frozen = json.loads((report/'frozen_run.json').read_text())
    for name, h in frozen['private_files'].items():
        if sha256(root/name) != h:
            raise ValueError(f'Private oracle/source freeze changed: {name}')
    rows = [json.loads(line) for line in (out/'predictions.jsonl').read_text().splitlines()]
    expected_order = json.loads((root/'diagnostics/phase3_6/inputs/order.json').read_text())
    if [r['query_id'] for r in rows] != expected_order:
        raise ValueError('Predictions differ from frozen order or contain duplicate calls')
    labels_opened_at = datetime.now(timezone.utc).isoformat()
    labels = [json.loads(line) for line in (root/'diagnostics/phase3_6/private/private_labels.jsonl').read_text().splitlines()]
    metrics, cases = score(rows, labels)
    metrics['timing'] = {'total_inference_seconds': sum(r['inference_seconds'] for r in rows),
                         'mean_inference_seconds': statistics.mean(r['inference_seconds'] for r in rows),
                         'min_inference_seconds': min(r['inference_seconds'] for r in rows),
                         'max_inference_seconds': max(r['inference_seconds'] for r in rows),
                         'model_load_seconds': session['model_load_seconds']}
    metrics['memory'] = {k: max(r[k] for r in rows) for k in ['peak_allocated_mib', 'peak_reserved_mib', 'nvidia_peak_device_used_mib']}
    metrics['vision_forward_calls'] = sum(r['vision_forward_calls'] for r in rows)
    metrics['token_limit_hits'] = sum(r['hit_token_limit'] for r in rows)
    metrics['evaluation'] = {'labels_opened_at': labels_opened_at, 'inference_finished_at': session['finished_at'],
                             'separate_cpu_process': True, 'session_sha256': sha256(out/'session.json'),
                             'predictions_sha256': sha256(out/'predictions.jsonl')}
    # Write new reports only, reject accidental reevaluation overwrites.
    with (report/'metrics.json').open('x') as f:
        json.dump(metrics, f, indent=2); f.write('\n')
    for name, selected in [('cases.jsonl', cases), ('error_cases.jsonl', [c for c in cases if not c['correct']])]:
        with (report/name).open('x') as f:
            for case in selected:
                f.write(json.dumps(case, ensure_ascii=False)+'\n')
    print(json.dumps(metrics, indent=2))


if __name__ == '__main__':
    main()
