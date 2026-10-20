"""Independent post-inference evaluation. Never imported by the model runner."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path

KEYS = ('F_A','F_B','F_AB')


def evaluate_rows(predictions,truths,expected_ids):
    ids = [row['sample_id'] for row in predictions]
    if len(ids) != len(set(ids)) or set(ids) != set(expected_ids):
        raise ValueError('Expected exactly one prediction for each planned sample')
    ground = {row['sample_id']:row for row in truths}
    metrics = {key:{'correct':0,'denominator':len(ids),'unknown':0} for key in KEYS}
    cases = []
    for row in predictions:
        sid = row['sample_id']
        truth = ground[sid]
        if truth['status'] != 'verified' or any(type(truth['labels'][key]) is not bool for key in KEYS):
            raise ValueError('Oracle unresolved/invalid truth cannot enter smoke evaluation')
        parsed = row.get('parsed_output') if row.get('parse_ok') and row.get('status')=='ok' else None
        values = {key:parsed.get(key) if parsed else None for key in KEYS}
        matches = {}
        for key in KEYS:
            matches[key] = type(values[key]) is bool and values[key] == truth['labels'][key]
            metrics[key]['correct'] += int(matches[key])
            metrics[key]['unknown'] += int(values[key] is None)
        cases.append({'sample_id':sid,'family':truth['family'],'prediction':values,
                      'truth':{key:truth['labels'][key] for key in KEYS},'correct':matches,
                      'full_combination_correct':all(matches.values()),
                      'both_singles_correct_ab_wrong':matches['F_A'] and matches['F_B'] and not matches['F_AB'],
                      'parse_ok':row.get('parse_ok',False),'status':row.get('status'),
                      'response_text':row.get('response_text'),'parsed_output':row.get('parsed_output'),
                      'parse_error':row.get('parse_error'),'inference_seconds':row.get('inference_seconds'),
                      'peak_vram_mb':row.get('peak_vram_mb'),
                      'nvidia_peak_device_used_mib':row.get('nvidia_peak_device_used_mib')})
    for value in metrics.values():
        value['accuracy'] = value['correct']/value['denominator']
    return {'n_samples':len(ids),'per_state':metrics,
            'all_state_decisions_correct':sum(sum(case['correct'].values()) for case in cases),
            'all_state_decisions_denominator':len(ids)*3,
            'full_combination_correct':sum(case['full_combination_correct'] for case in cases),
            'full_combination_denominator':len(ids),
            'both_singles_correct_ab_wrong_count':sum(case['both_singles_correct_ab_wrong'] for case in cases),
            'parse_failures':sum(not case['parse_ok'] for case in cases),'cases':cases,
            'interpretation':'Six selected smoke samples only; no statistical significance or H1/H2 research conclusion.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run',type=Path,default=Path('outputs/phase3/core'))
    parser.add_argument('--output',type=Path,default=Path('reports/phase3'))
    args = parser.parse_args()
    session = json.loads((args.run/'session.json').read_text())
    if session['status'] != 'completed' or session['stage'] != 'core':
        raise ValueError('Read truth only after six-core inference completed')
    prediction_path = args.run/'predictions.jsonl'
    predictions = [json.loads(line) for line in prediction_path.read_text().splitlines()]
    if len(predictions) != len(session['sample_ids']):
        raise ValueError('Incomplete inference; truth remains unread')
    # This is the first and only private-label read in the evaluation pipeline.
    truth_path = Path('data/private_labels.jsonl')
    truths = [json.loads(line) for line in truth_path.read_text().splitlines()]
    result = evaluate_rows(predictions,truths,session['sample_ids'])
    result.update({'evaluated_at':datetime.now().astimezone().isoformat(),
                   'predictions_sha256':hashlib.sha256(prediction_path.read_bytes()).hexdigest(),
                   'truth_sha256':hashlib.sha256(truth_path.read_bytes()).hexdigest(),
                   'model_id':session['model_id'],'model_revision':session['model_revision'],
                   'prompt_version':session['prompt_version'],'prompt_sha256':session['prompt_sha256']})
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'evaluation.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    errors = [case for case in result['cases'] if not case['full_combination_correct']]
    (args.output/'error_cases.jsonl').write_text(''.join(json.dumps(case,ensure_ascii=False)+'\n' for case in errors))
    print(json.dumps({key:value for key,value in result.items() if key!='cases'},indent=2))


if __name__ == '__main__':
    main()
