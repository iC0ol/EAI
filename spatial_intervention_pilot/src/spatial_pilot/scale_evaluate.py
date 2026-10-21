"""Independent CPU evaluation after all Part A/B public-only inference has completed."""
from datetime import datetime,timezone
import json
from pathlib import Path
import statistics
import time
import numpy as np
from PIL import Image
import shapely
from .geometry import CollisionModel
from .scale_io import verify_frozen,digest

ROOT=Path(__file__).resolve().parents[2]


def read_rows(path):return list(map(json.loads,path.read_text().splitlines()))


def metrics(rows,truth):
    assert len({r['query_id'] for r in rows})==len(rows) and {r['query_id'] for r in rows}==set(truth)
    cases=[]
    for r in rows:
        label=truth[r['query_id']];pred=r['prediction'];t=label['passable']
        cases.append({**r,'category':label['category'],'truth':t,'correct':pred is t,'layout_description':label['layout_description']})
    tp=sum(c['truth'] and c['prediction'] is True for c in cases);tn=sum(not c['truth'] and c['prediction'] is False for c in cases)
    fp=sum(not c['truth'] and c['prediction'] is True for c in cases);fn=sum(c['truth'] and c['prediction'] is False for c in cases)
    unknown=sum(c['prediction'] is None for c in cases);positive=sum(c['truth'] for c in cases);negative=len(cases)-positive
    timing=[c['end_to_end_seconds'] for c in cases if c.get('end_to_end_seconds') is not None]
    return {'total':len(cases),'correct':tp+tn,'accuracy':(tp+tn)/len(cases),'TP':tp,'FP':fp,'TN':tn,'FN':fn,'unknown':unknown,
            'reachable_recall':tp/positive,'unreachable_recognition_rate':tn/negative,
            'categories':{cat:{'correct':sum(c['correct'] for c in cases if c['category']==cat),'total':sum(c['category']==cat for c in cases)} for cat in 'ABCD'},
            'prediction_reachable':tp+fp,'prediction_unreachable':tn+fn,
            'end_to_end_mean_seconds':statistics.mean(timing) if timing else None,
            'end_to_end_total_seconds':sum(timing),'failures':sum(c.get('status')=='pipeline_error' for c in cases),
            'parse_success':sum(c.get('parse_ok',True) for c in cases),
            'always_reachable_correct':positive,'always_unreachable_correct':negative},cases


def vlm_row(r,dataset=None):
    return {'query_id':r['query_id'],'dataset':dataset or r['dataset'],'prediction':r['parsed_output']['passable'] if r['parse_ok'] else None,
            'response_text':r['response_text'],'parse_ok':r['parse_ok'],'parse_error':r['parse_error'],'status':r['status'],
            'end_to_end_seconds':r.get('end_to_end_seconds',r['elapsed_seconds']),
            'preprocess_seconds':r['preprocess_seconds'],'generation_seconds':r['inference_seconds'],
            'peak_allocated_mib':r['peak_allocated_mib']}


def paired(first,second):
    a={c['query_id']:c for c in first};b={c['query_id']:c for c in second};assert set(a)==set(b)
    return {'4b_wrong_8b_right':sum(not a[k]['correct'] and b[k]['correct'] for k in a),
            '4b_right_8b_wrong':sum(a[k]['correct'] and not b[k]['correct'] for k in a),
            'both_correct':sum(a[k]['correct'] and b[k]['correct'] for k in a),
            'both_wrong':sum(not a[k]['correct'] and not b[k]['correct'] for k in a),
            'prediction_agreements':sum(a[k]['prediction'] is b[k]['prediction'] for k in a)}


