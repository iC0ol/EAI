"""One independent replayed-prefix surrogate, then one log-action proxy suffix."""
import json
import random
import time
import traceback
from collections import deque

import h5py
import numpy as np
import torch

from .io import ROOT,M_ROOT,OUT,LOCAL,config,sha256,array_hash,read_json,write_json,git,stable_seed
from .audit import verify,deadline,Ledger,canonical_branch
from .geometry import PhysicalObserver,contact_frame
from m_direction.assets import create_env,data_path,flatten_obs,demo_obs
from m_direction.replay import ControllerTap,snapshot,source_error
from m_direction.perturb import intervention
from m_direction.policy import predict


class Steps:
    def __init__(self):self.allowed=False;self.prefix=0;self.suffix=0;self.phase='prefix'
    def __enter__(self):
        from robosuite.utils.binding_utils import MjSim
        self.cls=MjSim;self.original={k:getattr(MjSim,k) for k in ['step','step1','step2']}
        def step(sim,*args,**kwargs):
            if not self.allowed:raise RuntimeError('Unexpected constructor/reset integration')
            out=self.original['step'](sim,*args,**kwargs)
            setattr(self,self.phase,getattr(self,self.phase)+1);return out
        def forbidden(*a,**kw):raise RuntimeError('Frozen lite_physics=false; unexpected step1/step2')
        MjSim.step=step;MjSim.step1=forbidden;MjSim.step2=forbidden;return self
    def __exit__(self,*args):
        for k,v in self.original.items():setattr(self.cls,k,v)
    def run(self,env,action):
        deadline();self.allowed=True;before=getattr(self,self.phase)
        try:out=env.step(action)
        finally:self.allowed=False
        assert getattr(self,self.phase)-before==25
        return out


def control_vector(raw):
    c=raw.robots[0].part_controllers['right']
    return np.r_[c.goal_pos,np.asarray(c.goal_ori).reshape(-1),c.ref_pos,np.asarray(c.ref_ori_mat).reshape(-1)]


def gripper_vector(raw):
    x=np.asarray(raw.robots[0].gripper['right'].current_action).reshape(-1)
    assert len(x)<=2
    return np.r_[x,np.zeros(2-len(x))],len(x)


