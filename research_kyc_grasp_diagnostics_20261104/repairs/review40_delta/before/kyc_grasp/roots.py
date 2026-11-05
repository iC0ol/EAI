"""Freeze substitute XML once, then restore identical physical state/controller/RNG."""
from .common import *

def digest_array(a):
    import numpy as np
    a=np.ascontiguousarray(a);return dict(shape=list(a.shape),dtype=str(a.dtype),sha256=hashlib.sha256(a.tobytes()).hexdigest())
def physics(env):
    import numpy as np
    model=env.sim.model
    names=['body_pos','body_quat','body_mass','body_inertia','geom_type','geom_size','geom_pos','geom_quat','geom_friction','geom_condim','geom_contype','geom_conaffinity','geom_solref','geom_solimp','jnt_type','jnt_pos','jnt_axis','jnt_range','jnt_stiffness','dof_damping','dof_armature','actuator_gainprm','actuator_biasprm','actuator_ctrlrange','site_pos','site_quat','site_size']
    values={k:digest_array(np.asarray(getattr(model,k))) for k in names if hasattr(model,k)}
    require(all(k in values for k in ['body_mass','geom_size','geom_friction','jnt_type']),'physical model fingerprint incomplete')
    return dict(dimensions={k:int(getattr(model,k)) for k in ['nq','nv','nu','nbody','ngeom','njnt']},arrays=values,cube_geom_size=np.asarray(model.geom_size[model.geom_name2id(env.cube.contact_geoms[0])]).tolist(),camera_arrays_excluded=True)
def controllers(env):
    r=env.robots[0];v=getattr(r,'part_controllers',None)
    if v is None:v=r.composite_controller.part_controllers
    return v

def control_state(env):
    import numpy as np
    result={}
    for name,c in controllers(env).items():
        record={}
        for k in ['goal_pos','goal_ori','origin_pos','origin_ori','initial_joint','current_action']:
            if hasattr(c,k):
                value=getattr(c,k);record[k]=None if value is None else np.asarray(value).tolist()
        result[name]=record
    grip=env.robots[0].gripper;gs=grip if isinstance(grip,dict) else {'gripper':grip}
    return dict(wrapper_abs_pose=env._asw_last_abs_pose.tolist(),controllers=result,grippers={n:np.asarray(g.current_action).tolist() for n,g in gs.items() if hasattr(g,'current_action')})
def restore_control(env,value):
    import numpy as np
    for name,attrs in value['controllers'].items():
        c=controllers(env)[name]
        for k,v in attrs.items():setattr(c,k,None if v is None else np.asarray(v,float))
    grip=env.robots[0].gripper;gs=grip if isinstance(grip,dict) else {'gripper':grip}
    for n,v in value['grippers'].items():gs[n].current_action=np.asarray(v,float)
    env._asw_last_abs_pose=np.asarray(value['wrapper_abs_pose'],float).copy()
def freeze_one(env,lib,audit,root):
    import numpy as np,torch
    directory=P/('roots/root_'+str(root['root_id']));directory.mkdir(exist_ok=False)
    with np.load(P/root['expert_file'],allow_pickle=False) as z:source=z['source_initial_state'].copy();first=z['starting_abs_action'].copy();action=z['actions'][0].copy()
    env.sim.set_state_from_flattened(source);env.sim.forward();env.set_init_action()
    xml=env.model.get_xml();(directory/'model.xml').write_text(xml)
    audit.label('ROOT_FREEZE_'+str(root['root_id']));env.reset_from_xml_string(xml);env.sim.set_state_from_flattened(source);env.sim.forward();env.set_init_action()
    current=env.sim.get_state().flatten();require(np.array_equal(current,source),'source state failed exact canonical restore')
    np.save(directory/'state.npy',current);torch.save(lib.rng_state(),directory/'rng.pt')
    control=control_state(env);write(directory/'control.json',control);fingerprint=physics(env);write(directory/'physical_model.json',fingerprint)
    err=float(np.max(np.abs(env._asw_last_abs_pose+action[:6]-first[:6])));require(err<1e-4,'first expert absolute target incompatible with restored initial pose')
    files={str(f.relative_to(P)):sha(f) for f in sorted(directory.iterdir()) if f.is_file()}
    return dict(root_id=root['root_id'],directory=str(directory.relative_to(P)),files=files,source_demo_XML_available=False,substitute_seed=root['env_seed'],physical_model=fingerprint,first_absolute_command_error=err,original_source_state_sha256=root['HDF5_initial_state_sha256'])
def restore(env,lib,audit,root,T):
    import numpy as np,torch
    frozen=next(x for x in read(P/'roots/manifest.json')['roots'] if x['root_id']==root['root_id']);directory=P/frozen['directory']
    for n,v in frozen['files'].items():require(sha(P/n)==v,'root file changed')
    audit.label('RESTORE_'+str(root['root_id']));env.reset_from_xml_string((directory/'model.xml').read_text());state=np.load(directory/'state.npy',allow_pickle=False);env.sim.set_state_from_flattened(state);env.sim.forward();env.set_init_action()
    control=read(directory/'control.json');require(np.allclose(env._asw_last_abs_pose,np.asarray(control['wrapper_abs_pose']),atol=1e-12,rtol=0),'initial accumulated target differs')
    restore_control(env,control);lib.restore_rng(torch.load(directory/'rng.pt',map_location='cpu',weights_only=False));lib.camera_pose(env,np.asarray(T))
    require(np.array_equal(env.sim.get_state().flatten(),state),'paired physical state differs')
    require(physics(env)==frozen['physical_model'],'paired physical model/geometry differs')
    require(control_state(env)==control,'controller/gripper target restore differs')
    return dict(root_id=root['root_id'],root_files=frozen['files'],state_exact=True,physical_model_exact=True,controller_exact=True,T=np.asarray(T).tolist())