def main(root=ROOT):
    reports=root/'reports/phase3_7';out=root/'outputs/phase3_7'
    # Enforce process/order isolation before opening any private label.
    for name,count in [('vlm8b_a',40),('vlm4b_new',24),('rgb',80)]:
        s=json.loads((out/name/'session.json').read_text())
        assert s['status']=='completed' and s.get('completed_queries',s.get('records'))==count
    verify_frozen(root)
    frozen=json.loads((reports/'frozen_run.json').read_text())
    assert all(digest(root/n)==h for n,h in frozen['private_files'].items())
    opened=datetime.now(timezone.utc).isoformat()
    label_sets={'old16':read_rows(root/'diagnostics/phase3_6/private/private_labels.jsonl'),
                'new24':read_rows(root/'diagnostics/phase3_7/private/new24_labels.jsonl')}
    truth={d:{l['sample_id']:l for l in rows} for d,rows in label_sets.items()}
    old4=[vlm_row(r,'old16') for r in read_rows(root/'outputs/phase3_6/predictions.jsonl')]
    new4=[vlm_row(r) for r in read_rows(out/'vlm4b_new/predictions.jsonl')]
    eight=[vlm_row(r) for r in read_rows(out/'vlm8b_a/predictions.jsonl')]
    rgb=read_rows(out/'rgb/predictions.jsonl')
    allcases={};summary={'evaluated_at':opened,'private_labels_opened_after_all_inference':True,'sets':{},'paired':{}}
    for dataset in ['old16','new24']:
        methods={'4b':old4 if dataset=='old16' else new4,'8b':[r for r in eight if r['dataset']==dataset]}
        for algorithm in ['bfs','astar']:
            methods[algorithm]=[{**r,'prediction':r['passable']} for r in rgb if r['dataset']==dataset and r['algorithm']==algorithm]
        summary['sets'][dataset]={};allcases[dataset]={}
        for name,rows in methods.items():
            summary['sets'][dataset][name],allcases[dataset][name]=metrics(rows,truth[dataset])
        summary['sets'][dataset]['oracle_reference']={'labels':len(truth[dataset]),'three_resolution_agreement':all(len({g['passable'] for g in l['grids']})==1 for l in truth[dataset].values()),
                                                      'not_an_independent_image_method':True,'accuracy_not_reported_as_performance':True}
        summary['paired'][dataset]=paired(allcases[dataset]['4b'],allcases[dataset]['8b'])
    # Gate fixed in configuration BEFORE inference. No further VLM run is triggered here.
    import yaml
    policy=yaml.safe_load((root/'configs/phase3_7.yaml').read_text())['gate']
    new=summary['sets']['new24']['8b'];b_correct=new['categories']['B']['correct']
    negative_correct=new['categories']['C']['correct']+new['categories']['D']['correct']
    gate={'policy':policy,'new8b_detour_correct':b_correct,'new8b_negative_correct':negative_correct,
          'part_c_permitted':b_correct>=policy['part_c_min_correct_new_detours'] and negative_correct>=policy['part_c_min_correct_new_negatives'],
          'status':'pending_gate'}
    gate['status']='permitted_exploratory_only' if gate['part_c_permitted'] else 'No-Go: basic reliability gate not met; do not execute Part C'
    summary['part_c_gate']=gate
    with (reports/'part_a_b_metrics.json').open('x') as f:json.dump(summary,f,indent=2);f.write('\n')
    paired_rows=[]
    for dataset,methods in allcases.items():
        maps={m:{c['query_id']:c for c in rows} for m,rows in methods.items()}
        for sid,l in truth[dataset].items():
            paired_rows.append({'sample_id':sid,'dataset':dataset,'category':l['category'],'truth':l['passable'],
                                'methods':{m:maps[m][sid] for m in maps}})
    with (reports/'paired_cases.jsonl').open('x') as f:
        for row in paired_rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    # Optional post-inference geometry audit is explicitly separate from image prediction.
    # It cannot alter any occupancy grid, path or prediction.
    audits=[]
    for row in paired_rows:
        sid=row['sample_id'];dataset=row['dataset']
        scene_path=(root/f'diagnostics/phase3_6/private/scenes/{sid}.json' if dataset=='old16' else root/f'diagnostics/phase3_7/private/scenes/{sid}.json')
        scene=json.loads(scene_path.read_text());model=CollisionModel.from_scene(scene)
        extracted=json.loads((out/f'rgb/{sid}_extraction.json').read_text()) if (out/f'rgb/{sid}_extraction.json').is_file() else None
        audit={'sample_id':sid,'dataset':dataset,'post_inference_only':True}
        if extracted:
            left,top,right,bottom=extracted['frame_px'];scale=extracted['scale'];h=bottom-top+1;w=right-left+1
            yy,xx=np.meshgrid(np.arange(h),np.arange(w),indexing='ij')
            raw=shapely.intersects_xy(model.raw_obstacles,xx/scale,12-yy/scale)
            with Image.open(out/f'rgb/{sid}_occupancy.png') as im:predicted=np.array(im)>0
            a,b=raw[2:-2,2:-2],predicted[2:-2,2:-2];union=np.logical_or(a,b).sum()
            audit['obstacle_IoU_excluding_two_pixel_frame']=float(np.logical_and(a,b).sum()/union) if union else 1.0
            audit['endpoint_errors_m']={k:float(np.linalg.norm(np.array([extracted['markers'][k][0]/scale,12-extracted['markers'][k][1]/scale])-scene[k])) for k in ['start','goal']}
        for method in ['bfs','astar']:
            c=row['methods'][method];path=c.get('path_m',[])
            audit[method]={'predicted_passable':c['prediction'],'correct':c['correct'],'failure_reason':c.get('failure_reason')}
            if path:
                augmented=[scene['start']]+path+[scene['goal']]
                audit[method]['path_collision_free_in_private_geometry']=all(model.segment_free(a,b) for a,b in zip(augmented,augmented[1:]))
                audit[method]['path_min_clearance_m']=model.path_clearance(augmented)
        audits.append(audit)
    with (reports/'posthoc_segmentation_path_audit.json').open('x') as f:json.dump(audits,f,indent=2);f.write('\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
