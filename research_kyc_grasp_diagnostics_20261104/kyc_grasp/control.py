"""Observe the original wrapper and the absolute command received by base.step."""
from .common import *
from .ledger import reserve

def gripper_state(env,obs=None):
    import numpy as np
    robot=env.robots[0];groups=robot._ref_gripper_joint_pos_indexes
    require(isinstance(groups,dict) and groups,'verified gripper joint index mapping missing')
    result={};flat=[]
    for arm,indexes in groups.items():
        require(indexes is not None and len(indexes)>0,'empty gripper joint indices')
        gripper=robot.gripper[arm] if isinstance(robot.gripper,dict) else robot.gripper
        addresses=[env.sim.model.get_joint_qpos_addr(name) for name in gripper.joints]
        require(list(indexes)==addresses,'gripper qpos mapping does not match actual named joints')
        values=np.asarray(env.sim.data.qpos[indexes]).copy();require(values.size>0 and np.isfinite(values).all(),'gripper qpos unavailable/nonfinite')
        result[arm]=dict(joint_names=list(gripper.joints),qpos_indexes=[int(x) for x in indexes],qpos=values.tolist(),actual_named_sim_joints_verified=True);flat.extend(values.tolist())
    seen={k:np.asarray(v).tolist() for k,v in (obs or {}).items() if k.endswith('gripper_qpos')}
    if seen:require(any(np.array_equal(np.asarray(v).reshape(-1),np.asarray(flat)) for v in seen.values()),'gripper observation disagrees with verified sim joints')
    return dict(by_arm=result,qpos=flat,observation_fields=seen,source='named actual sim joints, crosschecked with obs when present')

class StepRecorder:
    def __init__(self,env,folder,label):
        from robosuite.environments.base import MujocoEnv
        self.env=env;self.folder=folder;self.label=label;self.pending=None;self.rows=[];self.absolute=None
        self.initial_EEF=env.sim.data.site_xpos[env.sim.model.site_name2id('gripper0_right_grip_site')].copy().tolist()
        self.initial_cube=env.sim.data.body_xpos[env.cube_body_id].copy().tolist()
        self.initial_EEF_rotation=env.sim.data.site_xmat[env.sim.model.site_name2id('gripper0_right_grip_site')].reshape(3,3).copy().tolist()
        self.initial_gripper=gripper_state(env)
        if not hasattr(MujocoEnv,'_kyc_diag_original_step'):MujocoEnv._kyc_diag_original_step=MujocoEnv.step
        original=MujocoEnv._kyc_diag_original_step;rec=self
        def step(obj,action,*a,**kw):
            require(obj is rec.env and rec.pending is not None,'unplanned environment step');reserve('env_steps','control',rec.label)
            import numpy as np
            absolute=np.asarray(action).copy();expected=np.r_[rec.pending['previous']+rec.pending['delta'][:6],rec.pending['delta'][-1]]
            require(np.array_equal(absolute,expected),'original wrapper/base absolute accumulation mismatch');rec.absolute=absolute
            return original(obj,action,*a,**kw)
        MujocoEnv.step=step
    def step(self,delta):
        import numpy as np
        env=self.env;delta=np.asarray(delta).copy();require(delta.shape==(7,) and np.isfinite(delta).all(),'bad delta action')
        previous=env._asw_last_abs_pose.copy();self.pending=dict(previous=previous,delta=delta);self.absolute=None
        try:obs,reward,done,info=env.step(delta)
        finally:self.pending=None
        require(self.absolute is not None,'base step not observed');require(np.array_equal(env._asw_last_abs_pose,self.absolute[:6]),'wrapper target differs from command')
        site=env.sim.model.site_name2id('gripper0_right_grip_site');eef=env.sim.data.site_xpos[site].copy();cube=env.sim.data.body_xpos[env.cube_body_id].copy()
        success=bool(env._check_success());reward_success=bool(reward==1);grasp=bool(env._check_grasp(gripper=env.robots[0].gripper,object_geoms=env.cube))
        contacts=[]
        for j in range(env.sim.data.ncon):
            c=env.sim.data.contact[j];contacts.append(dict(geom1=env.sim.model.geom_id2name(c.geom1),geom2=env.sim.model.geom_id2name(c.geom2),distance=float(c.dist)))
        row=dict(step=len(self.rows),delta=delta.tolist(),absolute_target=self.absolute.tolist(),eef_pos=eef.tolist(),target_translation_tracking_error_m=float(np.linalg.norm(eef-self.absolute[:3])),eef_rotation=env.sim.data.site_xmat[site].reshape(3,3).tolist(),cube_position=cube.tolist(),distance_m=float(np.linalg.norm(eef-cube)),reach=bool(np.linalg.norm(eef-cube)<.05),grasp=grasp,success=success,reward=float(reward),reward_equals_one=reward_success,success_interfaces_agree=success==reward_success,gripper_command=float(delta[-1]),gripper_state=gripper_state(env,obs),contacts=contacts,sim_state=env.sim.get_state().flatten().tolist(),done=bool(done))
        self.rows.append(row);append(self.folder/(self.label+'_steps.jsonl'),row)
        require(success==reward_success,'reward==1 and original _check_success disagree')
        require(not done,'environment terminated before fixed trajectory end')
        return row
    def summary(self):
        require(self.rows,'empty control trajectory')
        return dict(steps=len(self.rows),success=any(x['success'] for x in self.rows),reach=any(x['reach'] for x in self.rows),grasp=any(x['grasp'] for x in self.rows),success_interfaces_agree=all(x['success_interfaces_agree'] for x in self.rows),minimum_EEF_cube_distance_m=min(x['distance_m'] for x in self.rows),initial_EEF=self.initial_EEF,initial_EEF_rotation=self.initial_EEF_rotation,initial_gripper=self.initial_gripper,initial_cube=self.initial_cube,initial_step_EEF=self.rows[0]['eef_pos'],final_EEF=self.rows[-1]['eef_pos'],maximum_cube_height_m=max(x['cube_position'][2] for x in self.rows),trajectory=str((self.folder/(self.label+'_steps.jsonl')).relative_to(P)))
