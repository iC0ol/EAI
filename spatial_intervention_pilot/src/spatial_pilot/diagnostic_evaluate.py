"""Phase 3.5 independent post-inference comparison; model runner never imports this."""
from collections import Counter,defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo
from .diagnostic_io import FIELDS

ROOT=Path(__file__).resolve().parents[2]


def exact_correct(value,truth):
    return type(value) is bool and value==truth


def pair_classification(original,poststate,truth):
    if type(original) is not bool or type(poststate) is not bool:
        return 'unknown_in_one_or_both'
    old=exact_correct(original,truth);new=exact_correct(poststate,truth)
    return {(True,True):'both_correct',(False,True):'phase3_wrong_poststate_correct',
            (False,False):'both_wrong',(True,False):'phase3_correct_poststate_wrong'}[(old,new)]


def flatten_overlap(value):
    return {**{f'{name}.{key}':value[name][key] for name in ['A','B'] for key in FIELDS},
            'AB_targets':value['AB_targets']}


def metrics(rows,key='correct'):
    return {'correct':sum(bool(r[key]) for r in rows),'denominator':len(rows),
            'accuracy':sum(bool(r[key]) for r in rows)/len(rows) if rows else None}


def match_queries(predictions,mapping):
    ids=[row['query_id'] for row in predictions]
    if len(ids)!=len(set(ids)) or set(ids)!=set(mapping):
        raise ValueError('Expected exactly one result for every diagnostic query; do not silently discard failures')
    return {row['query_id']:row for row in predictions}


