import numpy as np
from .io import ROOT,config,sha256
from m_direction.audit import compare_zero
from m_direction.geometry import quat_angle


def compare(a,b):
    for r in [a,b]:assert sha256(ROOT/r['trace_path'])==r['trace_sha256']
    x=np.load(ROOT/a['trace_path']);y=np.load(ROOT/b['trace_path'])
    aa={**a,'prefix_diagnostics':{'fork_snapshot':a['fork_snapshot']}}
    bb={**b,'prefix_diagnostics':{'fork_snapshot':b['fork_snapshot']}}
    out=compare_zero(aa,bb,x,y)
    out['prefix_obs_max_abs']=float(abs(x['prefix_obs']-y['prefix_obs']).max())
    out['prefix_action_max_abs']=float(abs(x['prefix_received_actions']-y['prefix_received_actions']).max())
    for phase in ['prefix','suffix']:
        s='prefix_states' if phase=='prefix' else 'suffix_sim_states'
        p='prefix_physical_obs' if phase=='prefix' else 'suffix_physical_obs'
        out[f'{phase}_raw_state_max_abs']=float(abs(x[s]-y[s]).max())
        out[f'{phase}_physical_position_m']=float(max(np.linalg.norm(x[p][:,:3]-y[p][:,:3],axis=1).max(),np.linalg.norm(x[p][:,7:10]-y[p][:,7:10],axis=1).max()))
        out[f'{phase}_physical_rotation_rad']=float(max(quat_angle(x[p][:,3:7],y[p][:,3:7]).max(),quat_angle(x[p][:,10:14],y[p][:,10:14]).max()))
        out[f'{phase}_controller_goal_max_abs']=float(abs(x[f'{phase}_controller']-y[f'{phase}_controller']).max())
        out[f'{phase}_gripper_action_max_abs']=float(abs(x[f'{phase}_gripper']-y[f'{phase}_gripper']).max())
    out['history_max_abs']=float(abs(x['replan_histories']-y['replan_histories']).max())
    extra=out['history_max_abs']<=1e-5 and out['fork_snapshot_identical'] and out['prefix_obs_max_abs']<=1e-5 and out['prefix_action_max_abs']<=1e-5
    for phase in ['prefix','suffix']:
        extra=extra and out[f'{phase}_raw_state_max_abs']<=1e-4 and out[f'{phase}_physical_position_m']<=1e-5 and out[f'{phase}_physical_rotation_rad']<=1e-4 and out[f'{phase}_controller_goal_max_abs']<=1e-5 and out[f'{phase}_gripper_action_max_abs']<=1e-5
    out['passed']=bool(out['passed'] and extra)
    x.close();y.close();return out