def execute(branch,state_card,policy):
    registration=verify();b=canonical_branch(branch)
    Ledger().reserve(b)
    start,cpu=time.monotonic(),time.process_time()
    r={**b,'subject':config()['subject'],'source_episode':state_card['source_episode'],'t':int(state_card['t']),
       'split':state_card['split'],'source_phase':state_card['phase'],'protocol_commit':registration['protocol_commit'],
       'execution_commit':git('rev-parse','HEAD'),'data_sha256':read_json(M_ROOT/'configs/gate0.json')['data_sha256'],
       'checkpoint_sha256':read_json(M_ROOT/'configs/gate0.json')['checkpoint_sha256']['42'],
       'code_sha256':{str(p.relative_to(ROOT)):sha256(p) for p in sorted((ROOT/'src').rglob('*.py'))},
       'status':'started','prefix_control_steps':0,'suffix_control_steps':0,'replans':[],
       'sim_wall_seconds':0.,'sim_cpu_seconds':0.,'inference_calls':0,'inference_wall_seconds':0.,'inference_cpu_seconds':0.,'inference_gpu_ms':0.}
    data={k:[] for k in ['prefix_states','prefix_obs','prefix_physical_obs','prefix_received_actions','prefix_controller','prefix_gripper',
                         'suffix_sim_states','suffix_observations','suffix_physical_obs','suffix_received_actions','suffix_after_clip_actions',
                         'suffix_controller','suffix_gripper','suffix_success','suffix_ncon','replan_histories','initial_noise']}
    errors=[];env=None;counter=None
    try:
        prefix_wall,prefix_cpu=time.monotonic(),time.process_time()
        with h5py.File(data_path(),'r') as f,Steps() as counter:
            g=f[f"data/{state_card['source_episode']}"];t=int(state_card['t'])
            seed=stable_seed(state_card['state_id']);random.seed(seed);np.random.seed(seed)
            env=create_env();env.reset()
            obs=env.reset_to({'model':g.attrs['model_file'],'states':g['states'][0],'ep_meta':g.attrs.get('ep_meta',None)})
            raw=env.env;assert not raw.lite_physics
            physical=PhysicalObserver(env);assert (physical.model.nq,physical.model.nv,physical.model.na)==(23,21,0)
            tap=ControllerTap(env);native=flatten_obs(obs);history=deque([native.copy(),native.copy()],maxlen=2)
            prefix_ever=False
            for j in range(t+1):
                s=raw.sim.get_state().flatten().copy();native=flatten_obs(obs);geo=physical.live()
                data['prefix_states'].append(s);data['prefix_obs'].append(native);data['prefix_physical_obs'].append(geo)
                data['prefix_controller'].append(control_vector(raw));gv,gl=gripper_vector(raw);data['prefix_gripper'].append(np.r_[gv,gl])
                error=source_error(s,native,g['states'][j],demo_obs(g,j));errors.append(error)
                if j==t:break
                action=g['actions'][j];tap.begin();obs,_,_,_=counter.run(env,action);r['prefix_control_steps']+=1
                receipt=tap.receipt(action);data['prefix_received_actions'].append(receipt['composite_input']);history.append(flatten_obs(obs))
                prefix_ever=prefix_ever or bool(env.is_success()['task'])
            r['prefix_wall_seconds']=time.monotonic()-prefix_wall;r['prefix_cpu_seconds']=time.process_time()-prefix_cpu
            r['source_deviation_max']={k:max(x[k] for x in errors) for k in errors[0]};r['source_deviation_at_fork']=errors[-1]
            r['source_physical_deviation_at_fork']=source_error(data['prefix_states'][-1],physical.live(),g['states'][t],demo_obs(g,t))
            r['prefix_ever_success']=prefix_ever
            r['fork_snapshot']=snapshot(env,history)
            obj_R,peg_R,peg_pos=physical.frames();contact_R,contact_info=contact_frame(raw,peg_R,config())
            r['geometry']={'object_rotation':obj_R,'task_rotation':peg_R,'peg_position':peg_pos,'contact_rotation':contact_R,
                           'contact':contact_info,'proxy_physical_obs16':physical.live(),'native_obs16':native,
                           'source_obs16':demo_obs(g,t),'source_logged_action7':g['actions'][t]}
            if bool(env.is_success()['task']):raise RuntimeError('Technical rejection: online proxy already successful at fork')
            logged=g['actions'][t].copy();np.testing.assert_array_equal(logged,json.loads(state_card['expert_action']))
            requested,delta=intervention(logged,b['direction'],b['sign'],b['radius'])
            r.update({'logged_action7':logged,'requested_action7':requested,'delta7':delta,'delta_norm':float(np.linalg.norm(delta[:3]))})
            if b['stage']!='A' and b['direction']!='nominal':
                nominal_id=f"LB1_{state_card['state_id']}_nominal_+0" if state_card['split']=='development' else f"LB3_{state_card['state_id']}_nominal_+0"
                nominal=read_json(OUT/'branches'/f'{nominal_id}.json')
                assert nominal['status']=='completed' and nominal['fork_snapshot']==r['fork_snapshot'],'Unmatched online fork/history/controller/RNG'
                r['nominal_branch_id']=nominal_id
            # Prefix histories are native. The logged command is used once; then only frozen DP.
            data['suffix_sim_states'].append(raw.sim.get_state().flatten().copy());data['suffix_observations'].append(native.copy())
            data['suffix_physical_obs'].append(physical.live());data['suffix_controller'].append(control_vector(raw))
            gv,gl=gripper_vector(raw);data['suffix_gripper'].append(np.r_[gv,gl])
            counter.phase='suffix';policy.reset()
            for index in range(t,config()['episode_horizon']):
                deadline()
                if index==t:action=requested
                else:
                    offset=(index-t-1)%8
                    if offset==0:
                        data['replan_histories'].append(np.stack(history));torch.cuda.synchronize()
                        iw,ic=time.monotonic(),time.process_time();e0,e1=torch.cuda.Event(enable_timing=True),torch.cuda.Event(enable_timing=True)
                        e0.record();chunk,schedule,noise=predict(policy,history,state_card['state_id'],len(r['replans']),0)
                        e1.record();torch.cuda.synchronize()
                        r['inference_gpu_ms']+=e0.elapsed_time(e1);r['inference_wall_seconds']+=time.monotonic()-iw;r['inference_cpu_seconds']+=time.process_time()-ic
                        schedule['absolute_step_before']=index;r['replans'].append(schedule);data['initial_noise'].append(noise);r['inference_calls']+=1
                    action=chunk[offset]
                sw,sc=time.monotonic(),time.process_time();tap.begin();obs,_,_,_=counter.run(env,action);r['suffix_control_steps']+=1
                receipt=tap.receipt(action)
                if index==t:
                    assert not receipt['command_clipped'],'First intervention was clipped'
                    np.testing.assert_allclose(receipt['composite_input']-logged,delta,atol=1e-15,rtol=0)
                    np.testing.assert_array_equal(receipt['composite_input'][3:],logged[3:])
                    r['intervention_receipt']=receipt;r['actual_delta7']=receipt['composite_input']-logged
                native=flatten_obs(obs);history.append(native.copy());geo=physical.live()
                data['suffix_sim_states'].append(raw.sim.get_state().flatten().copy());data['suffix_observations'].append(native)
                data['suffix_physical_obs'].append(geo);data['suffix_received_actions'].append(receipt['composite_input'])
                data['suffix_after_clip_actions'].append(receipt['normalized_after_clip']);data['suffix_controller'].append(control_vector(raw))
                gv,gl=gripper_vector(raw);data['suffix_gripper'].append(np.r_[gv,gl]);data['suffix_success'].append(bool(env.is_success()['task']))
                data['suffix_ncon'].append(int(raw.sim.data.ncon));r['sim_wall_seconds']+=time.monotonic()-sw;r['sim_cpu_seconds']+=time.process_time()-sc
            assert r['suffix_control_steps']==400-t
            assert raw.timestep==400 and abs(float(raw.sim.data.time)-float(g['states'][0,0])-20.)<1e-8
            r['final_env_timestep']=int(raw.timestep);r['final_sim_time']=float(raw.sim.data.time)
            success=data['suffix_success'];r.update({'status':'completed','ever_success':any(success),'final_success':success[-1],
                'first_success_absolute_step':t+1+success.index(True) if any(success) else None,'final_native_obs16':native,'final_physical_obs16':geo,
                'final_nut_to_peg_xy_m':float(np.linalg.norm((geo[:3]-peg_pos)[:2])),
                'policy_clipped_steps':int(np.any(np.asarray(data['suffix_received_actions'])[1:,:6]!=np.asarray(data['suffix_after_clip_actions'])[1:,:6],axis=1).sum())})
    except Exception as exc:
        r.update({'status':'invalid','error_type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc()})
    finally:
        r['prefix_integration_steps']=counter.prefix if counter else 0;r['suffix_integration_steps']=counter.suffix if counter else 0
        r['partial_integration_steps']=r['prefix_integration_steps']+r['suffix_integration_steps']-25*(r['prefix_control_steps']+r['suffix_control_steps'])
        if r['partial_integration_steps'] and r['status']=='completed':r['status']='invalid';r['error']='Unaccounted partial control integration'
        trace=LOCAL/'traces'/f"{b['branch_id']}.npz";trace.parent.mkdir(parents=True,exist_ok=True)
        with trace.open('xb') as f:np.savez_compressed(f,**{k:np.asarray(v) for k,v in data.items()})
        r['trace_path']=str(trace.relative_to(ROOT));r['trace_sha256']=sha256(trace)
        if env is not None:env.env.close()
        r['wall_seconds']=time.monotonic()-start;r['process_cpu_seconds']=time.process_time()-cpu
        r['peak_cuda_allocated_bytes']=torch.cuda.max_memory_allocated();r['peak_cuda_reserved_bytes']=torch.cuda.max_memory_reserved()
        p=OUT/'branches'/f"{b['branch_id']}.json";write_json(p,r)
        Ledger().append({'event':'finished','branch_id':b['branch_id'],'stage':b['stage'],'status':r['status'],
                         'prefix_control_steps':r['prefix_control_steps'],'suffix_control_steps':r['suffix_control_steps'],
                         'prefix_integration_steps':r['prefix_integration_steps'],'suffix_integration_steps':r['suffix_integration_steps'],'result_sha256':sha256(p)})
        print(json.dumps({k:r.get(k) for k in ['branch_id','status','suffix_control_steps','ever_success','final_success','error','wall_seconds']}),flush=True)
    return r