def main():
    output=ROOT/'outputs/phase3_5'
    session=json.loads((output/'session.json').read_text())
    if session['status']!='completed' or session['completed_queries']!=30:
        raise ValueError('Do not read private data until all diagnostic inference completed')
    for path in session['data_read_events']:
        if not path.startswith(('data/images/','diagnostics/phase3_5/inputs/','diagnostics/phase3_5/images/')):
            raise ValueError('Unexpected model-process read')
    prediction_path=output/'predictions.jsonl'
    predictions=[json.loads(line) for line in prediction_path.read_text().splitlines()]
    # Private sources are first opened in this evaluator, after the completed-run gate.
    mapping=json.loads((ROOT/'diagnostics/phase3_5/private/query_map.json').read_text())
    indexed=match_queries(predictions,mapping)
    truths={row['sample_id']:row for row in map(json.loads,(ROOT/'data/private_labels.jsonl').read_text().splitlines())}
    old={row['sample_id']:row for row in map(json.loads,(ROOT/'outputs/phase3/core/predictions.jsonl').read_text().splitlines())}
    geometry=json.loads((ROOT/'diagnostics/phase3_5/private/geometry_diagnostics.json').read_text())
    geo_states={(row['sample_id'],row['state']):row for row in geometry['states']}
    frozen=json.loads((ROOT/'reports/phase3_5/frozen_run.json').read_text())
    for name,sha in frozen['sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha:
            raise ValueError(f'Frozen input/code changed: {name}')
    post,overlap,overlap_details=[],[],[]
    for qid,meta in mapping.items():
        row=indexed[qid];sid=meta['sample_id'];value=row['parsed_output'] if row['parse_ok'] and row['status']=='ok' else None
        if meta['kind']=='poststate':
            state=meta['state'];truth=truths[sid]['labels']['F_'+state]
            if truths[sid]['status']!='verified' or type(truth) is not bool:
                raise ValueError('Unresolved original truth cannot enter diagnostic scoring')
            sensitivity=geo_states[(sid,state)]['sensitivity']
            baseline=next(r for r in sensitivity if r['condition']=='baseline')
            if baseline['status']!='verified' or baseline['passable']!=truth:
                raise ValueError('Baseline oracle disagreement: quarantine before scoring')
            pred=value['passable'] if value else None
            before=old[sid].get('parsed_output')
            old_value=before['F_'+state] if before and state!='NONE' else None
            post.append({'query_id':qid,'sample_id':sid,'state':state,'family':truths[sid]['family'],
                'truth':truth,'prediction':pred,'phase3_prediction':old_value,'correct':exact_correct(pred,truth),
                'phase3_correct':exact_correct(old_value,truth) if state!='NONE' else None,
                'pair_classification':pair_classification(old_value,pred,truth) if state!='NONE' else None,
                'parse_ok':row['parse_ok'],'explanation':value['explanation'] if value else None,
                'raw_response':row['response_text'],'inference_seconds':row.get('inference_seconds'),
                'peak_allocated_mib':row.get('peak_allocated_mib')})
        else:
            actual=flatten_overlap(geometry['overlap'][sid]['answers'])
            predicted=flatten_overlap(value) if value else dict.fromkeys(actual,None)
            fields=[{'field':key,'truth':actual[key],'prediction':predicted[key],
                     'correct':exact_correct(predicted[key],actual[key])} for key in actual]
            overlap_details.extend(dict(field,sample_id=sid,query_id=qid) for field in fields)
            overlap.append({'query_id':qid,'sample_id':sid,'parse_ok':row['parse_ok'],'fields':fields,
                'explanation':value['explanation'] if value else None,'raw_response':row['response_text'],
                'geometry':geometry['overlap'][sid],'phase3_explanation':old[sid]['parsed_output']['explanation']})
    paired=[r for r in post if r['state']!='NONE']
    counters=dict(Counter(r['pair_classification'] for r in paired))
    flip_conditions=[];unresolved=[]
    for row in geometry['states']:
        baseline=next(r for r in row['sensitivity'] if r['condition']=='baseline')['passable']
        for condition in row['sensitivity']:
            entry={'sample_id':row['sample_id'],'state':row['state'],**condition}
            if condition['status']!='verified':unresolved.append(entry)
            elif condition['passable']!=baseline:flip_conditions.append(entry)
    families={family:{'phase3_paired':metrics([r for r in paired if r['family']==family],'phase3_correct'),
                      'poststate_paired':metrics([r for r in paired if r['family']==family]),
                      'poststate_all':metrics([r for r in post if r['family']==family])}
              for family in sorted({r['family'] for r in post})}
    result={'evaluated_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        'model_id':session['model_id'],'model_revision':session['model_revision'],
        'predictions_sha256':hashlib.sha256(prediction_path.read_bytes()).hexdigest(),
        'poststate_all':metrics(post),'poststate_paired':metrics(paired),'phase3_paired':metrics(paired,'phase3_correct'),
        'poststate_by_state':{state:metrics([r for r in post if r['state']==state]) for state in ['NONE','A','B','AB']},
        'paired_categories':counters,'families':families,
        'overlap_atomic':metrics(overlap_details),
        'overlap_truth_positive_count':sum(r['truth'] for r in overlap_details),
        'overlap_false_positive_count':sum(r['prediction'] is True and not r['truth'] for r in overlap_details),
        'overlap_unknown_count':sum(r['prediction'] is None for r in overlap_details),
        'parse_failures':sum(not r['parse_ok'] for r in predictions),
        'sensitivity_label_flips':flip_conditions,'sensitivity_unresolved_or_illegal':unresolved,
        'poststate_cases':post,'overlap_cases':overlap,
        'interpretation_limits':['Paired recovery is consistent with hypothetical-edit/state-prediction burden but not causal proof.',
          'Prompt, rendering and supplied post-state observation differ; direct errors do not separate perception from route reasoning.',
          'Overlap truth set contains no positive overlaps; accuracy alone cannot establish overlap-detection sensitivity.',
          'Six base examples with controlled views; no statistical or generalization conclusion.']}
    report=ROOT/'reports/phase3_5'
    (report/'evaluation.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    errors=[r for r in post if not r['correct']]
    (report/'poststate_errors.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in errors))
    (report/'overlap_atomic_results.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in overlap_details))
    print(json.dumps({k:v for k,v in result.items() if k not in ['poststate_cases','overlap_cases']},indent=2))


if __name__=='__main__':
    main()
