"""Independent geometry diagnostics, never imported by the VLM runner."""
from copy import deepcopy
import json
from pathlib import Path
import time
from shapely.affinity import scale
from shapely.geometry import Point,shape
from shapely.ops import unary_union
import yaml
from .diagnostic_data import STATES
from .edits import apply_edits
from .geometry import InvalidGeometry,geo,validate_scene
from .oracle import solve


def pair_overlap(first,second):
    area = first.intersection(second).area
    return {'overlap':bool(area>1e-10),'intersection_area_m2':float(area),
            'touches_without_area':bool(first.touches(second)),
            'minimum_separation_m':None if first.is_empty or second.is_empty else float(first.distance(second))}


def overlap_truth(scene):
    wall = unary_union([shape(g) for g in scene['walls']])
    originals = {o['id']:shape(o['geometry']) for o in scene['objects']}
    answers,details = {},{}
    for name in ['A','B']:
        edit = scene['edits'][name]
        target = shape(edit['target_geometry'])
        other = unary_union([g for oid,g in originals.items() if oid!=edit['object_id']])
        refs = {'start':Point(scene['start']).buffer(scene['robot_radius_m'],quad_segs=128),
                'goal':Point(scene['goal']).buffer(scene['robot_radius_m'],quad_segs=128),
                'walls':wall,'other_original':other}
        details[name] = {key:pair_overlap(target,ref) for key,ref in refs.items()}
        for key in ['start','goal']:
            details[name][key]['distance_to_robot_center_m'] = float(target.distance(Point(scene[key])))
        answers[name] = {key:value['overlap'] for key,value in details[name].items()}
    details['AB_targets'] = pair_overlap(shape(scene['edits']['A']['target_geometry']),
                                         shape(scene['edits']['B']['target_geometry']))
    answers['AB_targets'] = details['AB_targets']['overlap']
    return {'answers':answers,'details':details,
            'definition':'positive-area intersection; boundary contact is recorded separately',
            'robot_disk_quad_segs':128}


def perturbed(scene,object_scale=1.0,radius_offset=0.0):
    result = deepcopy(scene)
    result['robot_radius_m'] += radius_offset
    for obj in result['objects']:
        obj['geometry'] = geo(scale(shape(obj['geometry']),xfact=object_scale,yfact=object_scale,origin='centroid'))
    validate_scene(result)
    return result


def radius_capacity(scene,resolution,low=.001,high=1.2,tolerance=.005):
    """Feasible/infeasible radius bracket on the SAME finite graph, not continuous width."""
    def test(radius):
        changed = deepcopy(scene)
        changed['robot_radius_m'] = radius
        return solve(changed,resolution)
    trace = []
    def check(radius):
        result = test(radius)
        trace.append({'radius_m':radius,'passable':result['passable'],'status':result['status']})
        return result
    initial_low = check(low)
    if not initial_low['passable']:
        return {'status':'no_route_at_minimum_radius','resolution_m':resolution,'trace':trace,
                'max_radius_feasible_lower_m':None,'max_radius_infeasible_upper_m':low}
    if check(high)['passable']:
        return {'status':'upper_radius_not_bracketed','resolution_m':resolution,'trace':trace,
                'max_radius_feasible_lower_m':high,'max_radius_infeasible_upper_m':None}
    while high-low>tolerance:
        mid = (low+high)/2
        if check(mid)['passable']:
            low = mid
        else:
            high = mid
    return {'status':'bracketed','resolution_m':resolution,'trace':trace,
            'max_radius_feasible_lower_m':low,'max_radius_infeasible_upper_m':high,
            'radius_bracket_width_m':high-low,
            'usable_radius_margin_lower_m':low-scene['robot_radius_m'],
            'usable_radius_margin_upper_m':high-scene['robot_radius_m'],
            'effective_disk_diameter_bracket_m':[2*low,2*high],
            'continuous_channel_width_claimed':False}


def run(root):
    root = Path(root)
    cfg = yaml.safe_load((root/'configs/phase3_5.yaml').read_text())
    sensitivity = cfg['sensitivity']
    output = root/'diagnostics/phase3_5/private/geometry_diagnostics.json'
    if output.exists():
        raise FileExistsError(output)
    started = time.perf_counter()
    conditions = [('baseline',1.0,0.0)]
    conditions += [(f'object_scale_{value}',value,0.0) for value in sensitivity['object_scale_factors']]
    conditions += [(f'radius_offset_{value}',1.0,value) for value in sensitivity['robot_radius_offsets_m']]
    rows,overlaps,failures = [],{},[]
    for sid in cfg['sample_ids']:
        scene = json.loads((root/f'data/scenes/{sid}/scene.json').read_text())
        overlaps[sid] = overlap_truth(scene)
        for state,names in STATES.items():
            after = apply_edits(scene,names)
            tests = []
            for name,size,offset in conditions:
                try:
                    variant = perturbed(after,size,offset)
                    resolutions = []
                    for resolution in sensitivity['resolutions_m']:
                        result = solve(variant,resolution)
                        resolutions.append({k:result[k] for k in ['resolution_m','passable','status','path_min_clearance_m']})
                    agree = len({r['passable'] for r in resolutions})==1
                    tests.append({'condition':name,'object_scale':size,'robot_radius_m':variant['robot_radius_m'],
                                  'status':'verified' if agree else 'oracle_unresolved',
                                  'passable':resolutions[0]['passable'] if agree else None,'resolutions':resolutions})
                except InvalidGeometry as exc:
                    tests.append({'condition':name,'status':'illegal_perturbation','error':str(exc),'passable':None})
                    failures.append({'sample_id':sid,'state':state,'condition':name,'error':str(exc)})
            capacity = radius_capacity(after,sensitivity['capacity_resolution_m'],
                sensitivity['capacity_radius_min_m'],sensitivity['capacity_radius_max_m'],sensitivity['capacity_tolerance_m'])
            rows.append({'sample_id':sid,'state':state,'sensitivity':tests,'capacity':capacity})
            print(f'{sid} {state}: capacity {capacity.get("max_radius_feasible_lower_m")}–{capacity.get("max_radius_infeasible_upper_m")}',flush=True)
    record = {'sample_count':6,'state_count':24,'conditions_per_state':len(conditions),
              'attempted_sensitivity_searches':24*len(conditions)*len(sensitivity['resolutions_m']),
              'illegal_perturbations':failures,'overlap':overlaps,'states':rows,
              'elapsed_seconds':time.perf_counter()-started,
              'notes':['Radius perturbation changes obstacle buffer AND workspace inset; not object-only physical inflation.',
                       'Capacity is a conservative finite-grid feasible/infeasible radius bracket, not a continuous-space proof.',
                       'Returned BFS witness clearance is distinct from the best feasible radius margin.']}
    output.write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':
    result=run(Path(__file__).resolve().parents[2])
    print(json.dumps({k:v for k,v in result.items() if k not in ['overlap','states']},indent=2))
